"""G8 checks on the full design run.

The plan's G8 condition: known synthetic score tables select the correct
candidate, and the no-eligible case is handled. These use a stubbed model, so
they run without Ollama.
"""

import json

import pytest

from src.analyzer.access import DataAccess, FinalTestLockedError
from src.analyzer.spec import Constraints, EntitySpec, IntentSpec, ProjectSpec
from src.architect.design_run import estimate_p95, make_config_evaluator, run_design
from src.llm import client as client_mod
from src.llm.client import LLMClient
from src.pipelines.catalogue import CATALOGUE, get_config

POOL = [
    {"case_id": "k1", "utt": "wake me up at six am", "true_intent": "alarm_set",
     "in_scope": True, "entities": [{"type": "time", "text": "six am", "start": 14, "end": 20}]},
    {"case_id": "k2", "utt": "cancel my alarm", "true_intent": "alarm_remove",
     "in_scope": True, "entities": []},
]
DEV = [
    {"case_id": "d1", "utt": "set an alarm for five am", "true_intent": "alarm_set",
     "in_scope": True,
     "entities": [{"type": "time", "text": "five am", "start": 17, "end": 24}]},
    {"case_id": "d2", "utt": "delete my alarm", "true_intent": "alarm_remove",
     "in_scope": True, "entities": []},
    {"case_id": "d3", "utt": "what is the weather", "true_intent": "weather_query",
     "in_scope": False, "entities": []},
]

SPEC = ProjectSpec(
    project_id="PT", name="Test project",
    description_text="An assistant that sets and cancels alarms for people at home.",
    intents=[IntentSpec("alarm_set"), IntentSpec("alarm_remove")],
    entity_types=[EntitySpec("time")],
    slots_by_intent={"alarm_set": ["time"], "alarm_remove": []},
    constraints=Constraints(),
    source={"kshot": "pool.jsonl", "dev": "dev.jsonl", "test": "test.jsonl"},
)


def access(**kwargs) -> DataAccess:
    return DataAccess(
        project_id="PT",
        sources={"kshot": "pool.jsonl", "dev": "dev.jsonl", "test": "test.jsonl"},
        **kwargs,
    )


def loader(path: str) -> list[dict]:
    return POOL if "pool" in path else DEV


class _Stub:
    """Routes by what the prompt asks for, since one client serves three roles.

    A single queue would be wrong: the Architect's planning reply would be
    consumed by a runtime prediction call, which is how an earlier version of
    this test quietly mis-measured the number of reasoned choices.
    """

    def __init__(self, enrichment=None, planning=None,
                 default='{"intent": "alarm_set", "entities": []}'):
        self.enrichment = list(enrichment or [])
        self.planning = list(planning or [])
        self.default = default
        self.prompts = []
        self.roles = []

    def __call__(self, request, timeout=None):  # noqa: ARG002
        prompt = json.loads(request.data.decode("utf-8"))["prompt"]
        self.prompts.append(prompt)
        if '{"descriptions"' in prompt:
            self.roles.append("enrichment")
            return _Resp(self.enrichment.pop(0) if self.enrichment else '{"descriptions": {}}')
        if '{"choices"' in prompt:
            self.roles.append("planning")
            return _Resp(self.planning.pop(0) if self.planning else '{"choices": []}')
        self.roles.append("runtime")
        return _Resp(self.default)


class _Resp:
    def __init__(self, text):
        self._text = text

    def read(self):
        return json.dumps({"response": self._text, "prompt_eval_count": 200,
                           "eval_count": 20}).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


ENRICHMENT = [
    '{"descriptions": {"alarm_set": "create an alarm", "alarm_remove": "delete an alarm"}}',
    '{"descriptions": {"time": "a clock time as written"}}',
]
PLANNING = [
    json.dumps({"choices": [
        {"config_id": "joint-fixed-llm", "why": "fewest calls"},
        {"config_id": "twostage-sim-llm", "why": "narrower second prompt"},
        {"config_id": "schema-fixed-llm", "why": "descriptions help"},
    ]}),
    json.dumps({"choices": [{"config_id": "joint-sim-llm", "why": "closer examples"}]}),
]


