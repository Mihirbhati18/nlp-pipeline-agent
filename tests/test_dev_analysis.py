"""Checks on the development analysis: error categories and the paired bootstrap."""

import importlib.util
from pathlib import Path

from src.evaluation.scorer import Prediction

_spec = importlib.util.spec_from_file_location(
    "run_dev_analysis", Path(__file__).resolve().parents[1] / "scripts" / "run_dev_analysis.py"
)
analysis = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(analysis)

LABELS = ["alarm_set", "alarm_remove"]


def case(cid, utt, intent, in_scope=True, entities=()):
    return {"case_id": cid, "utt": utt, "true_intent": intent if in_scope else "weather_query",
            "in_scope": in_scope, "entities": list(entities)}


def ent(utt, etype, text):
    start = utt.index(text)
    return {"type": etype, "text": text, "start": start, "end": start + len(text)}


U1 = "set an alarm for five am"
DEV = [
    case("d1", U1, "alarm_set", entities=[ent(U1, "time", "five am")]),
    case("d2", "delete my alarm", "alarm_remove"),
    case("d3", "what is the weather", None, in_scope=False),
    case("d4", "cancel the alarm", "alarm_remove"),
]


def ok(cid, intent, entities=()):
    return Prediction(cid, "ok", intent, list(entities), True, True)


def errors(preds):
    return analysis.classify_errors(DEV, preds)["counts"]


def test_a_perfect_system_has_no_errors():
    preds = [ok("d1", "alarm_set", [{"type": "time", "text": "five am"}]), ok("d2", "alarm_remove"),
             Prediction("d3", "oos", None, [], True, True), ok("d4", "alarm_remove")]
    assert errors(preds) == {}


def test_each_error_kind_is_counted_under_its_own_category():
    preds = [
        ok("d1", "alarm_set", [{"type": "date", "text": "five am"},   # right span, wrong type
                               {"type": "time", "text": "noon"}]),     # not in the request
        Prediction("d2", "oos", None, [], True, True),                  # wrongly rejected
        ok("d3", "alarm_set"),                                          # answered off-topic
        ok("d4", "alarm_set"),                                          # wrong intent
    ]
    counts = errors(preds)
    assert counts["wrong entity type"] == 1
    assert counts["unsupported value (text not in the request)"] == 1
    assert counts["incorrect out-of-scope rejection"] == 1
    assert counts["missed out-of-scope (answered an off-topic request)"] == 1
    assert counts["confused intent"] == 1
    assert "missed entity" not in counts  # the wrong-type span still covers the gold span


def test_boundary_spurious_and_missed_entities_are_told_apart():
    preds = [ok("d1", "alarm_set", [{"type": "time", "text": "five"}]), ok("d2", "alarm_remove",
             [{"type": "time", "text": "my"}]), Prediction("d3", "oos", None, [], True, True),
             ok("d4", "alarm_remove")]
    counts = errors(preds)
    assert counts["wrong entity boundary"] == 1
    assert counts["spurious entity"] == 1
    assert "missed entity" not in counts


def test_a_missing_entity_is_counted_as_missed():
    preds = [ok("d1", "alarm_set"), ok("d2", "alarm_remove"),
             Prediction("d3", "oos", None, [], True, True), ok("d4", "alarm_remove")]
    assert errors(preds) == {"missed entity": 1}


def test_failed_outputs_are_counted_not_skipped():
    preds = [Prediction("d1", "invalid", None, [], False, False, error="bad json"),
             ok("d2", "alarm_remove"), Prediction("d3", "oos", None, [], True, True),
             Prediction("d4", "error", None, [], False, False, error="timeout")]
    counts = errors(preds)
    assert counts["invalid output"] == 1 and counts["error output"] == 1


def test_identical_systems_give_a_zero_difference_and_a_zero_interval():
    preds = [ok("d1", "alarm_set"), ok("d2", "alarm_remove"),
             Prediction("d3", "oos", None, [], True, True), ok("d4", "alarm_set")]
    ci = analysis.paired_bootstrap(DEV, preds, preds, LABELS)
    for key in ("intent_macro_f1", "entity_span_f1"):
        assert ci[key]["difference"] == 0
        assert ci[key]["ci_low"] == 0 and ci[key]["ci_high"] == 0
        assert ci[key]["share_a_better"] == 0


def test_a_strictly_better_system_has_a_positive_difference_inside_its_interval():
    good = [ok("d1", "alarm_set"), ok("d2", "alarm_remove"),
            Prediction("d3", "oos", None, [], True, True), ok("d4", "alarm_remove")]
    bad = [ok("d1", "alarm_remove"), ok("d2", "alarm_set"),
           Prediction("d3", "oos", None, [], True, True), ok("d4", "alarm_set")]
    ci = analysis.paired_bootstrap(DEV, good, bad, LABELS)["intent_macro_f1"]
    assert ci["difference"] > 0
    assert ci["ci_low"] <= ci["difference"] <= ci["ci_high"]
    assert ci["share_a_better"] > 0.9


def test_the_bootstrap_is_reproducible():
    good = [ok("d1", "alarm_set"), ok("d2", "alarm_remove"),
            Prediction("d3", "oos", None, [], True, True), ok("d4", "alarm_set")]
    bad = [ok("d1", "alarm_remove"), ok("d2", "alarm_remove"),
           Prediction("d3", "oos", None, [], True, True), ok("d4", "alarm_set")]
    # Fixed seed, so two runs give exactly the same interval.
    assert analysis.paired_bootstrap(DEV, good, bad, LABELS) == \
        analysis.paired_bootstrap(DEV, good, bad, LABELS)
