"""G2 checks on MASSIVE annotation parsing and gold span conversion."""

import pytest

from src.evaluation.massive import (
    AnnotationMismatchError,
    parse_annotation,
    slot_types,
    strip_annotation,
)


def test_single_slot_offsets_are_exact():
    utt = "wake me up at five am this week"
    annot = "wake me up at [time : five am] [date : this week]"
    entities = parse_annotation(utt, annot)

    assert [(e.type, e.text) for e in entities] == [("time", "five am"), ("date", "this week")]
    assert utt[entities[0].start : entities[0].end] == "five am"
    assert utt[entities[1].start : entities[1].end] == "this week"


def test_utterance_without_slots_yields_nothing():
    assert parse_annotation("tell me a joke", "tell me a joke") == []


def test_slot_at_the_start_and_at_the_end():
    utt = "monday set an alarm for six"
    annot = "[date : monday] set an alarm for [time : six]"
    entities = parse_annotation(utt, annot)

    assert entities[0].start == 0
    assert entities[-1].end == len(utt)


def test_repeated_value_gets_its_own_occurrence():
    utt = "move the six alarm to six thirty"
    annot = "move the [time : six] alarm to [time : six thirty]"
    entities = parse_annotation(utt, annot)

    assert entities[0].start == 9
    assert entities[1].start == 22
    assert utt[entities[1].start : entities[1].end] == "six thirty"


def test_adjacent_slots_do_not_overlap():
    utt = "alarm for friday morning"
    annot = "alarm for [date : friday] [timeofday : morning]"
    entities = parse_annotation(utt, annot)

    assert entities[0].end < entities[1].start


def test_mismatched_annotation_is_rejected_not_guessed():
    with pytest.raises(AnnotationMismatchError):
        parse_annotation("wake me at five", "wake me at [time : six]")


def test_strip_annotation_recovers_the_utterance():
    annot = "turn the [house_place : kitchen] light [color_type : blue]"
    assert strip_annotation(annot) == "turn the kitchen light blue"


def test_slot_types_are_listed():
    annot = "alarm at [time : six] on [date : friday]"
    assert slot_types(annot) == {"time", "date"}


def test_whole_dataset_converts_without_a_single_mismatch():
    """The integrity check the plan requires at G2, run over all en-US records."""
    import json
    from pathlib import Path

    source = Path("data/raw/1.1/data/en-US.jsonl")
    if not source.exists():
        pytest.skip("MASSIVE en-US not downloaded")

    checked = 0
    with open(source, encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            parse_annotation(row["utt"], row["annot_utt"])  # raises on mismatch
            checked += 1

    assert checked == 16521
