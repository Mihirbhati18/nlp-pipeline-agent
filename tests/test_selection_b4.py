"""G5 checks on the shared selection rule and the B4 search baseline.

No model is needed: candidate evaluation is injected.
"""

import pytest

from src.baselines.b4_search import (
    DEFAULT_SEEDS,
    RANDOM_BUDGET,
    draw_random_configs,
    run_random_seeds,
    run_search,
    summarise_random,
)
from src.evaluation.selection import Candidate, select
from src.pipelines.catalogue import CATALOGUE


def metrics(intent=None, entity=None, schema=1.0, p95=None):
    return {
        "primary": {
            "intent_macro_f1": intent,
            "entity_span_f1": entity,
            "schema_validity_after_repair": schema,
            "latency_p95_s": p95,
        }
    }


# -- the selection rule ------------------------------------------------


def test_highest_intent_macro_f1_wins():
    result = select([
        Candidate("a", metrics(intent=0.70, entity=0.5)),
        Candidate("b", metrics(intent=0.82, entity=0.5)),
        Candidate("c", metrics(intent=0.61, entity=0.5)),
    ])

    assert result.selected.config_id == "b"
    assert result.eligible == ["b", "a", "c"]
    assert "highest intent macro-F1" in result.reason


def test_a_tie_on_intent_is_broken_by_entity_f1():
    result = select([
        Candidate("a", metrics(intent=0.80, entity=0.40)),
        Candidate("b", metrics(intent=0.80, entity=0.55)),
    ])

    assert result.selected.config_id == "b"
    assert "tie on intent macro-F1" in result.reason


def test_a_tie_on_intent_and_entity_is_broken_by_lower_p95():
    result = select([
        Candidate("slow", metrics(intent=0.80, entity=0.50, p95=4.0)),
        Candidate("fast", metrics(intent=0.80, entity=0.50, p95=1.5)),
    ])

    assert result.selected.config_id == "fast"


def test_selection_is_deterministic_regardless_of_input_order():
    a = Candidate("a", metrics(intent=0.80, entity=0.50))
    b = Candidate("b", metrics(intent=0.80, entity=0.50))

    assert select([a, b]).selected.config_id == select([b, a]).selected.config_id


def test_the_entity_floor_rejects_a_candidate_with_a_better_intent_score():
    """A hard constraint must beat a better headline score."""
    result = select(
        [
            Candidate("high_intent_bad_entities", metrics(intent=0.90, entity=0.10)),
            Candidate("balanced", metrics(intent=0.75, entity=0.60)),
        ],
        min_entity_f1=0.5,
    )

    assert result.selected.config_id == "balanced"
    assert [r.constraint for r in result.rejections] == ["min_entity_f1"]
    assert result.rejections[0].value == 0.10
    assert result.rejections[0].floor == 0.5


def test_the_schema_validity_floor_is_applied():
    result = select(
        [Candidate("a", metrics(intent=0.9, entity=0.6, schema=0.80))],
        min_schema_validity=0.98,
    )

    assert result.no_eligible_candidate
    assert result.rejections[0].constraint == "min_schema_validity"


def test_no_eligible_candidate_is_an_explicit_outcome():
    result = select(
        [
            Candidate("a", metrics(intent=0.90, entity=0.10)),
            Candidate("b", metrics(intent=0.85, entity=0.20)),
        ],
        min_entity_f1=0.5,
    )

    assert result.no_eligible_candidate
    assert result.selected is None
    assert "no eligible candidate" in result.reason
    assert "relaxing the constraint" in result.reason
    assert len(result.rejections) == 2


def test_a_missing_intent_score_is_rejected_not_treated_as_zero():
    result = select([
        Candidate("failed", metrics(intent=None, entity=0.5)),
        Candidate("ok", metrics(intent=0.4, entity=0.5)),
    ])

    assert result.selected.config_id == "ok"
    assert result.rejections[0].constraint == "intent_macro_f1_missing"


def test_a_measured_p95_is_preferred_over_an_estimate():
    candidate = Candidate("a", metrics(intent=0.8, entity=0.5, p95=2.0), estimated_p95_s=9.0)

    assert candidate.p95_for_constraint() == (2.0, "measured")


def test_an_estimate_is_used_when_no_measurement_exists():
    candidate = Candidate("a", metrics(intent=0.8, entity=0.5), estimated_p95_s=3.0)

    assert candidate.p95_for_constraint() == (3.0, "estimated")


def test_the_latency_floor_filters_on_the_estimate_and_says_so():
    result = select(
        [
            Candidate("slow", metrics(intent=0.9, entity=0.6), estimated_p95_s=8.0),
            Candidate("quick", metrics(intent=0.7, entity=0.6), estimated_p95_s=2.0),
        ],
        max_p95_latency_s=4.0,
    )

    assert result.selected.config_id == "quick"
    assert "estimated" in result.rejections[0].constraint


def test_an_unknown_latency_is_recorded_as_unchecked_not_silently_passed():
    result = select(
        [Candidate("a", metrics(intent=0.8, entity=0.6))],
        max_p95_latency_s=2.0,
    )

    assert result.selected.config_id == "a"
    assert result.unchecked_constraints
    assert "unchecked" in result.unchecked_constraints[0]


def test_the_result_records_the_rule_it_applied():
    result = select([Candidate("a", metrics(intent=0.8, entity=0.5))]).as_dict()

    assert "highest intent macro-F1" in result["rule"]
    assert "ranking" in result and result["ranking"][0]["config_id"] == "a"