def client_with(monkeypatch, enrichment=None, planning=None,
                default='{"intent": "alarm_set", "entities": []}'):
    stub = _Stub(enrichment, planning, default)
    monkeypatch.setattr(client_mod.urllib.request, "urlopen", stub)
    return LLMClient(model="t", model_digest="d", cache=None), stub


# -- the latency estimate ----------------------------------------------


def test_a_two_stage_configuration_is_estimated_at_twice_a_single_call():
    assert estimate_p95(get_config("joint-fixed-llm"), 0.6) == pytest.approx(0.6)
    assert estimate_p95(get_config("twostage-fixed-llm"), 0.6) == pytest.approx(1.2)


# -- the shared evaluator ----------------------------------------------


def test_a1_and_b4_are_given_the_same_evaluator(monkeypatch):
    """The same closure must score a configuration identically for both."""
    client, _ = client_with(monkeypatch)
    collected = []
    evaluate = make_config_evaluator(SPEC, client, POOL, DEV, 0.0, collect=collected)

    first = evaluate(get_config("joint-fixed-llm"))
    second = evaluate(get_config("joint-fixed-llm"))

    assert first[0]["primary"]["intent_macro_f1"] == second[0]["primary"]["intent_macro_f1"]
    assert len(collected) == 2


def test_evaluation_never_produces_a_latency_figure(monkeypatch):
    client, _ = client_with(monkeypatch)
    evaluate = make_config_evaluator(SPEC, client, POOL, DEV, 0.0)
    metrics, _, _ = evaluate(get_config("joint-fixed-llm"))

    assert metrics["primary"]["latency_median_s"] is None
    assert metrics["primary"]["latency_p95_s"] is None


def test_the_evaluator_reports_logical_and_physical_calls(monkeypatch):
    client, _ = client_with(monkeypatch)
    evaluate = make_config_evaluator(SPEC, client, POOL, DEV, 0.0)
    _, logical, physical = evaluate(get_config("joint-fixed-llm"))

    assert logical >= len(DEV)
    assert physical >= 0


# -- the full design ---------------------------------------------------


def test_a_full_design_enriches_then_picks_four_candidates(monkeypatch):
    client, stub = client_with(monkeypatch, list(ENRICHMENT), list(PLANNING))
    design = run_design(SPEC, access(), runtime_client=client, planning_client=client,
                        load_cases=loader)

    assert design.analysis.ok
    assert design.analysis.spec.enriched is True
    assert design.design.budget_used == 4
    assert design.design.reasoned_choices == 4
    assert design.selected_config_id in {c.config_id for c in CATALOGUE}


def test_design_cost_includes_analyzer_and_planning_calls(monkeypatch):
    client, _ = client_with(monkeypatch, list(ENRICHMENT), list(PLANNING))
    design = run_design(SPEC, access(), runtime_client=client, planning_client=client,
                        load_cases=loader)
    record = design.as_dict()["design_cost"]

    assert record["analyzer_calls"] == 2, "enrichment is design cost, not free overhead"
    assert record["planning_calls"] == 2
    assert record["logical_calls"] == record["analyzer_calls"] + record["candidate_calls"]


def test_the_design_selects_the_best_scoring_candidate(monkeypatch):
    """A known score table must pick the known winner."""
    client, _ = client_with(monkeypatch, list(ENRICHMENT), list(PLANNING))

    # Override the evaluator with a fixed score table via the Architect path.
    from src.architect.architect import Architect

    scores = {"twostage-sim-llm": 0.91, "joint-fixed-llm": 0.44,
              "schema-fixed-llm": 0.52, "joint-sim-llm": 0.63}

    def evaluate(config):
        return (
            {"primary": {"intent_macro_f1": scores.get(config.config_id, 0.1),
                         "entity_span_f1": 0.5,
                         "schema_validity_after_repair": 1.0,
                         "latency_p95_s": None}},
            10, 5,
        )

    result = Architect(client=client).design(SPEC, POOL, evaluate)

    assert result.selection.selected.config_id == "twostage-sim-llm"


