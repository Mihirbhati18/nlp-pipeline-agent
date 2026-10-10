"""G3 checks on the common scorer.

Every expected number here is computed by hand from the four fixture cases, so
the test fails if the scorer's arithmetic drifts. The plan names the fixtures
that must be covered: perfect, wrong, empty and malformed output.

Fixture (3 in-scope + 1 out-of-scope):

    c1 "wake me up at five am"      alarm_set         time: "five am" (14-21)
    c2 "turn off the kitchen light" iot_hue_lightoff  house_place: "kitchen" (12-19)
    c3 "what alarms do i have"      alarm_query       no entities
    c4 "what is the weather like"   OUT OF SCOPE      no entities
"""

import pytest

from src.evaluation.scorer import Prediction, score

LABELS = ["alarm_query", "alarm_remove", "alarm_set", "iot_hue_lightoff"]

CASES = [
    {
        "case_id": "c1",
        "utt": "wake me up at five am",
        "true_intent": "alarm_set",
        "in_scope": True,
        "entities": [{"type": "time", "text": "five am", "start": 14, "end": 21}],
    },
    {
        "case_id": "c2",
        "utt": "turn off the kitchen light",
        "true_intent": "iot_hue_lightoff",
        "in_scope": True,
        "entities": [{"type": "house_place", "text": "kitchen", "start": 13, "end": 20}],
    },
    {
        "case_id": "c3",
        "utt": "what alarms do i have",
        "true_intent": "alarm_query",
        "in_scope": True,
        "entities": [],
    },
    {
        "case_id": "c4",
        "utt": "what is the weather like",
        "true_intent": "weather_query",
        "in_scope": False,
        "entities": [],
    },
]


def ok(case_id, intent, entities=()):
    return Prediction(
        case_id=case_id,
        status="ok",
        intent=intent,
        entities=[{"type": t, "text": v} for t, v in entities],
        schema_valid_raw=True,
        schema_valid_final=True,
    )


def oos(case_id):
    return Prediction(
        case_id=case_id, status="oos", schema_valid_raw=True, schema_valid_final=True
    )


# -- the fixture spans are correct ------------------------------------


def test_fixture_gold_spans_are_self_consistent():
    for case in CASES:
        for entity in case["entities"]:
            assert case["utt"][entity["start"] : entity["end"]] == entity["text"]


# -- perfect output ----------------------------------------------------


def test_perfect_system_scores_one_everywhere():
    result = score(
        CASES,
        [
            ok("c1", "alarm_set", [("time", "five am")]),
            ok("c2", "iot_hue_lightoff", [("house_place", "kitchen")]),
            ok("c3", "alarm_query"),
            oos("c4"),
        ],
        labels=LABELS,
    )
    p = result["primary"]

    # Macro-F1 averages over all four declared labels. alarm_remove has no
    # gold case and no prediction, so its F1 is 0 and it drags the mean down:
    # (1 + 0 + 1 + 1) / 4.
    assert p["intent_macro_f1"] == pytest.approx(0.75)
    assert p["intent_accuracy_in_scope"] == pytest.approx(1.0)
    assert p["entity_span_f1"] == pytest.approx(1.0)
    assert p["entity_counts"] == {"tp": 2, "fp": 0, "fn": 0}
    assert p["oos_f1"] == pytest.approx(1.0)
    assert p["false_rejection_rate_in_scope"] == pytest.approx(0.0)
    assert p["schema_validity_after_repair"] == pytest.approx(1.0)
    assert p["unsupported_extraction_rate"] == pytest.approx(0.0)
    assert p["unsupported_extraction_counts"] == {"unsupported_items": 0, "predicted_items": 2}
    assert p["runtime_failure_rate"] == pytest.approx(0.0)
    assert result["secondary"]["end_to_end_exact_match"] == pytest.approx(1.0)


def test_macro_f1_is_one_when_averaged_over_only_the_supported_labels():
    """Without a declared label set, the gold labels are used."""
    result = score(
        CASES,
        [
            ok("c1", "alarm_set", [("time", "five am")]),
            ok("c2", "iot_hue_lightoff", [("house_place", "kitchen")]),
            ok("c3", "alarm_query"),
            oos("c4"),
        ],
    )

    assert result["intent_label_set"] == ["alarm_query", "alarm_set", "iot_hue_lightoff"]
    assert result["primary"]["intent_macro_f1"] == pytest.approx(1.0)


