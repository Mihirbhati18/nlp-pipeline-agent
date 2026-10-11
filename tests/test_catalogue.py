"""G4 checks on the 12-configuration execution catalogue.

The model server is replaced by a stub, so these run without Ollama. The
completion condition that all 12 configurations run on real P1/P2 development
cases is the separate `scripts/run_catalogue_check.py`, which needs a model.
"""

import json

import pytest

from src.analyzer.spec import Constraints, EntitySpec, IntentSpec, ProjectSpec
from src.evaluation.scorer import STATUS_OOS
from src.llm import client as client_mod
from src.llm.client import MAX_INPUT_TOKENS, LLMClient, estimate_tokens
from src.pipelines.catalogue import (
    B1_CONFIG_ID,
    CATALOGUE,
    Config,
    ConfigRunner,
    build_catalogue,
    get_config,
    render_prompt,
)
from src.pipelines.examples import ExampleSelector

POOL = [
    {"case_id": "k1", "utt": "wake me up at six am", "true_intent": "alarm_set", "in_scope": True,
     "entities": [{"type": "time", "text": "six am", "start": 14, "end": 20}]},
    {"case_id": "k2", "utt": "cancel my alarm for noon", "true_intent": "alarm_remove",
     "in_scope": True, "entities": [{"type": "time", "text": "noon", "start": 20, "end": 24}]},
    {"case_id": "k3", "utt": "what alarms are set", "true_intent": "alarm_query",
     "in_scope": True, "entities": []},
    {"case_id": "k4", "utt": "turn off the kitchen light", "true_intent": "iot_hue_lightoff",
     "in_scope": True, "entities": [{"type": "house_place", "text": "kitchen", "start": 13, "end": 20}]},
]

CASE = {
    "case_id": "d1",
    "utt": "set an alarm for five am",
    "true_intent": "alarm_set",
    "in_scope": True,
    "entities": [{"type": "time", "text": "five am", "start": 17, "end": 24}],
}

SPEC = ProjectSpec(
    project_id="PT",
    name="Test project",
    description_text="A test project.",
    intents=[
        IntentSpec("alarm_set"), IntentSpec("alarm_remove"),
        IntentSpec("alarm_query"), IntentSpec("iot_hue_lightoff"),
    ],
    entity_types=[EntitySpec("time"), EntitySpec("date"), EntitySpec("house_place")],
    slots_by_intent={
        "alarm_set": ["date", "time"], "alarm_remove": ["time"],
        "alarm_query": [], "iot_hue_lightoff": ["house_place"],
    },
    constraints=Constraints(),
)


