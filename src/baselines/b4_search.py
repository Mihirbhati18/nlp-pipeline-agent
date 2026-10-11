"""B4: plain search without the agent (PROJECT_PLAN.md section 3).

Why B4 exists, in the plan's own words:

    A1 selects among candidates using development scores; B1 gets no search at
    all. If A1 beats B1, the simplest explanation is "tuning on development
    data helps", not "the agent helps". B4 separates the two.

So B4 gets **everything A1 gets except the agent's judgement**: the same
12-configuration catalogue, the same project specification, the same
development cases, the same scorer and the same selection rule. The only
difference is which candidates get tried.

Two variants:

- **B4-random** — 4 configurations drawn uniformly at random, matching A1's
  4-evaluation budget. Run with 5 seeds, because a single random draw says
  nothing. This is the equal-budget comparison for RQ5.
- **B4-exhaustive** — all 12 configurations. Not a fair comparison at all; it
  is the development-score ceiling, showing how much quality any 4-candidate
  budget leaves on the table.

Determinism: a given seed always draws the same configurations, in the same
order, so a B4-random run is reproducible from its seed alone.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from ..evaluation.selection import Candidate, SelectionResult, select
from ..pipelines.catalogue import CATALOGUE, Config

RANDOM_BUDGET = 4
DEFAULT_SEEDS = (0, 1, 2, 3, 4)


def draw_random_configs(
    seed: int, budget: int = RANDOM_BUDGET, catalogue: Sequence[Config] = CATALOGUE
) -> list[Config]:
    """Draw ``budget`` distinct configurations for a seed, deterministically.

    ``random.Random(seed).sample`` over the catalogue's fixed order means the
    draw depends only on the seed, so it is reproducible and auditable.
    """
    if budget > len(catalogue):
        raise ValueError(f"budget {budget} exceeds the catalogue size {len(catalogue)}")
    return random.Random(seed).sample(list(catalogue), budget)


@dataclass
class SearchResult:
    variant: str
    seed: int | None
    attempted: list[str]
    candidates: list[Candidate]
    selection: SelectionResult
    # Logical calls the method would have made on its own, which is what
    # design cost reports regardless of how many were served from cache.
    logical_calls: int = 0
    physical_calls: int = 0
    events: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "variant": self.variant,
            "seed": self.seed,
            "budget_used": len(self.attempted),
            "attempted": self.attempted,
            "selection": self.selection.as_dict(),
            "design_cost": {
                "logical_calls": self.logical_calls,
                "physical_calls": self.physical_calls,
            },
        }


def run_search(
    *,
    variant: str,
    evaluate_config: Callable[[Config], tuple[dict[str, Any], int, int]],
    seed: int | None = None,
    budget: int = RANDOM_BUDGET,
    catalogue: Sequence[Config] = CATALOGUE,
    min_entity_f1: float | None = None,
    max_p95_latency_s: float | None = None,
    min_schema_validity: float | None = None,
    estimate_p95: Callable[[Config], float | None] | None = None,
) -> SearchResult:
    """Run one B4 search.

    ``evaluate_config`` scores one configuration on development data and
    returns ``(metrics, logical_calls, physical_calls)``. Injecting it keeps
    this module free of model and I/O concerns and makes it fully testable
    without a model.

    ``variant`` is "B4-random" (needs a seed) or "B4-exhaustive".
    """
    if variant == "B4-random":
        if seed is None:
            raise ValueError("B4-random needs a seed; a single unseeded draw is not reproducible")
        chosen = draw_random_configs(seed, budget, catalogue)
    elif variant == "B4-exhaustive":
        chosen = list(catalogue)
    else:
        raise ValueError(f"unknown variant {variant!r}")

    candidates: list[Candidate] = []
    events: list[dict] = []
    logical = physical = 0

    for config in chosen:
        metrics, config_logical, config_physical = evaluate_config(config)
        logical += config_logical
        physical += config_physical
        candidate = Candidate(
            config_id=config.config_id,
            metrics=metrics,
            # B4 has no reasoning to offer. Saying so plainly is the point of
            # the baseline: it is search without judgement.
            rationale=(
                f"drawn at random (seed {seed})" if variant == "B4-random"
                else "every catalogue entry evaluated"
            ),
            estimated_p95_s=estimate_p95(config) if estimate_p95 else None,
        )
        candidates.append(candidate)
        events.append({
            "kind": "candidate_attempt",
            "variant": variant,
            "seed": seed,
            "config_id": config.config_id,
            "intent_macro_f1": candidate.intent_macro_f1,
            "entity_span_f1": candidate.entity_span_f1,
            "logical_calls": config_logical,
            "physical_calls": config_physical,
        })

    selection = select(
        candidates,
        min_entity_f1=min_entity_f1,
        max_p95_latency_s=max_p95_latency_s,
        min_schema_validity=min_schema_validity,
    )
    events.append({
        "kind": "selection_decision",
        "variant": variant,
        "seed": seed,
        **selection.as_dict(),
    })

    return SearchResult(
        variant=variant,
        seed=seed,
        attempted=[c.config_id for c in chosen],
        candidates=candidates,
        selection=selection,
        logical_calls=logical,
        physical_calls=physical,
        events=events,
    )


def run_random_seeds(
    *,
    evaluate_config: Callable[[Config], tuple[dict[str, Any], int, int]],
    seeds: Sequence[int] = DEFAULT_SEEDS,
    **kwargs: Any,
) -> list[SearchResult]:
    """B4-random across its seeds. Reported as a distribution, not one number."""
    return [
        run_search(variant="B4-random", evaluate_config=evaluate_config, seed=seed, **kwargs)
        for seed in seeds
    ]


def summarise_random(results: Sequence[SearchResult]) -> dict[str, Any]:
    """Aggregate B4-random across seeds.

    A single random draw is noise; the comparison against A1 is against this
    spread. Seeds where no candidate was eligible are counted, not dropped.
    """
    import statistics

    scores = [
        r.selection.selected.intent_macro_f1
        for r in results
        if r.selection.selected is not None and r.selection.selected.intent_macro_f1 is not None
    ]
    no_eligible = [r.seed for r in results if r.selection.no_eligible_candidate]

    return {
        "n_seeds": len(results),
        "selected_config_ids": [
            r.selection.selected.config_id if r.selection.selected else None for r in results
        ],
        "selected_intent_macro_f1": scores,
        "mean_intent_macro_f1": statistics.mean(scores) if scores else None,
        "stdev_intent_macro_f1": statistics.stdev(scores) if len(scores) > 1 else None,
        "min_intent_macro_f1": min(scores) if scores else None,
        "max_intent_macro_f1": max(scores) if scores else None,
        "seeds_with_no_eligible_candidate": no_eligible,
        "mean_logical_calls": (
            statistics.mean([r.logical_calls for r in results]) if results else None
        ),
        "note": (
            "B4-random is a distribution over seeds. Comparing A1 against a "
            "single seed's draw would be comparing against noise."
        ),
    }
