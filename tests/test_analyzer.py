"""G6 checks on the Project Analyzer.

The plan's G6 test condition: matches gold specification fixtures, rejects
duplicate or conflicting labels, handles absent optional fields, preserves
constraints, and keeps held-out test paths inaccessible (the last is covered in
`test_access.py`).
"""

import json

import pytest

from src.analyzer.analyzer import Analyzer, validate
from src.analyzer.spec import Constraints, EntitySpec, IntentSpec, ProjectSpec
from src.llm import client as client_mod
from src.llm.client import LLMClient

POOL = [
    {"case_id": "k1", "utt": "wake me up at six am", "true_intent": "alarm_set",
     "in_scope": True, "entities": [{"type": "time", "text": "six am", "start": 14, "end": 20}]},
    {"case_id": "k2", "utt": "cancel my alarm", "true_intent": "alarm_remove",
     "in_scope": True, "entities": []},
]


def spec(**kwargs) -> ProjectSpec:
    base = dict(
        project_id="PT",
        name="Test project",
        description_text="An assistant that sets and cancels alarms for people at home.",
        intents=[IntentSpec("alarm_set"), IntentSpec("alarm_remove")],
        entity_types=[EntitySpec("time")],
        slots_by_intent={"alarm_set": ["time"], "alarm_remove": []},
        constraints=Constraints(),
    )
    base.update(kwargs)
    return ProjectSpec(**base)


def kinds(findings):
    return {f.kind for f in findings}


# -- validation, no model ----------------------------------------------


def test_a_clean_specification_produces_no_blocking_finding():
    findings = validate(spec(), POOL)

    assert not [f for f in findings if f.blocking]


def test_duplicate_intents_are_rejected():
    findings = validate(
        spec(intents=[IntentSpec("alarm_set"), IntentSpec("alarm_set")]), POOL
    )

    assert "duplicate_intents" in kinds(findings)
    assert any(f.blocking for f in findings if f.kind == "duplicate_intents")


def test_duplicate_entity_types_are_rejected():
    findings = validate(spec(entity_types=[EntitySpec("time"), EntitySpec("time")]), POOL)

    assert "duplicate_entity_types" in kinds(findings)


def test_declaring_the_reserved_out_of_scope_label_is_rejected():
    findings = validate(
        spec(intents=[IntentSpec("alarm_set"), IntentSpec("none_of_the_above")]), POOL
    )

    assert "oos_label_in_inventory" in kinds(findings)


def test_an_empty_intent_inventory_is_rejected():
    assert "no_intents" in kinds(validate(spec(intents=[]), POOL))


def test_an_empty_description_is_rejected():
    assert "no_description" in kinds(validate(spec(description_text="   "), POOL))


def test_an_impossible_latency_constraint_is_rejected():
    findings = validate(spec(constraints=Constraints(max_p95_latency_s=0)), POOL)

    assert "impossible_latency_constraint" in kinds(findings)


def test_an_out_of_range_schema_constraint_is_rejected():
    findings = validate(spec(constraints=Constraints(min_schema_validity=1.5)), POOL)

    assert "impossible_schema_constraint" in kinds(findings)


def test_examples_outside_the_declared_inventory_are_a_conflict():
    """A pool intent the project never declares is a real contradiction."""
    findings = validate(spec(intents=[IntentSpec("alarm_set")]), POOL)
    conflict = [f for f in findings if f.kind == "examples_outside_the_inventory"]

    assert conflict and conflict[0].blocking
    assert "alarm_remove" in conflict[0].message


def test_entity_types_outside_the_schema_are_a_conflict():
    findings = validate(spec(entity_types=[]), POOL)
    conflict = [f for f in findings if f.kind == "entity_types_outside_the_schema"]

    assert conflict and conflict[0].blocking
    assert "time" in conflict[0].message


def test_a_declared_intent_with_no_example_is_reported_but_not_blocking():
    findings = validate(
        spec(intents=[IntentSpec("alarm_set"), IntentSpec("alarm_remove"), IntentSpec("alarm_query")]),
        POOL,
    )
    gap = [f for f in findings if f.kind == "intents_without_examples"]

    assert gap and not gap[0].blocking
    assert "alarm_query" in gap[0].message


def test_a_declared_entity_type_with_no_example_is_reported_but_not_blocking():
    findings = validate(spec(entity_types=[EntitySpec("time"), EntitySpec("date")]), POOL)
    gap = [f for f in findings if f.kind == "entity_types_without_examples"]

    assert gap and not gap[0].blocking


def test_absent_optional_constraints_are_fine():
    """Optional fields left unset must not be treated as errors."""
    result = validate(spec(constraints=Constraints()), POOL)

    assert not [f for f in result if f.blocking]


def test_constraints_are_preserved_through_analysis():
    constraints = Constraints(max_p95_latency_s=2.5, min_schema_validity=0.98, notes="tight")
    result = Analyzer(client=None).analyze(spec(constraints=constraints), POOL)

    assert result.spec.constraints.max_p95_latency_s == 2.5
    assert result.spec.constraints.min_schema_validity == 0.98
    assert result.spec.constraints.notes == "tight"


# -- the no-model path (the ablation) ----------------------------------


def test_without_a_client_the_specification_is_returned_bare():
    result = Analyzer(client=None).analyze(spec(), POOL)

    assert result.ok
    assert result.spec.enriched is False
    assert all(i.description is None for i in result.spec.intents)
    assert result.logical_calls == 0