class _Stub:
    """Returns a queued reply per call, recording the prompts it received."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def __call__(self, request, timeout=None):  # noqa: ARG002
        self.prompts.append(json.loads(request.data.decode("utf-8"))["prompt"])
        reply = self.replies.pop(0) if self.replies else '{"intent": "alarm_set", "entities": []}'
        return _Resp(reply)


class _Resp:
    def __init__(self, text):
        self._text = text

    def read(self):
        return json.dumps(
            {"response": self._text, "prompt_eval_count": 200, "eval_count": 20}
        ).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def make_runner(monkeypatch, config, replies, *, threshold=None):
    stub = _Stub(replies)
    monkeypatch.setattr(client_mod.urllib.request, "urlopen", stub)
    client = LLMClient(model="test:3b", model_digest="sha256:t", cache=None)
    runner = ConfigRunner(
        config=config, spec=SPEC, client=client,
        selector=ExampleSelector(POOL), oos_threshold=threshold,
    )
    return runner, stub


# -- the catalogue itself ----------------------------------------------


def test_the_catalogue_has_exactly_twelve_unique_configurations():
    assert len(CATALOGUE) == 12
    assert len({c.config_id for c in CATALOGUE}) == 12


def test_the_catalogue_covers_every_factor_combination():
    combinations = {(c.extraction, c.example_selection, c.oos_policy) for c in CATALOGUE}

    assert len(combinations) == 12
    assert {c.extraction for c in CATALOGUE} == {"joint", "two_stage", "schema_guided"}
    assert {c.example_selection for c in CATALOGUE} == {"fixed", "similarity"}
    assert {c.oos_policy for c in CATALOGUE} == {"llm_label", "tfidf_threshold"}


def test_the_catalogue_order_is_stable():
    assert [c.config_id for c in build_catalogue()] == [c.config_id for c in CATALOGUE]


def test_four_configurations_are_two_stage_and_cost_two_calls():
    two_stage = [c for c in CATALOGUE if c.calls_per_request == 2]

    assert len(two_stage) == 4, "the plan's budget assumes 4 two-stage configurations"
    assert all(c.extraction == "two_stage" for c in two_stage)
    assert len([c for c in CATALOGUE if c.calls_per_request == 1]) == 8


def test_b1s_configuration_is_in_the_catalogue_and_is_the_predeclared_one():
    config = get_config(B1_CONFIG_ID)

    assert config.extraction == "joint"
    assert config.example_selection == "fixed"
    assert config.oos_policy == "llm_label"


def test_an_unknown_configuration_id_is_refused():
    with pytest.raises(KeyError, match="not a catalogue configuration"):
        get_config("joint-fixed-magic")


# -- prompt rendering --------------------------------------------------


def test_every_configuration_renders_a_prompt_within_the_cap():
    for config in CATALOGUE:
        prompt, n_examples = render_prompt(config, SPEC, CASE["utt"], SPEC and POOL)
        assert estimate_tokens(prompt) <= MAX_INPUT_TOKENS, config.config_id
        assert n_examples <= 16
        assert CASE["utt"] in prompt


def test_the_llm_label_policy_offers_the_out_of_scope_label_and_tfidf_does_not():
    with_label = get_config("joint-fixed-llm")
    without = get_config("joint-fixed-tfidf")

    assert "none_of_the_above" in render_prompt(with_label, SPEC, CASE["utt"], POOL)[0]
    assert "none_of_the_above" not in render_prompt(without, SPEC, CASE["utt"], POOL)[0]


def test_schema_guided_includes_field_descriptions_when_the_spec_has_them():
    enriched = SPEC.with_descriptions(
        {"alarm_set": "the user asks to create an alarm"},
        {"time": "a clock time as written in the request"},
    )
    plain = render_prompt(get_config("joint-fixed-llm"), enriched, CASE["utt"], POOL)[0]
    guided = render_prompt(get_config("schema-fixed-llm"), enriched, CASE["utt"], POOL)[0]

    assert "a clock time as written in the request" in guided
    assert "a clock time as written in the request" not in plain


def test_definitions_are_never_dropped_to_fit_the_cap():
    """Examples go first; every intent must survive."""
    long_pool = [
        {**POOL[i % len(POOL)], "case_id": f"k{i}", "utt": POOL[i % len(POOL)]["utt"] + " " + "x" * 700}
        for i in range(16)
    ]
    prompt, n_examples = render_prompt(get_config("joint-fixed-llm"), SPEC, CASE["utt"], long_pool)

    assert n_examples < 16, "examples were dropped to meet the cap"
    for intent in SPEC.intent_names:
        assert intent in prompt


def test_fixed_selection_ignores_the_request_and_similarity_does_not():
    fixed = get_config("joint-fixed-llm")
    similar = get_config("joint-sim-llm")
    selector = ExampleSelector(POOL)

    def body(prompt: str) -> str:
        """Everything before the final request line: definitions and examples."""
        return prompt.rsplit("\nRequest: ", 1)[0]

    assert selector.fixed() == selector.fixed()
    a = render_prompt(fixed, SPEC, "turn off the kitchen light", selector.fixed())[0]
    b = render_prompt(fixed, SPEC, "wake me at six", selector.fixed())[0]
    assert body(a) == body(b), "fixed selection must not vary with the request"

    near = selector.similarity("turn off the kitchen light")
    assert near[0]["true_intent"] == "iot_hue_lightoff"
    assert body(render_prompt(similar, SPEC, "turn off the kitchen light", near)[0]) != body(a)


def test_fixed_selection_covers_one_example_per_intent():
    chosen = ExampleSelector(POOL).fixed()

    assert {c["true_intent"] for c in chosen} == set(SPEC.intent_names)
    assert len(chosen) == len(SPEC.intent_names)


def test_the_entity_stage_asks_only_for_that_intents_slots():
    prompt, _ = render_prompt(
        get_config("twostage-fixed-llm"), SPEC, CASE["utt"], POOL,
        stage="entities", intent="iot_hue_lightoff",
    )

    assert "house_place" in prompt
    assert "- time" not in prompt, "a slot that intent cannot carry must not be offered"


# -- execution ---------------------------------------------------------


def test_a_single_call_configuration_makes_one_call(monkeypatch):
    runner, stub = make_runner(
        monkeypatch, get_config("joint-fixed-llm"),
        ['{"intent": "alarm_set", "entities": [{"type": "time", "text": "five am"}]}'],
    )
    outcome = runner.run_case(CASE)

    assert len(stub.prompts) == 1
    assert outcome.logical_calls == 1
    assert outcome.prediction.status == "ok"
    assert outcome.prediction.intent == "alarm_set"
    assert outcome.prediction.schema_valid_final


def test_a_two_stage_configuration_makes_two_calls_and_merges_them(monkeypatch):
    runner, stub = make_runner(
        monkeypatch, get_config("twostage-fixed-llm"),
        ['{"intent": "alarm_set"}', '{"entities": [{"type": "time", "text": "five am"}]}'],
    )
    outcome = runner.run_case(CASE)

    assert len(stub.prompts) == 2
    assert outcome.logical_calls == 2
    assert outcome.prediction.intent == "alarm_set"
    assert outcome.prediction.entities == [{"type": "time", "text": "five am"}]


def test_two_stage_stops_after_one_call_when_the_intent_is_out_of_scope(monkeypatch):
    runner, stub = make_runner(
        monkeypatch, get_config("twostage-fixed-llm"), ['{"intent": "none_of_the_above"}'],
    )
    outcome = runner.run_case(CASE)

    assert len(stub.prompts) == 1, "no entity call for a rejected request"
    assert outcome.prediction.status == STATUS_OOS


def test_the_tfidf_policy_rejects_without_spending_a_call(monkeypatch):
    runner, stub = make_runner(
        monkeypatch, get_config("joint-fixed-tfidf"), [], threshold=0.99,
    )
    outcome = runner.run_case({**CASE, "utt": "what is the capital of peru"})

    assert stub.prompts == [], "a threshold rejection must cost no model call"
    assert outcome.prediction.status == STATUS_OOS
    assert outcome.rejected_by_threshold
    assert outcome.logical_calls == 0


def test_the_tfidf_policy_calls_the_model_when_the_request_looks_in_scope(monkeypatch):
    runner, stub = make_runner(
        monkeypatch, get_config("joint-fixed-tfidf"),
        ['{"intent": "alarm_set", "entities": []}'], threshold=0.0,
    )
    outcome = runner.run_case(CASE)

    assert len(stub.prompts) == 1
    assert outcome.rejected_by_threshold is False


def test_a_tfidf_configuration_refuses_to_run_without_a_tuned_threshold():
    from src.llm.client import LLMClient as C

    with pytest.raises(ValueError, match="tuned on development data"):
        ConfigRunner(
            config=get_config("joint-fixed-tfidf"), spec=SPEC,
            client=C(model="t", cache=None), selector=ExampleSelector(POOL),
        )


def test_invalid_output_triggers_exactly_one_counted_repair(monkeypatch):
    runner, stub = make_runner(
        monkeypatch, get_config("joint-fixed-llm"),
        ["not json at all", '{"intent": "alarm_set", "entities": []}'],
    )
    outcome = runner.run_case(CASE)

    assert len(stub.prompts) == 2
    assert "rejected" in stub.prompts[1], "the repair names the problem"
    assert outcome.repaired
    assert outcome.prediction.retries == 1
    assert outcome.prediction.schema_valid_raw is False
    assert outcome.prediction.schema_valid_final is True


def test_a_failed_repair_leaves_the_response_invalid(monkeypatch):
    runner, _ = make_runner(
        monkeypatch, get_config("joint-fixed-llm"), ["not json", "still not json"],
    )
    outcome = runner.run_case(CASE)

    assert outcome.prediction.status == "invalid"
    assert outcome.prediction.schema_valid_final is False


def test_repair_can_be_disabled_for_the_ablation(monkeypatch):
    stub = _Stub(["not json"])
    monkeypatch.setattr(client_mod.urllib.request, "urlopen", stub)
    runner = ConfigRunner(
        config=get_config("joint-fixed-llm"), spec=SPEC,
        client=LLMClient(model="t", cache=None), selector=ExampleSelector(POOL),
        allow_repair=False,
    )
    outcome = runner.run_case(CASE)

    assert len(stub.prompts) == 1
    assert outcome.repaired is False
    assert outcome.prediction.schema_valid_final is False


def test_a_runtime_failure_is_recorded_as_an_error_prediction(monkeypatch):
    def boom(request, timeout=None):  # noqa: ARG001
        raise TimeoutError("read timed out")

    monkeypatch.setattr(client_mod.urllib.request, "urlopen", boom)
    runner = ConfigRunner(
        config=get_config("joint-fixed-llm"), spec=SPEC,
        client=LLMClient(model="t", cache=None), selector=ExampleSelector(POOL),
    )
    outcome = runner.run_case(CASE)

    assert outcome.prediction.status == "error"
    assert "Timeout" in (outcome.prediction.error or "")
    assert outcome.prediction.schema_valid_final is False


def test_a_hallucinated_label_fails_the_schema_but_is_still_reported(monkeypatch):
    runner, _ = make_runner(
        monkeypatch, get_config("joint-fixed-llm"),
        ['{"intent": "iot_coffee", "entities": []}'] * 2,
    )
    outcome = runner.run_case(CASE)

    assert outcome.prediction.intent == "iot_coffee"
    assert outcome.prediction.schema_valid_final is False
