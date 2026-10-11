"""G7 checks on the NLP Architect.

The plan's G7 condition: choices are valid catalogue entries, the budget cap is
respected, and rationale is logged. These run without a model; the planning
client is stubbed.
"""

import json

import pytest

from src.analyzer.spec import Constraints, EntitySpec, IntentSpec, ProjectSpec
from src.architect.architect import (
    FALLBACK_ORDER,
    INITIAL_BUDGET,
    TOTAL_BUDGET,
    Architect,
    coverage_note,
    error_report,
)
from src.architect.architect import Attempt
from src.llm import client as client_mod
from src.llm.client import LLMClient
from src.pipelines.catalogue import CATALOGUE, CATALOGUE_BY_ID

POOL = [
    {"case_id": "k1", "utt": "wake me up at six am", "true_intent": "alarm_set",
     "in_scope": True, "entities": [{"type": "time", "text": "six am", "start": 14, "end": 20}]},
    {"case_id": "k2", "utt": "cancel my alarm", "true_intent": "alarm_remove",
     "in_scope": True, "entities": []},
]

SPEC = ProjectSpec(
    project_id="PT", name="Test project",
    description_text="An assistant that sets and cancels alarms.",
    intents=[IntentSpec("alarm_set"), IntentSpec("alarm_remove")],
    entity_types=[EntitySpec("time"), EntitySpec("date")],
    slots_by_intent={"alarm_set": ["time"], "alarm_remove": []},
    constraints=Constraints(),
)


def metrics(intent=0.5, entity=0.5, schema=1.0, p95=None):
    return {
        "primary": {
            "intent_macro_f1": intent,
            "entity_span_f1": entity,
            "schema_validity_after_repair": schema,
            "latency_p95_s": p95,
            "false_rejection_rate_in_scope": 0.1,
            "unsupported_extraction_rate": 0.0,
            "runtime_failure_rate": 0.0,
        }
    }


def scored(scores: dict[str, float] | None = None, calls=(100, 50)):
    """Evaluator giving each configuration id a fixed intent score."""
    scores = scores or {}

    def evaluate(config):
        return metrics(intent=scores.get(config.config_id, 0.4)), calls[0], calls[1]

    return evaluate


class _Stub:
    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def __call__(self, request, timeout=None):  # noqa: ARG002
        self.prompts.append(json.loads(request.data.decode("utf-8"))["prompt"])
        reply = self.replies.pop(0) if self.replies else '{"choices": []}'
        return _Resp(reply)


class _Resp:
    def __init__(self, text):
        self._text = text

    def read(self):
        return json.dumps({"response": self._text, "prompt_eval_count": 300,
                           "eval_count": 60}).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def stubbed(monkeypatch):
    def make(replies):
        stub = _Stub(replies)
        monkeypatch.setattr(client_mod.urllib.request, "urlopen", stub)
        return Architect(client=LLMClient(model="t", model_digest="d", cache=None)), stub

    return make


def choices(*pairs):
    return json.dumps({"choices": [{"config_id": c, "why": w} for c, w in pairs]})


# -- the budget --------------------------------------------------------


def test_the_budget_is_three_initial_plus_one_revision():
    assert INITIAL_BUDGET == 3
    assert TOTAL_BUDGET == 4


def test_exactly_four_configurations_are_evaluated(stubbed):
    architect, _ = stubbed([
        choices(("joint-fixed-llm", "a"), ("twostage-sim-llm", "b"), ("schema-fixed-llm", "c")),
        choices(("joint-sim-tfidf", "d")),
    ])
    result = architect.design(SPEC, POOL, scored())

    assert result.budget_used == 4
    assert len(result.attempts) == 4
    assert [a.stage for a in result.attempts] == ["initial"] * 3 + ["revision"]


def test_a_model_proposing_too_many_is_cut_to_the_budget(stubbed):
    architect, _ = stubbed([
        choices(*[(c.config_id, "why") for c in CATALOGUE[:8]]),
        choices(("joint-sim-tfidf", "d")),
    ])
    result = architect.design(SPEC, POOL, scored())

    assert result.budget_used == TOTAL_BUDGET
    assert any("budget of 3" in f for f in result.findings)


def test_no_duplicate_configuration_is_evaluated_twice(stubbed):
    architect, _ = stubbed([
        choices(("joint-fixed-llm", "a"), ("joint-fixed-llm", "a again"), ("schema-fixed-llm", "c")),
        choices(("joint-sim-tfidf", "d")),
    ])
    result = architect.design(SPEC, POOL, scored())
    ids = [a.config_id for a in result.attempts]

    assert len(ids) == len(set(ids))
    assert any("twice" in f for f in result.findings)