# -- B4 search ---------------------------------------------------------


def test_a_seed_always_draws_the_same_configurations():
    assert [c.config_id for c in draw_random_configs(3)] == [
        c.config_id for c in draw_random_configs(3)
    ]


def test_different_seeds_draw_different_configurations():
    draws = {tuple(c.config_id for c in draw_random_configs(s)) for s in range(5)}

    assert len(draws) > 1, "five seeds should not all draw the same four configurations"


def test_a_random_draw_respects_the_budget_and_has_no_duplicates():
    chosen = draw_random_configs(0, budget=RANDOM_BUDGET)

    assert len(chosen) == RANDOM_BUDGET
    assert len({c.config_id for c in chosen}) == RANDOM_BUDGET


def test_a_draw_comes_only_from_the_catalogue():
    valid = {c.config_id for c in CATALOGUE}

    for seed in range(10):
        assert {c.config_id for c in draw_random_configs(seed)} <= valid


def test_a_budget_larger_than_the_catalogue_is_refused():
    with pytest.raises(ValueError, match="exceeds the catalogue size"):
        draw_random_configs(0, budget=99)


def test_b4_random_without_a_seed_is_refused():
    with pytest.raises(ValueError, match="needs a seed"):
        run_search(variant="B4-random", evaluate_config=lambda c: (metrics(0.5, 0.5), 1, 1))


def test_an_unknown_variant_is_refused():
    with pytest.raises(ValueError, match="unknown variant"):
        run_search(variant="B4-clever", evaluate_config=lambda c: (metrics(0.5, 0.5), 1, 1))


def _scored(scores):
    """An evaluator giving each configuration id a fixed score."""

    def evaluate(config):
        value = scores.get(config.config_id, 0.3)
        return metrics(intent=value, entity=0.6), config.calls_per_request * 100, 50

    return evaluate


def test_b4_random_evaluates_exactly_its_budget():
    result = run_search(variant="B4-random", evaluate_config=_scored({}), seed=0)

    assert len(result.attempted) == RANDOM_BUDGET
    assert len(result.candidates) == RANDOM_BUDGET
    assert result.selection.selected is not None


def test_b4_exhaustive_evaluates_the_whole_catalogue():
    result = run_search(variant="B4-exhaustive", evaluate_config=_scored({}))

    assert len(result.attempted) == 12
    assert result.seed is None


def test_b4_exhaustive_finds_the_best_configuration_in_the_catalogue():
    best_id = CATALOGUE[7].config_id
    result = run_search(
        variant="B4-exhaustive", evaluate_config=_scored({best_id: 0.95})
    )

    assert result.selection.selected.config_id == best_id


def test_b4_random_can_miss_the_best_configuration():
    """The point of the ceiling: a 4-candidate budget may not find the best."""
    best_id = CATALOGUE[7].config_id
    missed = 0
    for seed in range(10):
        result = run_search(
            variant="B4-random", evaluate_config=_scored({best_id: 0.95}), seed=seed
        )
        if result.selection.selected.config_id != best_id:
            missed += 1

    assert missed > 0, "a 4 of 12 random budget must sometimes miss the best entry"


def test_b4_records_that_it_has_no_reasoning_to_offer():
    result = run_search(variant="B4-random", evaluate_config=_scored({}), seed=1)

    assert "drawn at random" in result.candidates[0].rationale


def test_b4_reports_logical_calls_separately_from_physical():
    result = run_search(variant="B4-exhaustive", evaluate_config=_scored({}))

    # 8 single-call configurations at 100 and 4 two-stage at 200.
    assert result.logical_calls == 8 * 100 + 4 * 200
    assert result.physical_calls == 12 * 50


def test_b4_logs_an_attempt_event_per_candidate_and_one_decision():
    result = run_search(variant="B4-random", evaluate_config=_scored({}), seed=2)
    kinds = [e["kind"] for e in result.events]

    assert kinds.count("candidate_attempt") == RANDOM_BUDGET
    assert kinds.count("selection_decision") == 1


def test_b4_surfaces_a_no_eligible_outcome_rather_than_picking_anyway():
    def evaluate(config):
        return metrics(intent=0.8, entity=0.05), 100, 50

    result = run_search(
        variant="B4-random", evaluate_config=evaluate, seed=0, min_entity_f1=0.5
    )

    assert result.selection.no_eligible_candidate
    assert result.as_dict()["selection"]["selected"] is None


def test_the_five_seed_summary_reports_a_spread_not_one_number():
    scores = {c.config_id: 0.4 + i * 0.04 for i, c in enumerate(CATALOGUE)}
    results = run_random_seeds(evaluate_config=_scored(scores), seeds=DEFAULT_SEEDS)
    summary = summarise_random(results)

    assert summary["n_seeds"] == 5
    assert len(summary["selected_intent_macro_f1"]) == 5
    assert summary["stdev_intent_macro_f1"] is not None
    assert summary["min_intent_macro_f1"] <= summary["max_intent_macro_f1"]
    assert "noise" in summary["note"]


def test_the_summary_counts_seeds_with_no_eligible_candidate_rather_than_dropping_them():
    def evaluate(config):
        return metrics(intent=0.8, entity=0.05), 100, 50

    results = run_random_seeds(
        evaluate_config=evaluate, seeds=(0, 1), min_entity_f1=0.5
    )
    summary = summarise_random(results)

    assert summary["seeds_with_no_eligible_candidate"] == [0, 1]
    assert summary["mean_intent_macro_f1"] is None
