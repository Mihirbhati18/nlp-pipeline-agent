"""The candidate selection rule, shared by B4 and the agent (A1).

From PROJECT_PLAN.md section 6:

    Filter by declared hard constraints. Use a fixed ranking rule: highest
    intent macro-F1 among candidates meeting the entity and latency floors,
    with tie-breaks by entity F1 and then lower p95 latency. Do not hide
    trade-offs inside an unexplained weighted average.

This rule lives here and nowhere else, because B4 exists precisely to test
whether the *agent's choice of candidates* helps. If B4 and A1 ranked their
candidates by different logic, any difference between them would be
uninterpretable: it could be the search or it could be the ranking.

**No-eligible-candidate is a real outcome.** If every candidate fails a hard
constraint, ``select`` returns a result with ``selected=None`` and the reason,
rather than quietly relaxing the constraint or returning the least-bad option.

**On the latency floor.** A declared p95 latency constraint cannot be checked
from a cached evaluation run, because cached predictions carry no latency
(section 2A), and timing every candidate would cost far more calls than the
budget allows. So a candidate may carry a *declared estimate*, and the floor is
applied to that; the selected pipeline's real p95 is then measured in the
uncached timing run and checked against L_max. Where no estimate exists, the
latency constraint is recorded as unchecked rather than silently passed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass
class Candidate:
    """One evaluated candidate configuration awaiting selection."""

    config_id: str
    metrics: dict[str, Any]
    rationale: str = ""
    # Optional a priori p95 estimate in seconds; see the module docstring.
    estimated_p95_s: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def intent_macro_f1(self) -> float | None:
        return self.metrics.get("primary", {}).get("intent_macro_f1")

    @property
    def entity_span_f1(self) -> float | None:
        return self.metrics.get("primary", {}).get("entity_span_f1")

    @property
    def schema_validity(self) -> float | None:
        return self.metrics.get("primary", {}).get("schema_validity_after_repair")

    @property
    def measured_p95_s(self) -> float | None:
        return self.metrics.get("primary", {}).get("latency_p95_s")

    def p95_for_constraint(self) -> tuple[float | None, str]:
        """The p95 used for filtering, and where it came from."""
        if self.measured_p95_s is not None:
            return self.measured_p95_s, "measured"
        if self.estimated_p95_s is not None:
            return self.estimated_p95_s, "estimated"
        return None, "unavailable"


@dataclass
class Rejection:
    config_id: str
    constraint: str
    value: float | None
    floor: float | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "config_id": self.config_id,
            "constraint": self.constraint,
            "value": self.value,
            "floor": self.floor,
        }


@dataclass
class SelectionResult:
    selected: Candidate | None
    reason: str
    eligible: list[str]
    rejections: list[Rejection]
    ranking: list[dict[str, Any]]
    unchecked_constraints: list[str] = field(default_factory=list)

    @property
    def no_eligible_candidate(self) -> bool:
        return self.selected is None

    def as_dict(self) -> dict[str, Any]:
        return {
            "selected": self.selected.config_id if self.selected else None,
            "no_eligible_candidate": self.no_eligible_candidate,
            "reason": self.reason,
            "eligible": self.eligible,
            "rejections": [r.as_dict() for r in self.rejections],
            "ranking": self.ranking,
            "unchecked_constraints": self.unchecked_constraints,
            "rule": (
                "highest intent macro-F1 among candidates meeting the declared "
                "floors; ties broken by entity F1, then by lower p95 latency, "
                "then by configuration id for determinism"
            ),
        }


def select(
    candidates: Sequence[Candidate],
    *,
    min_entity_f1: float | None = None,
    max_p95_latency_s: float | None = None,
    min_schema_validity: float | None = None,
) -> SelectionResult:
    """Apply the fixed rule. Deterministic for a given candidate list.

    A candidate whose intent macro-F1 is missing cannot be ranked and is
    rejected rather than treated as zero, because a missing score usually
    means the run failed and should be visible as such.
    """
    rejections: list[Rejection] = []
    unchecked: list[str] = []
    eligible: list[Candidate] = []

    for candidate in candidates:
        if candidate.intent_macro_f1 is None:
            rejections.append(Rejection(candidate.config_id, "intent_macro_f1_missing", None, None))
            continue

        if min_entity_f1 is not None:
            value = candidate.entity_span_f1
            if value is None or value < min_entity_f1:
                rejections.append(
                    Rejection(candidate.config_id, "min_entity_f1", value, min_entity_f1)
                )
                continue

        if min_schema_validity is not None:
            value = candidate.schema_validity
            if value is None or value < min_schema_validity:
                rejections.append(
                    Rejection(
                        candidate.config_id, "min_schema_validity", value, min_schema_validity
                    )
                )
                continue

        if max_p95_latency_s is not None:
            value, source = candidate.p95_for_constraint()
            if value is None:
                # Recorded as unchecked, never silently passed.
                unchecked.append(
                    f"{candidate.config_id}: p95 latency constraint unchecked "
                    f"(no measured or estimated value)"
                )
            elif value > max_p95_latency_s:
                rejections.append(
                    Rejection(
                        candidate.config_id, f"max_p95_latency_s ({source})",
                        value, max_p95_latency_s,
                    )
                )
                continue

        eligible.append(candidate)

    # Rank: intent macro-F1 desc, entity F1 desc, p95 asc, config_id asc.
    def sort_key(candidate: Candidate):
        p95, _ = candidate.p95_for_constraint()
        return (
            -(candidate.intent_macro_f1 or 0.0),
            -(candidate.entity_span_f1 or 0.0),
            p95 if p95 is not None else float("inf"),
            candidate.config_id,
        )

    ordered = sorted(eligible, key=sort_key)
    ranking = [
        {
            "config_id": c.config_id,
            "intent_macro_f1": c.intent_macro_f1,
            "entity_span_f1": c.entity_span_f1,
            "schema_validity": c.schema_validity,
            "p95_s": c.p95_for_constraint()[0],
            "p95_source": c.p95_for_constraint()[1],
        }
        for c in ordered
    ]

    if not ordered:
        return SelectionResult(
            selected=None,
            reason=(
                "no eligible candidate: every candidate failed a declared hard "
                "constraint. Reported as an explicit outcome rather than "
                "relaxing the constraint or returning the least-bad option."
            ),
            eligible=[],
            rejections=rejections,
            ranking=[],
            unchecked_constraints=unchecked,
        )

    best = ordered[0]
    reason = (
        f"{best.config_id} has the highest intent macro-F1 "
        f"({best.intent_macro_f1:.4f}) among {len(ordered)} eligible candidate(s)"
    )
    if len(ordered) > 1 and ordered[1].intent_macro_f1 == best.intent_macro_f1:
        reason += "; tie on intent macro-F1 broken by entity F1, then p95 latency"

    return SelectionResult(
        selected=best,
        reason=reason,
        eligible=[c.config_id for c in ordered],
        rejections=rejections,
        ranking=ranking,
        unchecked_constraints=unchecked,
    )