def test_a_contradictory_specification_stops_the_design_before_any_candidate(monkeypatch):
    client, stub = client_with(monkeypatch, list(ENRICHMENT), list(PLANNING))
    broken = ProjectSpec(
        project_id="PT", name="Broken", description_text="x",
        intents=[IntentSpec("alarm_set"), IntentSpec("alarm_set")],
        entity_types=[EntitySpec("time")],
        slots_by_intent={}, constraints=Constraints(),
        source=dict(SPEC.source),
    )
    design = run_design(broken, access(), runtime_client=client, planning_client=client,
                        load_cases=loader)

    assert not design.analysis.ok
    assert design.design.budget_used == 0
    assert design.selected_config_id is None
    assert any("contradictory" in f for f in design.design.findings)


def test_an_impossible_constraint_yields_an_explicit_no_eligible_outcome(monkeypatch):
    client, _ = client_with(monkeypatch, list(ENRICHMENT), list(PLANNING))
    design = run_design(SPEC, access(), runtime_client=client, planning_client=client,
                        load_cases=loader, min_entity_f1=1.01)

    assert design.design.selection.no_eligible_candidate
    assert design.selected_config_id is None
    assert design.as_dict()["no_eligible_candidate"] is True


def test_the_no_analyzer_ablation_skips_enrichment(monkeypatch):
    client, stub = client_with(monkeypatch, list(ENRICHMENT), list(PLANNING))
    design = run_design(SPEC, access(), runtime_client=client, planning_client=client,
                        load_cases=loader, enrich=False)

    assert design.analysis.spec.enriched is False
    assert design.analysis.logical_calls == 0
    assert design.design.budget_used == 4, "the search still runs"


def test_without_a_planning_client_the_record_shows_no_reasoning(monkeypatch):
    client, _ = client_with(monkeypatch, list(ENRICHMENT), None)
    design = run_design(SPEC, access(), runtime_client=client, planning_client=None,
                        load_cases=loader)

    assert design.design.reasoned_choices == 0
    assert design.design.budget_used == 4
    assert design.design.planning_calls == 0


# -- data access -------------------------------------------------------


def test_a_design_run_never_touches_the_test_split(monkeypatch):
    client, _ = client_with(monkeypatch, list(ENRICHMENT), list(PLANNING))
    handle = access()
    run_design(SPEC, handle, runtime_client=client, planning_client=client,
               load_cases=loader)

    assert "test" not in handle.splits_accessed
    assert set(handle.splits_accessed) == {"kshot", "dev"}


def test_the_test_split_would_be_refused_if_asked_for(monkeypatch):
    handle = access()
    with pytest.raises(FinalTestLockedError):
        handle.test_path


def test_the_design_record_states_which_splits_it_read(monkeypatch):
    client, _ = client_with(monkeypatch, list(ENRICHMENT), list(PLANNING))
    design = run_design(SPEC, access(), runtime_client=client, planning_client=client,
                        load_cases=loader)
    record = design.as_dict()["data_access"]

    assert record["freeze_released"] is False
    assert "kshot" in record["splits_accessed"] and "dev" in record["splits_accessed"]
    assert "test" not in record["splits_accessed"]


# -- the out-of-scope threshold ----------------------------------------


def test_the_threshold_is_tuned_on_development_data_and_recorded(monkeypatch):
    client, _ = client_with(monkeypatch, list(ENRICHMENT), list(PLANNING))
    design = run_design(SPEC, access(), runtime_client=client, planning_client=client,
                        load_cases=loader)
    record = design.oos_threshold.as_dict()

    assert record["tuned_on"] == "development split only"
    assert "binary" in record["criterion"]
