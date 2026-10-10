"""The span-location rule (PROJECT_PLAN.md section 5).

LLMs return entity *strings*, not character offsets. This module converts them
to spans deterministically, and it is the only place that conversion happens:
every LLM system uses it, so no system can gain an advantage from a kinder
matching rule.

The rule, exactly as the plan states it:

1. Search for the exact returned string in the original request text
   (case-sensitive first, then case-insensitive).
2. If it occurs more than once, take the first occurrence not already assigned
   to another predicted entity, scanning left to right.
3. If it is not found, the entity is **unsupported**: it counts as a false
   positive for span F1 and in the unsupported-extraction numerator. It is
   never fuzzy-matched into a span.
4. Strip only leading and trailing whitespace and surrounding quotes before
   matching. No other normalisation.

A wrong entity *type* on a correctly located span is still supported by the
text; entity F1 catches that error, not this rule.
"""

from __future__ import annotations

from dataclasses import dataclass

# Quote characters stripped from the ends of a returned string (rule step 4).
QUOTES = "\"'`“”‘’"


@dataclass(frozen=True)
class LocatedEntity:
    """One predicted entity after span location.

    ``start`` and ``end`` are None exactly when ``supported`` is False.
    """

    type: str
    text: str
    start: int | None
    end: int | None
    supported: bool
    case_insensitive: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "type": self.type,
            "text": self.text,
            "start": self.start,
            "end": self.end,
            "supported": self.supported,
            "case_insensitive": self.case_insensitive,
        }


def clean_returned_text(text: str) -> str:
    """Rule step 4: strip whitespace and surrounding quotes, nothing else."""
    cleaned = text.strip()
    while len(cleaned) >= 2 and cleaned[0] in QUOTES and cleaned[-1] in QUOTES:
        cleaned = cleaned[1:-1].strip()
    # A string that is only quotes collapses to empty, which is unsupported.
    return cleaned.strip(QUOTES).strip() if len(cleaned) == 1 and cleaned in QUOTES else cleaned


def _occurrences(haystack: str, needle: str) -> list[int]:
    """Every start index of ``needle`` in ``haystack``, left to right."""
    found: list[int] = []
    start = haystack.find(needle)
    while start != -1:
        found.append(start)
        start = haystack.find(needle, start + 1)
    return found


def locate_entities(
    utterance: str, predicted: list[tuple[str, str]] | list[dict]
) -> list[LocatedEntity]:
    """Locate each predicted (type, text) pair in ``utterance``.

    Predictions are processed in the order the model returned them. Each
    located entity claims its character range, so a later entity with the same
    text takes the next unclaimed occurrence (rule step 2).
    """
    pairs: list[tuple[str, str]] = []
    for item in predicted:
        if isinstance(item, dict):
            pairs.append((str(item.get("type", "")), str(item.get("text", ""))))
        else:
            pairs.append((str(item[0]), str(item[1])))

    lowered = utterance.lower()
    claimed: list[tuple[int, int]] = []
    located: list[LocatedEntity] = []

    for entity_type, raw_text in pairs:
        text = clean_returned_text(raw_text)
        if not text:
            # An empty or quote-only string locates nothing and is unsupported.
            located.append(LocatedEntity(entity_type, text, None, None, False))
            continue

        placed = False
        # Case-sensitive first, then case-insensitive (rule step 1).
        for insensitive in (False, True):
            if insensitive:
                starts = _occurrences(lowered, text.lower())
            else:
                starts = _occurrences(utterance, text)
            for start in starts:
                end = start + len(text)
                if any(start < c_end and c_start < end for c_start, c_end in claimed):
                    continue  # already assigned to another predicted entity
                claimed.append((start, end))
                located.append(
                    LocatedEntity(
                        type=entity_type,
                        # The span's actual text, so a case-insensitive match
                        # reports what the utterance says, not what the model said.
                        text=utterance[start:end],
                        start=start,
                        end=end,
                        supported=True,
                        case_insensitive=insensitive,
                    )
                )
                placed = True
                break
            if placed:
                break

        if not placed:
            # Rule step 3: unsupported. Never fuzzy-matched.
            located.append(LocatedEntity(entity_type, text, None, None, False))

    return located