def test_the_revision_cannot_repeat_an_already_tried_configuration(stubbed):
    architect, _ = stubbed([
        choices(("joint-fixed-llm", "a"), ("twostage-sim-llm", "b"), ("schema-fixed-llm", "c")),
        choices(("joint-fixed-llm", "let us try it again")),
    ])
    result = architect.design(SPEC, POOL, scored())
    ids = [a.config_id for a in result.attempts]

    assert len(ids) == len(set(ids))
    assert any("not an available configuration" in f for f in result.findings)


# -- only real catalogue entries ---------------------------------------


def test_every_evaluated_configuration_is_a_real_catalogue_entry(stubbed):
    architect, _ = stubbed([
        choices(("joint-fixed-llm", "a"), ("twostage-sim-llm", "b"), ("schema-fixed-llm", "c")),
        choices(("joint-sim-tfidf", "d")),
    ])
    result = architect.design(SPEC, POOL, scored())

    for attempt in result.attempts:
        assert attempt.config_id in CATALOGUE_BY_ID


def test_a_hallucinated_configuration_is_discarded_and_reported(stubbed):
    architect, _ = stubbed([
        choices(("joint-fixed-llm", "a"), ("magic-best-config", "trust me"),
                ("schema-fixed-llm", "c")),
        choices(("joint-sim-tfidf", "d")),
    ])
    result = architect.design(SPEC, POOL, scored())

    assert "magic-best-config" not in [a.config_id for a in result.attempts]
    assert any("magic-best-config" in f and "discarded" in f for f in result.findings)
    # The gap is filled, so the budget is still used in full.
    assert result.budget_used == TOTAL_BUDGET


def test_a_discarded_proposal_is_replaced_by_a_recorded_fallback(stubbed):
    architect, _ = stubbed([
        choices(("magic-one", "x"), ("magic-two", "y"), ("magic-three", "z")),
        choices(("joint-sim-tfidf", "d")),
    ])
    result = architect.design(SPEC, POOL, scored())
    initial = [a for a in result.attempts if a.stage == "initial"]

    assert all(a.source == "fallback" for a in initial)
    assert result.reasoned_choices == 1  # only the revision was usable
    assert [a.config_id for a in initial] == list(FALLBACK_ORDER[:3])


# -- rationale and records ---------------------------------------------


def test_every_attempt_records_a_rationale_and_its_source(stubbed):
    architect, _ = stubbed([
        choices(("joint-fixed-llm", "fewest calls, covers every intent"),
                ("twostage-sim-llm", "narrower second prompt"),
                ("schema-fixed-llm", "descriptions help unseen fields")),
        choices(("joint-sim-tfidf", "cheaper rejection")),
    ])
    result = architect.design(SPEC, POOL, scored())

    for attempt in result.attempts:
        assert attempt.rationale
        assert attempt.source in ("reasoned", "fallback")
    assert result.attempts[0].rationale == "fewest calls, covers every intent"
    assert result.reasoned_choices == 4


def test_the_record_separates_reasoned_from_fallback_choices(stubbed):
    architect, _ = stubbed([choices(("joint-fixed-llm", "a")), choices()])
    record = architect.design(SPEC, POOL, scored()).as_dict()

    assert record["reasoned_choices"] + record["fallback_choices"] == record["budget_used"]
    assert record["budget"] == TOTAL_BUDGET


def test_planning_calls_are_counted_separately_from_runtime_calls(stubbed):
    architect, _ = stubbed([
        choices(("joint-fixed-llm", "a"), ("twostage-sim-llm", "b"), ("schema-fixed-llm", "c")),
        choices(("joint-sim-tfidf", "d")),
    ])
    result = architect.design(SPEC, POOL, scored(calls=(100, 50)))

    assert result.planning_calls == 2, "one initial call plus one revision call"
    assert result.logical_calls == 400, "four candidates at 100 logical calls each"


def test_an_event_is_logged_per_attempt_plus_one_decision(stubbed):
    architect, _ = stubbed([
        choices(("joint-fixed-llm", "a"), ("twostage-sim-llm", "b"), ("schema-fixed-llm", "c")),
        choices(("joint-sim-tfidf", "d")),
    ])
    result = architect.design(SPEC, POOL, scored())
    kinds = [e["kind"] for e in result.events]

    assert kinds.count("candidate_attempt") == 4
    assert kinds.count("selection_decision") == 1


# -- selection and the explicit no-eligible outcome --------------------


def test_the_best_evaluated_candidate_is_selected(stubbed):
    architect, _ = stubbed([
        choices(("joint-fixed-llm", "a"), ("twostage-sim-llm", "b"), ("schema-fixed-llm", "c")),
        choices(("joint-sim-tfidf", "d")),
    ])
    result = architect.design(SPEC, POOL, scored({"twostage-sim-llm": 0.9}))

    assert result.selection.selected.config_id == "twostage-sim-llm"