# -- wrong output ------------------------------------------------------


def test_wrong_system_scores_zero_and_records_why():
    result = score(
        CASES,
        [
            # wrong intent, and an entity string that is not in the utterance
            ok("c1", "alarm_remove", [("time", "nine pm")]),
            oos("c2"),  # an in-scope request rejected: a false rejection
            ok("c3", "iot_coffee"),  # a label outside the project's inventory
            ok("c4", "alarm_set"),  # missed out-of-scope
        ],
        labels=LABELS,
    )
    p = result["primary"]

    assert p["intent_macro_f1"] == pytest.approx(0.0)
    assert p["intent_accuracy_in_scope"] == pytest.approx(0.0)
    # c1 predicted alarm_remove, a real label: charged as a false positive.
    assert result["per_intent"]["alarm_remove"] == {
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "support": 0,
    }
    # c3 predicted iot_coffee, which the project does not declare.
    assert result["invalid_label_predictions"] == {"iot_coffee": 1}

    # Entities: c1 predicted one unsupported item (false positive) and missed
    # its gold entity; c2 predicted none and missed its gold entity.
    assert p["entity_counts"] == {"tp": 0, "fp": 1, "fn": 2}
    assert p["entity_span_f1"] == pytest.approx(0.0)

    # Out-of-scope: c2 wrongly rejected (fp), c4 wrongly accepted (fn).
    assert p["oos_counts"] == {"tp": 0, "fp": 1, "fn": 1}
    assert p["oos_f1"] == pytest.approx(0.0)
    assert p["false_rejection_rate_in_scope"] == pytest.approx(1 / 3)

    assert p["unsupported_extraction_rate"] == pytest.approx(1.0)
    assert p["unsupported_extraction_counts"] == {"unsupported_items": 1, "predicted_items": 1}
    assert result["secondary"]["unsupported_request_rate"] == pytest.approx(0.25)


# -- empty output ------------------------------------------------------


def test_empty_entity_output_does_not_look_successful():
    """The plan's rule: an empty output must not appear to be a solution.

    Intents are all correct, but no entity is ever predicted. Entity recall
    must stay visible at 0, and the unsupported-extraction rate must be N/A
    (None) rather than a flattering 0.
    """
    result = score(
        CASES,
        [ok("c1", "alarm_set"), ok("c2", "iot_hue_lightoff"), ok("c3", "alarm_query"), oos("c4")],
        labels=LABELS,
    )
    p = result["primary"]

    assert p["intent_macro_f1"] == pytest.approx(0.75)
    assert p["entity_counts"] == {"tp": 0, "fp": 0, "fn": 2}
    assert p["entity_span_recall"] == pytest.approx(0.0)
    assert p["entity_span_f1"] == pytest.approx(0.0)
    assert p["unsupported_extraction_rate"] is None, "N/A, not zero"
    assert p["unsupported_extraction_counts"]["predicted_items"] == 0
    # Two cases needed entities and got none, so exact match is 2 of 4.
    assert result["secondary"]["end_to_end_exact_match"] == pytest.approx(0.5)


# -- malformed and failed output ---------------------------------------


def test_malformed_and_failed_responses_stay_in_every_denominator():
    result = score(
        CASES,
        [
            Prediction("c1", status="invalid", schema_valid_raw=False, schema_valid_final=False),
            Prediction("c2", status="error", error="TimeoutError", schema_valid_final=False),
            # c3 has no prediction at all: a missing response.
            oos("c4"),
        ],
        labels=LABELS,
    )
    p = result["primary"]

    assert result["n_cases"] == 4, "nothing was dropped"
    assert result["missing_responses"] == 1
    assert p["runtime_failure_rate"] == pytest.approx(0.75)
    assert p["runtime_failure_counts"] == {"invalid": 1, "error": 1, "missing": 1, "oos": 1}
    assert p["schema_validity_after_repair"] == pytest.approx(0.25)
    assert p["intent_macro_f1"] == pytest.approx(0.0)
    assert p["oos_f1"] == pytest.approx(1.0), "the one out-of-scope case was handled"
    assert result["secondary"]["end_to_end_exact_match"] == pytest.approx(0.25)


