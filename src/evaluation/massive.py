"""MASSIVE annotation parsing and character-span conversion.

MASSIVE marks slots inline in ``annot_utt``::

    utt:       wake me up at five am this week
    annot_utt: wake me up at [time : five am] [date : this week]

Gold entities must become (type, text, start, end) character spans in the
*original* ``utt``, because the evaluator compares predicted spans against
them (PROJECT_PLAN.md section 5). This module does that conversion and
verifies it: ``parse_annotation`` raises if the reconstructed plain text does
not equal ``utt`` exactly, so a silent misalignment can never become gold data.

The separate rule for converting *LLM-returned strings* into spans lives in
``span_rule.py``; this file only handles the dataset's own annotations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# [type : value] — the value runs to the closing bracket and contains no bracket.
SLOT_PATTERN = re.compile(r"\[(?P<type>[^\[\]:]+?)\s*:\s*(?P<value>[^\[\]]+?)\]")


class AnnotationMismatchError(ValueError):
    """The annotation does not reconstruct the original utterance."""


@dataclass(frozen=True)
class GoldEntity:
    type: str
    text: str
    start: int
    end: int

    def as_dict(self) -> dict[str, object]:
        return {"type": self.type, "text": self.text, "start": self.start, "end": self.end}


def strip_annotation(annot_utt: str) -> str:
    """Return the plain utterance implied by an annotated utterance."""
    return SLOT_PATTERN.sub(lambda m: m.group("value").strip(), annot_utt)


def parse_annotation(utt: str, annot_utt: str) -> list[GoldEntity]:
    """Convert ``annot_utt`` into character spans over ``utt``.

    Raises ``AnnotationMismatchError`` if the annotation's plain text differs
    from ``utt``, which would make every span offset unreliable.
    """
    entities: list[GoldEntity] = []
    plain_parts: list[str] = []
    cursor = 0  # position in the reconstructed plain text
    last = 0  # position in annot_utt

    for match in SLOT_PATTERN.finditer(annot_utt):
        literal = annot_utt[last : match.start()]
        plain_parts.append(literal)
        cursor += len(literal)

        value = match.group("value").strip()
        entities.append(
            GoldEntity(
                type=match.group("type").strip(),
                text=value,
                start=cursor,
                end=cursor + len(value),
            )
        )
        plain_parts.append(value)
        cursor += len(value)
        last = match.end()

    plain_parts.append(annot_utt[last:])
    reconstructed = "".join(plain_parts)

    if reconstructed != utt:
        raise AnnotationMismatchError(
            f"annotation does not reconstruct the utterance\n"
            f"  utt:          {utt!r}\n"
            f"  reconstructed: {reconstructed!r}"
        )

    for entity in entities:
        if utt[entity.start : entity.end] != entity.text:
            raise AnnotationMismatchError(
                f"span {entity.start}:{entity.end} is {utt[entity.start:entity.end]!r}, "
                f"expected {entity.text!r}"
            )

    return entities


def slot_types(annot_utt: str) -> set[str]:
    """The slot types named in one annotation."""
    return {m.group("type").strip() for m in SLOT_PATTERN.finditer(annot_utt)}
