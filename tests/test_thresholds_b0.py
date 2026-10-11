"""G4 checks on threshold tuning and the B0 baseline."""

import pytest

from src.evaluation.scorer import score
from src.evaluation.thresholds import (
    macro_f1_with_oos,
    tune_binary_threshold,
    tune_threshold,
)

# -- threshold tuning --------------------------------------------------


def test_a_perfectly_separable_confidence_finds_a_clean_threshold():
    # In-scope cases are confident, out-of-scope cases are not.
    confidences = [0.9, 0.8, 0.85, 0.2, 0.1]
    predictions = ["a", "a", "b", "a", "b"]
    gold = ["a", "a", "b", "none_of_the_above", "none_of_the_above"]

    choice = tune_threshold(confidences, predictions, gold, ["a", "b"])

    assert 0.2 < choice.threshold <= 0.8
    assert choice.macro_f1 == pytest.approx(1.0)


def test_tuning_prefers_the_lower_threshold_on_a_tie():
    """A tie must not be broken toward rejecting more in-scope requests."""
    confidences = [0.9, 0.8, 0.3, 0.2]
    predictions = ["a", "a", "a", "a"]
    gold = ["a", "a", "none_of_the_above", "none_of_the_above"]

    choice = tune_threshold(confidences, predictions, gold, ["a"])

    assert choice.threshold == pytest.approx(0.8)


def test_tuning_can_choose_to_reject_nothing():
    """With no out-of-scope cases, the best threshold rejects nothing."""
    confidences = [0.4, 0.5, 0.6]
    predictions = ["a", "a", "a"]
    gold = ["a", "a", "a"]

    choice = tune_threshold(confidences, predictions, gold, ["a"])
    rejected = [c < choice.threshold for c in confidences]

    assert not any(rejected)


def test_the_threshold_record_states_it_was_tuned_on_development_data():
    choice = tune_threshold([0.5, 0.1], ["a", "a"], ["a", "none_of_the_above"], ["a"])

    assert choice.as_dict()["tuned_on"] == "development split only"
    assert "dev" in choice.as_dict()["criterion"]


def test_empty_input_does_not_crash_tuning():
    choice = tune_threshold([], [], [], ["a"])

    assert choice.threshold == 0.0
    assert choice.n_candidates == 0


def test_macro_f1_with_oos_weights_every_class_equally():
    # Class 'a' perfect, class 'b' never predicted, out-of-scope perfect.
    gold = ["a", "a", "b", "none_of_the_above"]
    predicted = ["a", "a", "a", "none_of_the_above"]

    # F1: a = 2*2/(2+3)... precision 2/3, recall 1 -> 0.8; b = 0; oos = 1.
    assert macro_f1_with_oos(gold, predicted, ["a", "b"]) == pytest.approx((0.8 + 0.0 + 1.0) / 3)


def test_the_binary_variant_tunes_only_the_in_scope_decision():
    confidences = [0.9, 0.85, 0.2, 0.1]
    in_scope = [True, True, False, False]

    choice = tune_binary_threshold(confidences, in_scope)

    assert 0.2 < choice.threshold <= 0.85
    assert choice.macro_f1 == pytest.approx(1.0)
    assert "binary" in choice.criterion


def test_the_binary_variant_explains_why_it_differs_from_the_macro_rule():
    choice = tune_binary_threshold([0.5, 0.1], [True, False])

    assert "before the model call" in choice.criterion


# -- B0 ----------------------------------------------------------------

POOL = [
    {"case_id": "k1", "utt": "wake me up at six am", "true_intent": "alarm_set", "in_scope": True, "entities": []},
    {"case_id": "k2", "utt": "set an alarm for seven", "true_intent": "alarm_set", "in_scope": True, "entities": []},
    {"case_id": "k3", "utt": "cancel my alarm", "true_intent": "alarm_remove", "in_scope": True, "entities": []},
    {"case_id": "k4", "utt": "delete the alarm for noon", "true_intent": "alarm_remove", "in_scope": True, "entities": []},
    {"case_id": "k5", "utt": "turn off the kitchen light", "true_intent": "iot_hue_lightoff", "in_scope": True, "entities": []},
    {"case_id": "k6", "utt": "lights off in the hall", "true_intent": "iot_hue_lightoff", "in_scope": True, "entities": []},
]

DEV = [
    {"case_id": "d1", "utt": "wake me at six am", "true_intent": "alarm_set", "in_scope": True,
     "entities": [{"type": "time", "text": "six am", "start": 11, "end": 17}]},
    {"case_id": "d2", "utt": "cancel my alarm for noon", "true_intent": "alarm_remove",
     "in_scope": True, "entities": []},
    {"case_id": "d3", "utt": "turn off the kitchen light", "true_intent": "iot_hue_lightoff",
     "in_scope": True, "entities": []},
    {"case_id": "d4", "utt": "who won the world cup in nineteen ninety", "true_intent": "qa_factoid",
     "in_scope": False, "entities": []},
]

LABELS = ["alarm_set", "alarm_remove", "iot_hue_lightoff"]


def fitted():
    from src.baselines.b0_tfidf import B0TfidfClassifier

    classifier = B0TfidfClassifier(labels=LABELS).fit(POOL)
    classifier.tune(DEV)
    return classifier


def test_b0_makes_no_model_calls():
    assert fitted().config()["model_calls"] == 0


def test_b0_predicts_an_intent_for_every_case():
    predictions = fitted().predict(DEV)

    assert len(predictions) == len(DEV)
    assert {p.case_id for p in predictions} == {c["case_id"] for c in DEV}


def test_b0_extracts_no_entities_and_says_so():
    classifier = fitted()

    assert classifier.config()["extracts_entities"] is False
    assert all(p.entities == [] for p in classifier.predict(DEV))


def test_b0_output_always_satisfies_the_contract():
    """Its output is constructed, not generated, so it cannot be malformed."""
    assert all(p.schema_valid_final for p in fitted().predict(DEV))


def test_b0_entity_f1_is_zero_and_unsupported_rate_is_not_applicable():
    classifier = fitted()
    result = score(DEV, classifier.predict(DEV), labels=LABELS)
    p = result["primary"]

    assert p["entity_span_f1"] == pytest.approx(0.0)
    assert p["entity_counts"]["fn"] == 1, "the missed gold entity stays visible"
    assert p["unsupported_extraction_rate"] is None
    assert p["schema_validity_after_repair"] == pytest.approx(1.0)


def test_b0_refuses_to_predict_before_its_threshold_is_tuned():
    from src.baselines.b0_tfidf import B0TfidfClassifier

    classifier = B0TfidfClassifier(labels=LABELS).fit(POOL)

    with pytest.raises(ValueError, match="before predicting"):
        classifier.predict(DEV)


def test_b0_is_deterministic():
    first = [(p.case_id, p.status, p.intent) for p in fitted().predict(DEV)]
    second = [(p.case_id, p.status, p.intent) for p in fitted().predict(DEV)]

    assert first == second


def test_b0_records_its_threshold_and_criterion_in_its_config():
    config = fitted().config()

    assert config["threshold"]["tuned_on"] == "development split only"
    assert config["threshold"]["threshold"] >= 0.0