def test_a_failure_is_not_charged_as_a_false_positive_to_any_intent():
    result = score(
        CASES,
        [
            Prediction("c1", status="error", schema_valid_final=False),
            ok("c2", "iot_hue_lightoff", [("house_place", "kitchen")]),
            ok("c3", "alarm_query"),
            oos("c4"),
        ],
        labels=LABELS,
    )

    assert result["per_intent"]["alarm_set"]["recall"] == pytest.approx(0.0)
    for label, row in result["per_intent"].items():
        if label not in ("alarm_set", "alarm_remove"):
            assert row["precision"] == pytest.approx(1.0), label


def test_schema_validity_is_reported_before_and_after_repair():
    result = score(
        CASES,
        [
            Prediction(
                "c1", status="ok", intent="alarm_set",
                entities=[{"type": "time", "text": "five am"}],
                schema_valid_raw=False, schema_valid_final=True, retries=1,
            ),
            ok("c2", "iot_hue_lightoff", [("house_place", "kitchen")]),
            ok("c3", "alarm_query"),
            oos("c4"),
        ],
        labels=LABELS,
    )
    p = result["primary"]

    assert p["schema_validity_before_repair"] == pytest.approx(0.75)
    assert p["schema_validity_after_repair"] == pytest.approx(1.0)
    assert p["retries"] == 1


def test_unexpected_prediction_ids_are_reported_not_ignored():
    result = score(
        CASES,
        [ok("c1", "alarm_set"), ok("c99", "alarm_set")],
        labels=LABELS,
    )

    assert result["unexpected_prediction_ids"] == ["c99"]
    assert result["missing_responses"] == 3


# -- latency -----------------------------------------------------------


def test_latency_comes_only_from_supplied_timing_values():
    result = score(
        CASES,
        [ok("c1", "alarm_set"), ok("c2", "iot_hue_lightoff"), ok("c3", "alarm_query"), oos("c4")],
        labels=LABELS,
        latencies=[1.0, 2.0, 3.0, 4.0, 100.0],
        cold_start_s=12.5,
    )
    p = result["primary"]

    assert p["latency_median_s"] == pytest.approx(3.0)
    assert p["latency_p95_s"] == pytest.approx(80.8)
    assert p["latency_n_timed"] == 5
    assert p["cold_start_s"] == pytest.approx(12.5)


def test_latency_is_none_when_no_timing_run_was_done():
    result = score(CASES, [oos("c4")], labels=LABELS)

    assert result["primary"]["latency_median_s"] is None
    assert result["primary"]["latency_p95_s"] is None
    assert result["primary"]["latency_n_timed"] == 0


def test_design_cost_is_carried_through():
    result = score(
        CASES, [oos("c4")], labels=LABELS,
        design_cost={"logical_calls": 400, "physical_calls": 120, "wall_time_s": 95.0},
    )

    assert result["primary"]["design_cost"]["logical_calls"] == 400
    assert result["primary"]["design_cost"]["physical_calls"] == 120


# -- the span rule is wired into entity scoring ------------------------


def test_case_difference_still_counts_as_a_correct_span():
    cases = [
        {
            "case_id": "x1",
            "utt": "set an alarm for Friday",
            "true_intent": "alarm_set",
            "in_scope": True,
            "entities": [{"type": "date", "text": "Friday", "start": 17, "end": 23}],
        }
    ]
    result = score(cases, [ok("x1", "alarm_set", [("date", "friday")])], labels=["alarm_set"])

    assert result["primary"]["entity_counts"] == {"tp": 1, "fp": 0, "fn": 0}


def test_right_span_but_wrong_type_is_a_false_positive_and_a_miss():
    cases = [
        {
            "case_id": "x1",
            "utt": "make the kitchen light blue",
            "true_intent": "iot_hue_lightchange",
            "in_scope": True,
            "entities": [{"type": "house_place", "text": "kitchen", "start": 9, "end": 16}],
        }
    ]
    result = score(
        cases,
        [ok("x1", "iot_hue_lightchange", [("color_type", "kitchen")])],
        labels=["iot_hue_lightchange"],
    )
    p = result["primary"]

    assert p["entity_counts"] == {"tp": 0, "fp": 1, "fn": 1}
    # The text supports the span, so this is not an unsupported extraction.
    assert p["unsupported_extraction_rate"] == pytest.approx(0.0)
