"""G3 checks on the runtime output contract."""

from src.evaluation.output_schema import parse_output, repair_instruction

LABELS = ["alarm_set", "alarm_query"]
TYPES = ["time", "date"]


def parse(raw):
    return parse_output(raw, labels=LABELS, entity_types=TYPES)


def test_a_valid_response_parses():
    parsed = parse('{"intent": "alarm_set", "entities": [{"type": "time", "text": "six am"}]}')

    assert parsed.status == "ok"
    assert parsed.schema_valid
    assert parsed.intent == "alarm_set"
    assert parsed.entities == [{"type": "time", "text": "six am"}]
    assert parsed.errors == []


def test_an_empty_entity_list_is_valid():
    parsed = parse('{"intent": "alarm_query", "entities": []}')

    assert parsed.schema_valid
    assert parsed.entities == []


def test_an_absent_entity_list_is_an_empty_list_not_a_guess():
    parsed = parse('{"intent": "alarm_query"}')

    assert parsed.schema_valid
    assert parsed.entities == []


def test_the_out_of_scope_label_becomes_an_oos_status():
    parsed = parse('{"intent": "none_of_the_above", "entities": []}')

    assert parsed.status == "oos"
    assert parsed.schema_valid


def test_unparseable_text_is_invalid_with_no_asserted_answer():
    parsed = parse("I think this is an alarm request.")

    assert parsed.status == "invalid"
    assert parsed.schema_valid is False
    assert parsed.intent is None
    assert parsed.entities == []
    assert "unparseable JSON" in parsed.errors[0]


def test_an_empty_response_is_invalid():
    parsed = parse("   ")

    assert parsed.status == "invalid"
    assert parsed.errors == ["empty response"]


def test_a_json_array_is_invalid():
    parsed = parse('["alarm_set"]')

    assert parsed.status == "invalid"
    assert "not an object" in parsed.errors[0]


def test_a_missing_intent_is_invalid():
    parsed = parse('{"entities": []}')

    assert parsed.status == "invalid"
    assert parsed.errors == ["missing or non-string intent"]


def test_a_code_fence_is_removed_without_changing_the_json():
    parsed = parse('```json\n{"intent": "alarm_set", "entities": []}\n```')

    assert parsed.status == "ok"
    assert parsed.schema_valid
    assert parsed.intent == "alarm_set"


def test_an_undeclared_intent_fails_the_schema_but_still_asserts_its_label():
    parsed = parse('{"intent": "iot_coffee", "entities": []}')

    assert parsed.status == "ok", "this is a contract violation, not a runtime failure"
    assert parsed.schema_valid is False
    assert parsed.intent == "iot_coffee", "kept so the scorer can record an invented label"
    assert "not a declared label" in parsed.errors[0]


def test_an_undeclared_entity_type_fails_the_schema_and_is_kept():
    parsed = parse('{"intent": "alarm_set", "entities": [{"type": "color", "text": "blue"}]}')

    assert parsed.schema_valid is False
    assert parsed.entities == [{"type": "color", "text": "blue"}], "never silently dropped"
    assert any("not declared" in e for e in parsed.errors)


def test_a_non_list_entities_field_fails_the_schema():
    parsed = parse('{"intent": "alarm_set", "entities": "six am"}')

    assert parsed.schema_valid is False
    assert parsed.entities == []
    assert any("not a list" in e for e in parsed.errors)


def test_a_malformed_entity_item_is_reported_not_dropped_silently():
    parsed = parse('{"intent": "alarm_set", "entities": [{"type": "time"}, "six am"]}')

    assert parsed.schema_valid is False
    assert any("non-string text" in e for e in parsed.errors)
    assert any("not an object" in e for e in parsed.errors)
    assert parsed.entities == [{"type": "time", "text": ""}]


def test_extra_fields_fail_the_schema():
    parsed = parse('{"intent": "alarm_set", "entities": [], "confidence": 0.9}')

    assert parsed.schema_valid is False
    assert any("unexpected field" in e for e in parsed.errors)


def test_as_prediction_carries_validity_and_retries():
    parsed = parse('{"intent": "alarm_set", "entities": []}')
    prediction = parsed.as_prediction("c1", retries=1)

    assert prediction.case_id == "c1"
    assert prediction.status == "ok"
    assert prediction.schema_valid_raw is True
    assert prediction.schema_valid_final is True
    assert prediction.retries == 1
    assert prediction.error is None


def test_an_invalid_response_becomes_a_prediction_carrying_its_error():
    prediction = parse("not json").as_prediction("c1")

    assert prediction.status == "invalid"
    assert prediction.schema_valid_final is False
    assert prediction.error and "unparseable" in prediction.error


def test_the_repair_instruction_names_the_actual_problem_and_the_contract():
    parsed = parse('{"intent": "iot_coffee", "entities": []}')
    text = repair_instruction(parsed, LABELS, TYPES)

    assert "not a declared label" in text
    assert "alarm_set" in text and "none_of_the_above" in text
    assert "time" in text and "date" in text
