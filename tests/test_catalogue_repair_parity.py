"""Repair parity across extraction strategies (G4 follow-up).

Found by the G4 catalogue check on real P1 data: a two-stage configuration
returned invalid output at stage one and was recorded as invalid *without* a
repair attempt, while single-call configurations got one. That would have made
two-stage strategies look worse on schema validity for a reason unrelated to
the strategy, biasing the catalogue comparison.

Every strategy must get the same repair allowance: exactly one retry, counted.
"""

import json

import pytest

from src.analyzer.spec import Constraints, EntitySpec, IntentSpec, ProjectSpec
from src.llm import client as client_mod
from src.llm.client import LLMClient
from src.pipelines.catalogue import ConfigRunner, get_config
from src.pipelines.examples import ExampleSelector

POOL = [
    {"case_id": "k1", "utt": "wake me up at six am", "true_intent": "alarm_set",
     "in_scope": True, "entities": [{"type": "time", "text": "six am", "start": 14, "end": 20}]},
    {"case_id": "k2", "utt": "what alarms are set", "true_intent": "alarm_query",
     "in_scope": True, "entities": []},
]
CASE = {"case_id": "d1", "utt": "set an alarm for five am", "true_intent": "alarm_set",
        "in_scope": True,
        "entities": [{"type": "time", "text": "five am", "start": 17, "end": 24}]}

SPEC = ProjectSpec(
    project_id="PT", name="Test", description_text="t",
    intents=[IntentSpec("alarm_set"), IntentSpec("alarm_query")],
    entity_types=[EntitySpec("time")],
    slots_by_intent={"alarm_set": ["time"], "alarm_query": []},
    constraints=Constraints(),
)


class _Stub:
    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def __call__(self, request, timeout=None):  # noqa: ARG002
        self.prompts.append(json.loads(request.data.decode("utf-8"))["prompt"])
        reply = self.replies.pop(0) if self.replies else '{"intent": "alarm_set"}'
        return _Resp(reply)


class _Resp:
    def __init__(self, text):
        self._text = text

    def read(self):
        return json.dumps({"response": self._text, "prompt_eval_count": 100,
                           "eval_count": 10}).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def runner(monkeypatch, config_id, replies, threshold=None):
    stub = _Stub(replies)
    monkeypatch.setattr(client_mod.urllib.request, "urlopen", stub)
    return ConfigRunner(
        config=get_config(config_id), spec=SPEC,
        client=LLMClient(model="t", model_digest="d", cache=None),
        selector=ExampleSelector(POOL), oos_threshold=threshold,
    ), stub


# The exact failure seen on real data: stage one replies with no intent field.
STAGE_ONE_BROKEN = '{"entities": []}'


def test_two_stage_repairs_a_broken_intent_stage(monkeypatch):
    run, stub = runner(
        monkeypatch, "twostage-fixed-tfidf",
        [STAGE_ONE_BROKEN, '{"intent": "alarm_set"}',
         '{"entities": [{"type": "time", "text": "five am"}]}'],
        threshold=0.0,
    )
    outcome = run.run_case(CASE)

    assert len(stub.prompts) == 3, "broken stage one, its repair, then the entity stage"
    assert outcome.repaired
    assert outcome.prediction.status == "ok"
    assert outcome.prediction.intent == "alarm_set"
    assert outcome.prediction.schema_valid_raw is False
    assert outcome.prediction.schema_valid_final is True


def test_the_stage_one_repair_asks_only_for_an_intent(monkeypatch):
    run, stub = runner(
        monkeypatch, "twostage-fixed-tfidf",
        [STAGE_ONE_BROKEN, '{"intent": "alarm_set"}', '{"entities": []}'],
        threshold=0.0,
    )
    run.run_case(CASE)
    repair = stub.prompts[1]

    assert "rejected" in repair
    assert '"intent"' in repair
    assert '"entities"' not in repair.split("rejected")[1], (
        "the stage-one repair must not ask for entities; that is stage two's job"
    )


def test_a_tfidf_two_stage_repair_does_not_offer_the_out_of_scope_label(monkeypatch):
    """The repair must offer exactly what the original prompt offered."""
    run, stub = runner(
        monkeypatch, "twostage-fixed-tfidf",
        [STAGE_ONE_BROKEN, '{"intent": "alarm_set"}', '{"entities": []}'],
        threshold=0.0,
    )
    run.run_case(CASE)

    assert "none_of_the_above" not in stub.prompts[1]


def test_an_llm_label_two_stage_repair_does_offer_the_out_of_scope_label(monkeypatch):
    run, stub = runner(
        monkeypatch, "twostage-fixed-llm",
        [STAGE_ONE_BROKEN, '{"intent": "none_of_the_above"}'],
    )
    run.run_case(CASE)

    assert "none_of_the_above" in stub.prompts[1]


def test_a_failed_stage_one_repair_still_ends_as_invalid(monkeypatch):
    run, stub = runner(
        monkeypatch, "twostage-fixed-llm", [STAGE_ONE_BROKEN, STAGE_ONE_BROKEN],
    )
    outcome = run.run_case(CASE)

    assert len(stub.prompts) == 2, "exactly one repair, never a second"
    assert outcome.prediction.status == "invalid"
    assert outcome.prediction.schema_valid_final is False


def test_the_stage_one_repair_is_counted_as_a_call(monkeypatch):
    run, _ = runner(
        monkeypatch, "twostage-fixed-llm",
        [STAGE_ONE_BROKEN, '{"intent": "alarm_set"}', '{"entities": []}'],
    )
    outcome = run.run_case(CASE)

    # stage one + repair + stage two
    assert outcome.logical_calls == 3
    assert run.client.counter.retries == 1


def test_disabling_repair_disables_it_for_two_stage_too(monkeypatch):
    stub = _Stub([STAGE_ONE_BROKEN])
    monkeypatch.setattr(client_mod.urllib.request, "urlopen", stub)
    run = ConfigRunner(
        config=get_config("twostage-fixed-llm"), spec=SPEC,
        client=LLMClient(model="t", cache=None), selector=ExampleSelector(POOL),
        allow_repair=False,
    )
    outcome = run.run_case(CASE)

    assert len(stub.prompts) == 1
    assert outcome.repaired is False
    assert outcome.prediction.status == "invalid"


@pytest.mark.parametrize("config_id", [
    "joint-fixed-llm", "schema-fixed-llm", "twostage-fixed-llm",
])
def test_every_strategy_gets_exactly_one_repair_allowance(config_id):
    """Parity check across all three extraction strategies."""
    import json as _json

    class Counter:
        def __init__(self):
            self.n = 0

        def __call__(self, request, timeout=None):  # noqa: ARG002
            self.n += 1
            return _Resp("not json at all")

    counter = Counter()
    original = client_mod.urllib.request.urlopen
    client_mod.urllib.request.urlopen = counter
    try:
        run = ConfigRunner(
            config=get_config(config_id), spec=SPEC,
            client=LLMClient(model="t", cache=None), selector=ExampleSelector(POOL),
        )
        outcome = run.run_case(CASE)
    finally:
        client_mod.urllib.request.urlopen = original

    assert counter.n == 2, f"{config_id} made {counter.n} calls; expected one call + one repair"
    assert outcome.prediction.status == "invalid"
    del _json
