"""The Project Analyzer (PROJECT_PLAN.md section 6).

    Input: frozen project description, supported schema, labelled examples and
    constraints. Output: validated ProjectSpec with intent definitions, entity
    types, required/optional fields and constraint values. Authoritative
    supplied schema fields take precedence over inferred fields. Flag
    contradictions or missing information rather than filling in unsupported
    assumptions.

Two separable parts, deliberately:

1. **Validation** - no model involved. Checks the authoritative inputs for
   duplicates, contradictions and gaps, and refuses to proceed on a genuine
   conflict. This is what makes the Analyzer trustworthy rather than merely
   verbose.
2. **Enrichment** - the only part that uses a model. It writes one-line
   descriptions for the declared intents and entity types, which the
   schema-guided catalogue configurations then put in their prompts.

The enrichment can only *describe* what the manifest already declares. It can
never add, rename or remove an intent or entity type: a description for an
unknown name is discarded and reported, and a declared name the model failed
to describe is reported as missing rather than invented. That is what
"authoritative supplied fields take precedence" means in code.

This split is also what makes the no-Analyzer ablation meaningful: the ablation
runs on the bare specification, A1 on the enriched one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Sequence

from ..llm.client import LLMClient
from .spec import OOS_LABEL, ProjectSpec

# The Architect's planning budget is a handful of calls per project
# (plan section 2A), so enrichment takes two: intents, then entity types.
ENRICHMENT_CALLS = 2


@dataclass
class Finding:
    """One thing the Analyzer noticed. ``blocking`` stops the pipeline."""

    kind: str
    message: str
    blocking: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "message": self.message, "blocking": self.blocking}


@dataclass
class AnalysisResult:
    spec: ProjectSpec
    findings: list[Finding] = field(default_factory=list)
    logical_calls: int = 0
    physical_calls: int = 0
    described_intents: int = 0
    described_entities: int = 0

    @property
    def blocking(self) -> list[Finding]:
        return [f for f in self.findings if f.blocking]

    @property
    def ok(self) -> bool:
        return not self.blocking

    def as_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.spec.project_id,
            "ok": self.ok,
            "enriched": self.spec.enriched,
            "n_intents": len(self.spec.intents),
            "n_entity_types": len(self.spec.entity_types),
            "described_intents": self.described_intents,
            "described_entities": self.described_entities,
            "findings": [f.as_dict() for f in self.findings],
            "design_cost": {
                "logical_calls": self.logical_calls,
                "physical_calls": self.physical_calls,
            },
        }


# -- part one: validation, no model ------------------------------------


def validate(spec: ProjectSpec, pool: Sequence[dict]) -> list[Finding]:
    """Check the authoritative inputs. Blocking findings stop the pipeline."""
    findings: list[Finding] = []

    if not spec.intents:
        findings.append(Finding("no_intents", "the project declares no intents", True))

    names = [i.name for i in spec.intents]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        findings.append(
            Finding("duplicate_intents", f"intent declared more than once: {duplicates}", True)
        )

    if OOS_LABEL in names:
        findings.append(
            Finding(
                "oos_label_in_inventory",
                f"{OOS_LABEL!r} is the reserved out-of-scope label and must not be "
                "declared as a supported intent",
                True,
            )
        )

    type_names = [e.name for e in spec.entity_types]
    duplicate_types = sorted({n for n in type_names if type_names.count(n) > 1})
    if duplicate_types:
        findings.append(
            Finding(
                "duplicate_entity_types",
                f"entity type declared more than once: {duplicate_types}",
                True,
            )
        )

    if not spec.description_text.strip():
        findings.append(
            Finding("no_description", "the project description is empty", True)
        )

    constraints = spec.constraints
    if constraints.max_p95_latency_s is not None and constraints.max_p95_latency_s <= 0:
        findings.append(
            Finding(
                "impossible_latency_constraint",
                f"max_p95_latency_s is {constraints.max_p95_latency_s}, which no "
                "pipeline can satisfy",
                True,
            )
        )
    if constraints.min_schema_validity is not None and not (
        0.0 <= constraints.min_schema_validity <= 1.0
    ):
        findings.append(
            Finding(
                "impossible_schema_constraint",
                f"min_schema_validity is {constraints.min_schema_validity}, outside 0..1",
                True,
            )
        )

    # Non-blocking gaps: real, worth reporting, but the pipeline can proceed.
    pool_intents = {case["true_intent"] for case in pool}
    missing_examples = sorted(set(names) - pool_intents)
    if missing_examples:
        findings.append(
            Finding(
                "intents_without_examples",
                f"declared intents with no training example: {missing_examples}",
            )
        )

    unexpected = sorted(pool_intents - set(names))
    if unexpected:
        findings.append(
            Finding(
                "examples_outside_the_inventory",
                f"the example pool contains intents the project does not declare: "
                f"{unexpected}",
                True,
            )
        )

    pool_types = {e["type"] for case in pool for e in case["entities"]}
    unused_types = sorted(set(type_names) - pool_types)
    if unused_types:
        findings.append(
            Finding(
                "entity_types_without_examples",
                f"declared entity types never seen in the example pool: {unused_types}",
            )
        )

    undeclared_types = sorted(pool_types - set(type_names))
    if undeclared_types:
        findings.append(
            Finding(
                "entity_types_outside_the_schema",
                f"the example pool contains entity types the schema does not declare: "
                f"{undeclared_types}",
                True,
            )
        )

    if not spec.slots_by_intent:
        findings.append(
            Finding("no_slot_mapping", "no intent-to-slot mapping was derived from the pool")
        )

    return findings


# -- part two: enrichment, the only part that calls a model ------------

INTENT_PROMPT = """You are documenting an existing product's request types.

