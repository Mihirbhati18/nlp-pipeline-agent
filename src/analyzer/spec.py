"""The project specification every system runs against.

At G4 this is loaded directly from the authoritative sources: the data manifest
(intents, entity types, split files) and the frozen project description. At G6
the Analyzer produces the *same* structure from the free-text description, and
its job is to add the enrichment that is ``None`` here — intent and entity
descriptions — without contradicting the authoritative fields.

That split is what makes the no-Analyzer ablation meaningful: the ablation uses
this bare specification, and A1 uses the enriched one.

Authoritative supplied fields always take precedence over inferred fields
(PROJECT_PLAN.md section 6), so ``intents`` and ``entity_types`` are taken from
the manifest and the Analyzer may never change them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OOS_LABEL = "none_of_the_above"


@dataclass(frozen=True)
class IntentSpec:
    name: str
    description: str | None = None


@dataclass(frozen=True)
class EntitySpec:
    name: str
    description: str | None = None


@dataclass
class Constraints:
    """Declared operating limits. Hard constraints filter candidates at G8."""

    max_p95_latency_s: float | None = None
    min_schema_validity: float | None = None
    notes: str = ""


@dataclass
class ProjectSpec:
    project_id: str
    name: str
    description_text: str
    intents: list[IntentSpec]
    entity_types: list[EntitySpec]
    # Which entity types occur with which intent, derived from the k-shot pool
    # only. Used by the two-stage extraction strategy to ask for just the slots
    # that intent can carry.
    slots_by_intent: dict[str, list[str]] = field(default_factory=dict)
    constraints: Constraints = field(default_factory=Constraints)
    source: dict[str, str] = field(default_factory=dict)
    enriched: bool = False

    @property
    def intent_names(self) -> list[str]:
        return [i.name for i in self.intents]

    @property
    def entity_type_names(self) -> list[str]:
        return [e.name for e in self.entity_types]

    def describe_intents(self) -> list[tuple[str, str | None]]:
        return [(i.name, i.description) for i in self.intents]

    def with_descriptions(
        self,
        intent_descriptions: dict[str, str],
        entity_descriptions: dict[str, str],
    ) -> "ProjectSpec":
        """Return an enriched copy. Authoritative names are never changed.

        Descriptions for names outside the declared inventory are ignored, so
        an Analyzer cannot introduce an intent or entity type by describing one.
        """
        return ProjectSpec(
            project_id=self.project_id,
            name=self.name,
            description_text=self.description_text,
            intents=[
                IntentSpec(i.name, intent_descriptions.get(i.name, i.description))
                for i in self.intents
            ],
            entity_types=[
                EntitySpec(e.name, entity_descriptions.get(e.name, e.description))
                for e in self.entity_types
            ],
            slots_by_intent=dict(self.slots_by_intent),
            constraints=self.constraints,
            source=dict(self.source),
            enriched=True,
        )


def load_cases(path: str | Path) -> list[dict]:
    with open(ROOT / path if not Path(path).is_absolute() else path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def load_spec(
    project_id: str,
    *,
    constraints: Constraints | None = None,
    root: Path = ROOT,
) -> ProjectSpec:
    """Build the bare specification for a project from its frozen sources."""
    manifest = json.loads(
        (root / "data" / "manifests" / f"{project_id}.json").read_text(encoding="utf-8")
    )
    description = (
        root / "configs" / "descriptions" / f"{project_id}.md"
    ).read_text(encoding="utf-8")

    pool = load_cases(root / manifest["files"]["kshot"])
    slots_by_intent: dict[str, set[str]] = {name: set() for name in manifest["intents"]}
    for case in pool:
        for entity in case["entities"]:
            slots_by_intent.setdefault(case["true_intent"], set()).add(entity["type"])

    return ProjectSpec(
        project_id=project_id,
        name=manifest["name"],
        description_text=description,
        intents=[IntentSpec(name) for name in manifest["intents"]],
        entity_types=[EntitySpec(name) for name in manifest["entity_schema"]],
        slots_by_intent={k: sorted(v) for k, v in sorted(slots_by_intent.items())},
        constraints=constraints or Constraints(),
        source={
            "manifest": f"data/manifests/{project_id}.json",
            "description": f"configs/descriptions/{project_id}.md",
            "kshot": manifest["files"]["kshot"],
            "dev": manifest["files"]["dev"],
            # The test path is recorded but must not be opened before the freeze.
            "test": manifest["files"]["test"],
        },
    )
