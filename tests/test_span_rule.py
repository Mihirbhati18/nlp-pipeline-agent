"""G3 checks on the span-location rule (PROJECT_PLAN.md section 5).

The plan names the cases that must be covered: repeated substring, missing
substring, case difference, and overlapping entities.
"""

from src.evaluation.span_rule import clean_returned_text, locate_entities


def test_exact_match_is_located():
    located = locate_entities("wake me up at five am", [("time", "five am")])

    assert len(located) == 1
    assert located[0].supported
    assert (located[0].start, located[0].end) == (14, 21)
    assert located[0].case_insensitive is False


def test_repeated_substring_takes_the_next_unclaimed_occurrence():
    """Rule step 2: scanning left to right, skipping assigned occurrences."""
    utterance = "move the six alarm to six thirty"
    located = locate_entities(utterance, [("time", "six"), ("time", "six")])

    assert located[0].start == 9
    assert located[1].start == 22, "the second must not reuse the first occurrence"
    assert all(e.supported for e in located)


def test_three_predictions_of_a_twice_occurring_string_leave_one_unsupported():
    utterance = "six and six"
    located = locate_entities(utterance, [("time", "six")] * 3)

    assert [e.supported for e in located] == [True, True, False]
    assert located[0].start == 0
    assert located[1].start == 8


def test_missing_substring_is_unsupported_and_never_fuzzy_matched():
    """Rule step 3."""
    located = locate_entities("turn on the kitchen light", [("house_place", "bedroom")])

    assert located[0].supported is False
    assert located[0].start is None and located[0].end is None
    assert located[0].text == "bedroom", "the model's string is kept for the error record"


def test_a_near_miss_is_still_unsupported():
    """'kitchens' is not in 'kitchen', and must not be snapped to it."""
    located = locate_entities("turn on the kitchen light", [("house_place", "kitchens")])
    assert located[0].supported is False


def test_case_difference_matches_case_insensitively_and_is_flagged():
    """Rule step 1: case-sensitive first, then case-insensitive."""
    located = locate_entities("set an alarm for Friday", [("date", "friday")])

    assert located[0].supported
    assert located[0].case_insensitive is True
    assert located[0].text == "Friday", "the span reports the utterance's own text"
    assert (located[0].start, located[0].end) == (17, 23)


def test_case_sensitive_occurrence_wins_over_an_earlier_case_folded_one():
    utterance = "friday means Friday"
    located = locate_entities(utterance, [("date", "Friday")])

    assert located[0].start == 13, "an exact match is preferred over a case-folded one"


def test_overlapping_entities_cannot_claim_the_same_characters():
    utterance = "set an alarm for five am tomorrow"
    located = locate_entities(utterance, [("time", "five am"), ("timeofday", "am")])

    assert located[0].supported
    # 'am' inside 'five am' is already claimed, and 'am' occurs nowhere else.
    assert located[1].supported is False


def test_a_contained_string_uses_a_free_occurrence_if_one_exists():
    utterance = "am i set for five am"
    located = locate_entities(utterance, [("time", "five am"), ("timeofday", "am")])

    assert located[0].start == 13
    assert located[1].supported
    assert located[1].start == 0, "the unclaimed 'am' at the start is used"


def test_surrounding_quotes_and_whitespace_are_stripped():
    """Rule step 4, and nothing more than that."""
    located = locate_entities("add milk to the list", [("list_name", '  "milk" ')])

    assert located[0].supported
    assert located[0].text == "milk"


def test_no_other_normalisation_happens():
    """Punctuation and inner spacing are not normalised away."""
    assert clean_returned_text("  'six thirty'  ") == "six thirty"
    assert clean_returned_text("six  thirty") == "six  thirty"
    assert clean_returned_text("six thirty.") == "six thirty."

    located = locate_entities("alarm at six thirty", [("time", "six thirty.")])
    assert located[0].supported is False, "a trailing full stop is not stripped"


def test_empty_and_quote_only_strings_are_unsupported():
    located = locate_entities("turn the light on", [("device_type", ""), ("color_type", '""')])

    assert [e.supported for e in located] == [False, False]


def test_entity_type_is_never_altered_by_the_rule():
    """A wrong type on a real span stays located; entity F1 catches the error."""
    located = locate_entities("make the kitchen light blue", [("color_type", "kitchen")])

    assert located[0].supported
    assert located[0].type == "color_type"


def test_dict_and_tuple_inputs_behave_identically():
    utterance = "alarm at six on friday"
    from_tuples = locate_entities(utterance, [("time", "six"), ("date", "friday")])
    from_dicts = locate_entities(
        utterance, [{"type": "time", "text": "six"}, {"type": "date", "text": "friday"}]
    )

    assert [e.as_dict() for e in from_tuples] == [e.as_dict() for e in from_dicts]


def test_malformed_entity_dict_does_not_crash_the_evaluator():
    located = locate_entities("alarm at six", [{"type": "time"}, {"text": "six"}])

    assert located[0].supported is False  # no text
    assert located[1].type == ""  # no type, but the span is still located
    assert located[1].supported
