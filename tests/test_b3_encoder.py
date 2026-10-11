"""Checks on B3's label scheme and BIO decoding (part of G5).

These need neither torch nor transformers: the module imports them lazily, so
the pure logic is testable on its own. Decoding is where entity errors would
hide, because a wrong merge produces a plausible-looking but wrong span.
"""

import pytest

from src.baselines.b3_encoder import B3Hyperparameters, bio_labels, decode_spans


def test_bio_labels_cover_every_declared_type():
    labels = bio_labels(["time", "date"])

    assert labels == ["O", "B-time", "I-time", "B-date", "I-date"]


def test_bio_labels_start_with_the_outside_tag():
    assert bio_labels([])[0] == "O"
    assert len(bio_labels(["a", "b", "c"])) == 7


# Offsets for "wake me at six am" with a plausible tokenization.
UTT = "wake me at six am"
OFFSETS = [[0, 0], [0, 4], [5, 7], [8, 10], [11, 14], [15, 17], [0, 0]]


def test_a_single_token_entity_is_decoded():
    tags = ["O", "O", "O", "O", "B-time", "O", "O"]

    assert decode_spans(UTT, OFFSETS, tags) == [{"type": "time", "text": "six"}]


def test_a_multi_token_entity_is_merged():
    tags = ["O", "O", "O", "O", "B-time", "I-time", "O"]

    assert decode_spans(UTT, OFFSETS, tags) == [{"type": "time", "text": "six am"}]


def test_no_entity_tags_yields_nothing():
    assert decode_spans(UTT, OFFSETS, ["O"] * 7) == []


def test_two_separate_entities_stay_separate():
    utt = "alarm friday at six"
    offsets = [[0, 0], [0, 5], [6, 12], [13, 15], [16, 19], [0, 0]]
    tags = ["O", "O", "B-date", "O", "B-time", "O"]

    assert decode_spans(utt, offsets, tags) == [
        {"type": "date", "text": "friday"},
        {"type": "time", "text": "six"},
    ]


def test_a_b_tag_starts_a_new_entity_even_next_to_the_same_type():
    """Two adjacent same-type entities must not be merged into one."""
    utt = "six am seven pm"
    offsets = [[0, 0], [0, 3], [4, 6], [7, 12], [13, 15], [0, 0]]
    tags = ["O", "B-time", "I-time", "B-time", "I-time", "O"]
    decoded = decode_spans(utt, offsets, tags)

    assert len(decoded) == 2
    assert decoded[0]["text"] == "six am"
    assert decoded[1]["text"] == "seven pm"


def test_an_i_tag_of_a_different_type_starts_a_new_entity():
    """A type change mid-entity is a boundary, not a silent continuation."""
    utt = "six friday"
    offsets = [[0, 0], [0, 3], [4, 10], [0, 0]]
    tags = ["O", "B-time", "I-date", "O"]
    decoded = decode_spans(utt, offsets, tags)

    assert [d["type"] for d in decoded] == ["time", "date"]


def test_an_orphan_i_tag_still_produces_an_entity():
    """A model can emit I- without B-; dropping it would hide a prediction."""
    utt = "six am"
    offsets = [[0, 0], [0, 3], [4, 6], [0, 0]]
    tags = ["O", "I-time", "I-time", "O"]

    assert decode_spans(utt, offsets, tags) == [{"type": "time", "text": "six am"}]


def test_special_tokens_are_skipped():
    tags = ["B-time", "O", "O", "O", "B-time", "O", "B-date"]
    decoded = decode_spans(UTT, OFFSETS, tags)

    assert decoded == [{"type": "time", "text": "six"}], (
        "tags on zero-width special tokens must not become entities"
    )


def test_decoded_text_is_always_a_substring_of_the_utterance():
    """This is what lets B3 go through the shared span rule unchanged."""
    tags = ["O", "B-time", "I-time", "I-time", "I-time", "I-time", "O"]

    for entity in decode_spans(UTT, OFFSETS, tags):
        assert entity["text"] in UTT


def test_a_whitespace_only_span_is_dropped():
    utt = "a  b"
    offsets = [[0, 0], [1, 3], [0, 0]]

    assert decode_spans(utt, offsets, ["O", "B-time", "O"]) == []


def test_hyphenated_entity_types_survive_the_tag_round_trip():
    """partition('-') must not split a type containing a hyphen's prefix."""
    labels = bio_labels(["house_place"])

    assert labels == ["O", "B-house_place", "I-house_place"]
    utt = "in the kitchen"
    offsets = [[0, 0], [0, 2], [3, 6], [7, 14], [0, 0]]
    decoded = decode_spans(utt, offsets, ["O", "O", "O", "B-house_place", "O"])

    assert decoded == [{"type": "house_place", "text": "kitchen"}]


def test_hyperparameters_record_everything_needed_to_reproduce():
    record = B3Hyperparameters().as_dict()

    for field in ("model_name", "learning_rate", "batch_size", "max_length",
                  "epochs_kshot", "epochs_full", "seed"):
        assert field in record
    assert record["model_name"] == "xlm-roberta-base"


def test_training_on_out_of_scope_examples_is_refused():
    """No system here trains on out-of-scope examples, B3 included."""
    pytest.importorskip("torch")
    pytest.importorskip("transformers")
    from src.baselines.b3_encoder import B3Trainer

    trainer = B3Trainer(intents=["alarm_set"], entity_types=["time"])
    with pytest.raises(ValueError, match="never be trained on out-of-scope"):
        trainer.fit(
            [{"case_id": "x", "utt": "news please", "true_intent": "news_query",
              "in_scope": False, "entities": []}],
            epochs=1,
        )