def test_no_eligible_candidate_is_reported_explicitly(stubbed):
    architect, _ = stubbed([
        choices(("joint-fixed-llm", "a"), ("twostage-sim-llm", "b"), ("schema-fixed-llm", "c")),
        choices(("joint-sim-tfidf", "d")),
    ])
    result = architect.design(SPEC, POOL, scored(), min_entity_f1=0.95)

    assert result.selection.no_eligible_candidate
    assert any("no-eligible-candidate" in f for f in result.findings)
    assert result.as_dict()["selection"]["selected"] is None


def test_a_candidate_that_crashes_is_recorded_and_excluded_from_selection(stubbed):
    architect, _ = stubbed([
        choices(("joint-fixed-llm", "a"), ("twostage-sim-llm", "b"), ("schema-fixed-llm", "c")),
        choices(("joint-sim-tfidf", "d")),
    ])

    def evaluate(config):
        if config.config_id == "twostage-sim-llm":
            raise RuntimeError("model unavailable")
        return metrics(intent=0.5), 100, 50

    result = architect.design(SPEC, POOL, evaluate)
    crashed = [a for a in result.attempts if a.error]

    assert len(crashed) == 1
    assert "model unavailable" in crashed[0].error
    assert result.budget_used == 4, "a crash still consumes its budget slot"
    assert "twostage-sim-llm" not in result.selection.eligible


# -- behaviour without a planning model --------------------------------


def test_without_a_model_the_fallback_ordering_is_used_and_declared():
    result = Architect(client=None).design(SPEC, POOL, scored())

    assert result.budget_used == TOTAL_BUDGET
    assert result.reasoned_choices == 0
    assert [a.config_id for a in result.attempts] == list(FALLBACK_ORDER[:4])
    assert any("no planning model" in f for f in result.findings)
    assert result.planning_calls == 0


def test_an_unparseable_planning_reply_falls_back_and_says_so(stubbed):
    architect, _ = stubbed(["I would try the joint one", '{"choices": []}'])
    result = architect.design(SPEC, POOL, scored())

    assert any("not JSON" in f for f in result.findings)
    assert result.reasoned_choices == 0
    assert result.budget_used == TOTAL_BUDGET


def test_a_failed_planning_call_falls_back(monkeypatch):
    def boom(request, timeout=None):  # noqa: ARG001
        raise TimeoutError("read timed out")

    monkeypatch.setattr(client_mod.urllib.request, "urlopen", boom)
    architect = Architect(client=LLMClient(model="t", cache=None))
    result = architect.design(SPEC, POOL, scored())

    assert any("planning call failed" in f for f in result.findings)
    assert result.budget_used == TOTAL_BUDGET


# -- what the Architect is told -----------------------------------------


def test_the_prompt_carries_the_project_specification_and_the_catalogue(stubbed):
    architect, stub = stubbed([
        choices(("joint-fixed-llm", "a"), ("twostage-sim-llm", "b"), ("schema-fixed-llm", "c")),
        choices(("joint-sim-tfidf", "d")),
    ])
    architect.design(SPEC, POOL, scored())
    initial = stub.prompts[0]

    assert "sets and cancels alarms" in initial
    assert "joint-fixed-llm" in initial and "schema-sim-tfidf" in initial
    assert "2 request types" in initial or "recognise 2" in initial


def test_the_revision_prompt_contains_the_error_report_and_excludes_tried_ids(stubbed):
    architect, stub = stubbed([
        choices(("joint-fixed-llm", "a"), ("twostage-sim-llm", "b"), ("schema-fixed-llm", "c")),
        choices(("joint-sim-tfidf", "d")),
    ])
    architect.design(SPEC, POOL, scored({"joint-fixed-llm": 0.81}))
    revision = stub.prompts[1]

    assert "0.810" in revision, "the revision step must see how the first attempts scored"
    assert "intent macro-F1" in revision
    remaining_section = revision.split("have NOT tried:")[1]
    assert "joint-fixed-llm" not in remaining_section


def test_the_coverage_note_states_missing_field_examples():
    note = coverage_note(SPEC, POOL)

    assert "no example" in note
    assert "date" in note


def test_the_coverage_note_says_so_when_coverage_is_complete():
    pool = POOL + [
        {"case_id": "k3", "utt": "alarm on friday", "true_intent": "alarm_set", "in_scope": True,
         "entities": [{"type": "date", "text": "friday", "start": 9, "end": 15}]}
    ]

    assert "Every kind of information" in coverage_note(SPEC, pool)


def test_the_error_report_names_failures_as_well_as_scores():
    attempts = [
        Attempt("joint-fixed-llm", "a", "reasoned", "initial", metrics=metrics(intent=0.7)),
        Attempt("twostage-sim-llm", "b", "reasoned", "initial", error="TimeoutError: x"),
    ]
    report = error_report(attempts)

    assert "0.700" in report
    assert "failed to run" in report