Project description:
{description}

Write one short line describing each of these request types, in the product's
own terms. Describe only the names listed. Do not add, rename or omit any.

Request types:
{names}

Reply with JSON only: {{"descriptions": {{"<name>": "<one line>"}}}}"""

ENTITY_PROMPT = """You are documenting the information an existing product
extracts from a user's request.

Project description:
{description}

Write one short line describing each of these information fields, saying what
it holds. Describe only the names listed. Do not add, rename or omit any.

Fields:
{names}

Reply with JSON only: {{"descriptions": {{"<name>": "<one line>"}}}}"""


def _ask_for_descriptions(
    client: LLMClient, prompt: str, allowed: Sequence[str]
) -> tuple[dict[str, str], list[Finding], int, int]:
    """One enrichment call, with the model's answer filtered to ``allowed``."""
    findings: list[Finding] = []
    record = client.generate(prompt)
    logical = 1
    physical = 0 if record.cache_hit else 1

    if record.error:
        findings.append(
            Finding("enrichment_call_failed", f"enrichment call failed: {record.error}")
        )
        return {}, findings, logical, physical

    text = record.text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[4:] if text.lower().startswith("json") else text
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        findings.append(
            Finding("enrichment_unparseable", f"enrichment reply was not JSON: {exc.msg}")
        )
        return {}, findings, logical, physical

    raw = payload.get("descriptions") if isinstance(payload, dict) else None
    if not isinstance(raw, dict):
        findings.append(
            Finding("enrichment_wrong_shape", "enrichment reply had no descriptions object")
        )
        return {}, findings, logical, physical

    allowed_set = set(allowed)
    kept: dict[str, str] = {}
    invented: list[str] = []
    for name, description in raw.items():
        if not isinstance(name, str) or not isinstance(description, str):
            continue
        if name not in allowed_set:
            invented.append(name)
            continue
        cleaned = " ".join(description.split())
        if cleaned:
            kept[name] = cleaned

    if invented:
        # The authoritative inventory wins: these are discarded, not adopted.
        findings.append(
            Finding(
                "enrichment_named_unknown_fields",
                f"enrichment described names the project does not declare, which were "
                f"discarded: {sorted(invented)}",
            )
        )
    undescribed = sorted(allowed_set - set(kept))
    if undescribed:
        findings.append(
            Finding(
                "enrichment_incomplete",
                f"no description produced for: {undescribed}. These keep no "
                "description rather than an invented one",
            )
        )

    return kept, findings, logical, physical


@dataclass
class Analyzer:
    """Validates a project specification and optionally enriches it."""

    client: LLMClient | None = None

    def analyze(self, spec: ProjectSpec, pool: Sequence[dict]) -> AnalysisResult:
        findings = validate(spec, pool)
        result = AnalysisResult(spec=spec, findings=findings)

        if not result.ok:
            # A contradiction is flagged and stops here; it is never papered
            # over by guessing what was meant.
            return result

        if self.client is None:
            # The no-Analyzer ablation path: the bare specification, unchanged.
            return result

        intent_descriptions, intent_findings, lc1, pc1 = _ask_for_descriptions(
            self.client,
            INTENT_PROMPT.format(
                description=spec.description_text.strip(),
                names="\n".join(f"- {name}" for name in spec.intent_names),
            ),
            spec.intent_names,
        )
        entity_descriptions, entity_findings, lc2, pc2 = _ask_for_descriptions(
            self.client,
            ENTITY_PROMPT.format(
                description=spec.description_text.strip(),
                names="\n".join(f"- {name}" for name in spec.entity_type_names),
            ),
            spec.entity_type_names,
        )

        result.findings.extend(intent_findings + entity_findings)
        result.logical_calls = lc1 + lc2
        result.physical_calls = pc1 + pc2
        result.described_intents = len(intent_descriptions)
        result.described_entities = len(entity_descriptions)
        result.spec = spec.with_descriptions(intent_descriptions, entity_descriptions)
        return result