def test_a_blocking_finding_stops_before_any_model_call():
    stub = _Stub(['{"descriptions": {}}'])
    result = Analyzer(client=_client(stub)).analyze(
        spec(intents=[IntentSpec("a"), IntentSpec("a")]), POOL
    )

    assert not result.ok
    assert stub.prompts == [], "a contradiction must not be papered over by a model call"
    assert result.logical_calls == 0


# -- enrichment --------------------------------------------------------


class _Stub:
    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def __call__(self, request, timeout=None):  # noqa: ARG002
        self.prompts.append(json.loads(request.data.decode("utf-8"))["prompt"])
        reply = self.replies.pop(0) if self.replies else '{"descriptions": {}}'
        return _Resp(reply)


class _Resp:
    def __init__(self, text):
        self._text = text

    def read(self):
        return json.dumps({"response": self._text, "prompt_eval_count": 50,
                           "eval_count": 20}).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _client(stub):
    import src.llm.client as mod

    mod.urllib.request.urlopen = stub
    return LLMClient(model="t", model_digest="d", cache=None)


@pytest.fixture(autouse=True)
def _restore():
    original = client_mod.urllib.request.urlopen
    yield
    client_mod.urllib.request.urlopen = original


def test_enrichment_adds_descriptions_for_declared_names():
    stub = _Stub([
        '{"descriptions": {"alarm_set": "create an alarm", "alarm_remove": "delete an alarm"}}',
        '{"descriptions": {"time": "a clock time as written"}}',
    ])
    result = Analyzer(client=_client(stub)).analyze(spec(), POOL)

    assert result.ok
    assert result.spec.enriched is True
    assert len(stub.prompts) == 2, "two enrichment calls: intents, then entity types"
    assert result.described_intents == 2
    assert result.described_entities == 1
    assert dict(result.spec.describe_intents())["alarm_set"] == "create an alarm"


def test_enrichment_cannot_add_an_intent_the_project_does_not_declare():
    stub = _Stub([
        '{"descriptions": {"alarm_set": "create an alarm", "iot_coffee": "brew coffee"}}',
        '{"descriptions": {"time": "a clock time"}}',
    ])
    result = Analyzer(client=_client(stub)).analyze(spec(), POOL)

    assert result.spec.intent_names == ["alarm_set", "alarm_remove"], "inventory unchanged"
    assert "enrichment_named_unknown_fields" in kinds(result.findings)
    assert "iot_coffee" in [
        f.message for f in result.findings if f.kind == "enrichment_named_unknown_fields"
    ][0]


def test_enrichment_cannot_rename_or_remove_a_declared_name():
    stub = _Stub(['{"descriptions": {"alarm_set": "create an alarm"}}',
                  '{"descriptions": {}}'])
    result = Analyzer(client=_client(stub)).analyze(spec(), POOL)

    assert result.spec.intent_names == ["alarm_set", "alarm_remove"]
    assert result.spec.entity_type_names == ["time"]


def test_a_name_the_model_failed_to_describe_keeps_no_description():
    stub = _Stub(['{"descriptions": {"alarm_set": "create an alarm"}}',
                  '{"descriptions": {}}'])
    result = Analyzer(client=_client(stub)).analyze(spec(), POOL)

    descriptions = dict(result.spec.describe_intents())
    assert descriptions["alarm_remove"] is None, "never an invented description"
    assert "enrichment_incomplete" in kinds(result.findings)


def test_unparseable_enrichment_is_reported_and_leaves_the_spec_usable():
    stub = _Stub(["I think these are alarms.", '{"descriptions": {"time": "a clock time"}}'])
    result = Analyzer(client=_client(stub)).analyze(spec(), POOL)

    assert result.ok, "a failed enrichment is a gap, not a contradiction"
    assert "enrichment_unparseable" in kinds(result.findings)
    assert result.described_intents == 0
    assert result.described_entities == 1


def test_a_failed_enrichment_call_is_reported():
    def boom(request, timeout=None):  # noqa: ARG001
        raise TimeoutError("read timed out")

    client_mod.urllib.request.urlopen = boom
    result = Analyzer(client=LLMClient(model="t", cache=None)).analyze(spec(), POOL)

    assert "enrichment_call_failed" in kinds(result.findings)
    assert result.ok


def test_a_fenced_json_reply_is_still_read():
    stub = _Stub(['```json\n{"descriptions": {"alarm_set": "create an alarm"}}\n```',
                  '{"descriptions": {}}'])
    result = Analyzer(client=_client(stub)).analyze(spec(), POOL)

    assert result.described_intents == 1


def test_enrichment_prompts_contain_the_frozen_description_and_the_names():
    stub = _Stub(['{"descriptions": {}}', '{"descriptions": {}}'])
    Analyzer(client=_client(stub)).analyze(spec(), POOL)

    assert "sets and cancels alarms" in stub.prompts[0]
    assert "alarm_set" in stub.prompts[0]
    assert "time" in stub.prompts[1]


def test_the_result_records_its_design_cost_and_findings():
    stub = _Stub(['{"descriptions": {"alarm_set": "x", "alarm_remove": "y"}}',
                  '{"descriptions": {"time": "z"}}'])
    record = Analyzer(client=_client(stub)).analyze(spec(), POOL).as_dict()

    assert record["ok"] is True
    assert record["enriched"] is True
    assert record["design_cost"]["logical_calls"] == 2
    assert record["described_intents"] == 2
    assert isinstance(record["findings"], list)
