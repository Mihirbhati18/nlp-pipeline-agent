"""The runtime output contract, and parsing raw model text against it.

Shared by every LLM system, so "schema validity" means the same thing for all
of them (PROJECT_PLAN.md section 5).

The contract:

    {"intent": "<a declared intent, or none_of_the_above>",
     "entities": [{"type": "<a declared entity type>", "text": "<exact text>"}]}

Validity rules, and what each violation costs:

- Unparseable text, or a non-object, or a missing/non-string intent: the
  response is **invalid**. It has no intent and no entities, it fails schema
  validity, and it stays in every denominator.
- An intent that is not in the project's declared inventory: the response
  **fails schema validity** but still asserts that label, so the scorer can
  record it under invalid label predictions. It is not a runtime failure.
- An entity whose type is not declared, or whose text is not a string: the
  response fails schema validity, and the entity is kept so that entity
  scoring and the unsupported-extraction rate still see it. Nothing is
  silently dropped.
- Validation never invents a missing value. An absent entity list is an empty
  list, not a guess.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Sequence

from .scorer import OOS_LABEL, STATUS_INVALID, STATUS_OK, STATUS_OOS, Prediction

# Models sometimes wrap JSON in a code fence despite being asked not to.
# Removing the fence is parsing, not repair: the JSON inside is unchanged.
FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


@dataclass
class ParsedOutput:
    status: str
    intent: str | None = None
    entities: list[dict] = field(default_factory=list)
    schema_valid: bool = False
    errors: list[str] = field(default_factory=list)

    def as_prediction(
        self, case_id: str, *, retries: int = 0, fallback_used: bool = False
    ) -> Prediction:
        return Prediction(
            case_id=case_id,
            status=self.status,
            intent=self.intent,
            entities=self.entities,
            schema_valid_raw=self.schema_valid,
            schema_valid_final=self.schema_valid,
            retries=retries,
            fallback_used=fallback_used,
            error="; ".join(self.errors) if self.status == STATUS_INVALID else None,
        )


def _strip_fence(text: str) -> str:
    match = FENCE.match(text or "")
    return match.group(1) if match else (text or "")


def parse_output(
    raw: str,
    *,
    labels: Sequence[str],
    entity_types: Sequence[str],
) -> ParsedOutput:
    """Parse one raw model response against the contract."""
    label_set = set(labels) | {OOS_LABEL}
    type_set = set(entity_types)
    errors: list[str] = []

    text = _strip_fence(raw)
    if not text.strip():
        return ParsedOutput(status=STATUS_INVALID, errors=["empty response"])

    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        return ParsedOutput(status=STATUS_INVALID, errors=[f"unparseable JSON: {exc.msg}"])

    if not isinstance(data, dict):
        return ParsedOutput(
            status=STATUS_INVALID, errors=[f"top level is {type(data).__name__}, not an object"]
        )

    intent = data.get("intent")
    if not isinstance(intent, str) or not intent.strip():
        return ParsedOutput(status=STATUS_INVALID, errors=["missing or non-string intent"])
    intent = intent.strip()

    if intent not in label_set:
        errors.append(f"intent {intent!r} is not a declared label")

    raw_entities = data.get("entities", [])
    entities: list[dict] = []
    if raw_entities is None:
        raw_entities = []
    if not isinstance(raw_entities, list):
        errors.append(f"entities is {type(raw_entities).__name__}, not a list")
        raw_entities = []

    for index, item in enumerate(raw_entities):
        if not isinstance(item, dict):
            errors.append(f"entity {index} is {type(item).__name__}, not an object")
            continue
        entity_type = item.get("type")
        entity_text = item.get("text")
        if not isinstance(entity_type, str):
            errors.append(f"entity {index} has a missing or non-string type")
            entity_type = ""
        if not isinstance(entity_text, str):
            errors.append(f"entity {index} has a missing or non-string text")
            entity_text = ""
        if entity_type and entity_type not in type_set:
            errors.append(f"entity type {entity_type!r} is not declared")
        # Kept either way: entity scoring and the unsupported-extraction rate
        # must see what the model actually produced.
        entities.append({"type": entity_type, "text": entity_text})

    unknown = sorted(set(data) - {"intent", "entities"})
    if unknown:
        errors.append(f"unexpected field(s): {', '.join(unknown)}")

    status = STATUS_OOS if intent == OOS_LABEL else STATUS_OK
    return ParsedOutput(
        status=status,
        intent=intent,
        entities=entities,
        schema_valid=not errors,
        errors=errors,
    )


def repair_instruction(parsed: ParsedOutput, labels: Sequence[str], entity_types: Sequence[str]) -> str:
    """The text appended for one JSON-repair retry.

    A retry is a new model call with its own cache entry and is counted in the
    budget, so repair is attempted at most once per request by the pipelines.
    """
    problems = "; ".join(parsed.errors) or "the reply was not valid JSON"
    return (
        f"Your previous reply was rejected: {problems}.\n"
        f'Reply with JSON only, exactly: {{"intent": "<one of: '
        f'{", ".join([*labels, OOS_LABEL])}>", "entities": [{{"type": "<one of: '
        f'{", ".join(entity_types)}>", "text": "<text copied exactly from the request>"}}]}}\n'
        "Use an empty list if there are no entities. Add no other fields."
    )
