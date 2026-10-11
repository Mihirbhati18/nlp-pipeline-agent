"""The experiment runner: one configuration over one split, into one run folder.

Every LLM system's evaluation goes through here, so each run gets the same
manifest, the same prediction log and the same scoring. Nothing is written by
hand (PROJECT_PLAN.md section 10).

Two separate jobs, deliberately not mixed:

- ``evaluate`` scores a configuration. It uses the prediction cache, so a
  configuration already run for another system costs no new calls, and it
  produces **no latency figure at all**.
- ``time_requests`` produces latency. It runs a fixed set of development cases
  with the cache disabled after a warm-up, and that is the only source of the
  numbers reported as latency (section 2A).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Sequence

from ..analyzer.spec import ProjectSpec
from ..llm.client import LLMClient
from ..pipelines.catalogue import Config, ConfigRunner
from ..pipelines.examples import ExampleSelector
from .runs import new_run
from .scorer import Prediction, score

TIMING_CASES = 50
TIMING_WARMUP = 5


@dataclass
class EvaluationResult:
    run_id: str
    metrics: dict[str, Any]
    predictions: list[Prediction]
    design_cost: dict[str, Any]


def _make_runner(
    config: Config,
    spec: ProjectSpec,
    client: LLMClient,
    pool: Sequence[dict],
    oos_threshold: float | None,
    allow_repair: bool,
) -> ConfigRunner:
    return ConfigRunner(
        config=config,
        spec=spec,
        client=client,
        selector=ExampleSelector(list(pool)),
        oos_threshold=oos_threshold,
        allow_repair=allow_repair,
    )


def evaluate(
    *,
    system: str,
    config: Config,
    spec: ProjectSpec,
    client: LLMClient,
    pool: Sequence[dict],
    cases: Sequence[dict],
    split: str,
    seed: int | str = 0,
    oos_threshold: float | None = None,
    allow_repair: bool = True,
    latencies: Sequence[float] | None = None,
    extra_config: dict[str, Any] | None = None,
) -> EvaluationResult:
    """Run and score one configuration. Produces no latency of its own.

    ``latencies`` may be supplied from a separate timing run; it is passed
    straight to the scorer and never inferred from these calls.
    """
    runner = _make_runner(config, spec, client, pool, oos_threshold, allow_repair)

    run_config: dict[str, Any] = {
        "system": system,
        "split": split,
        "config": config.as_dict(),
        "model": client.model,
        "model_digest": client.model_digest,
        "settings": client.settings,
        "cache_enabled": client.cache_enabled,
        "oos_threshold": oos_threshold,
        "allow_repair": allow_repair,
        "spec_enriched": spec.enriched,
        "n_cases": len(cases),
        "pool_size": len(pool),
        "data_sources": spec.source,
        **(extra_config or {}),
    }

    started = time.perf_counter()
    predictions: list[Prediction] = []
    logical = physical = hits = repairs = rejections = 0

    with new_run(
        spec.project_id,
        system,
        seed,
        run_config,
        data_paths={"pool": spec.source["kshot"], split: spec.source.get(split, "")},
    ) as log:
        for case in cases:
            outcome = runner.run_case(case)
            predictions.append(outcome.prediction)
            logical += outcome.logical_calls
            physical += outcome.physical_calls
            hits += outcome.cache_hits
            repairs += 1 if outcome.repaired else 0
            rejections += 1 if outcome.rejected_by_threshold else 0

            log.log_prediction(
                case_id=case["case_id"],
                gold_intent=case["true_intent"],
                gold_in_scope=case["in_scope"],
                status=outcome.prediction.status,
                predicted_intent=outcome.prediction.intent,
                predicted_entities=outcome.prediction.entities,
                schema_valid_raw=outcome.prediction.schema_valid_raw,
                schema_valid_final=outcome.prediction.schema_valid_final,
                retries=outcome.prediction.retries,
                error=outcome.prediction.error,
                logical_calls=outcome.logical_calls,
                physical_calls=outcome.physical_calls,
                cache_hits=outcome.cache_hits,
                prompt_tokens=outcome.prompt_tokens,
                rejected_by_threshold=outcome.rejected_by_threshold,
                # No latency here by design: see time_requests.
            )
            for event in outcome.events:
                log.log_event(event.pop("kind"), **event)

        design_cost = {
            "logical_calls": logical,
            "physical_calls": physical,
            "cache_hits": hits,
            "repair_retries": repairs,
            "threshold_rejections": rejections,
            "wall_time_s": time.perf_counter() - started,
            "note": (
                "logical calls are what this system would have made alone; "
                "physical calls are what was actually sent to the model. "
                "Cache hits are not free design cost."
            ),
        }
        metrics = score(
            cases,
            predictions,
            labels=spec.intent_names,
            latencies=latencies,
            design_cost=design_cost,
        )
        log.write_metrics(metrics)
        log.write_summary(_summary(system, spec, config, split, metrics, design_cost))
        log.finish(status="complete", n_cases=len(cases))
        run_id = log.run_id

    return EvaluationResult(
        run_id=run_id, metrics=metrics, predictions=predictions, design_cost=design_cost
    )


def time_requests(
    *,
    system: str,
    config: Config,
    spec: ProjectSpec,
    client: LLMClient,
    pool: Sequence[dict],
    cases: Sequence[dict],
    seed: int | str = 0,
    oos_threshold: float | None = None,
    n_cases: int = TIMING_CASES,
    warmup: int = TIMING_WARMUP,
) -> tuple[str, list[float]]:
    """Measure latency on a fixed case set with the cache disabled.

    The client is replaced by its cache-disabled twin, so a cached prediction
    can never supply a timing value. Returns the run ID and the latencies.
    """
    timed_client = client.with_cache_disabled()
    runner = _make_runner(config, spec, timed_client, pool, oos_threshold, True)
    selected = list(cases)[:n_cases]

    run_config = {
        "system": system,
        "split": "dev-timing",
        "purpose": "uncached latency measurement; the only source of latency figures",
        "config": config.as_dict(),
        "model": client.model,
        "model_digest": client.model_digest,
        "settings": client.settings,
        "cache_enabled": False,
        "oos_threshold": oos_threshold,
        "n_cases": len(selected),
        "warmup": warmup,
    }

    latencies: list[float] = []
    with new_run(spec.project_id, f"{system}-timing", seed, run_config) as log:
        cold_start: float | None = None
        for index, case in enumerate(list(cases)[:warmup]):
            started = time.perf_counter()
            runner.run_case(case)
            elapsed = time.perf_counter() - started
            if index == 0:
                cold_start = elapsed
            log.log_timing(case_id=case["case_id"], latency_s=elapsed, warmup=True)

        for case in selected:
            started = time.perf_counter()
            outcome = runner.run_case(case)
            elapsed = time.perf_counter() - started
            # A threshold rejection costs no model call; including it would
            # flatter the configuration's latency, so it is logged and excluded.
            if outcome.rejected_by_threshold:
                log.log_timing(
                    case_id=case["case_id"], latency_s=elapsed, warmup=False,
                    excluded="threshold rejection, no model call",
                )
                continue
            latencies.append(elapsed)
            log.log_timing(case_id=case["case_id"], latency_s=elapsed, warmup=False)

        log.write_metrics({
            "latency_n": len(latencies),
            "cold_start_s": cold_start,
            "note": "warm-up observations are logged but excluded from the figures",
        })
        log.finish(status="complete")
        run_id = log.run_id

    return run_id, latencies


def _summary(
    system: str,
    spec: ProjectSpec,
    config: Config,
    split: str,
    metrics: dict[str, Any],
    design_cost: dict[str, Any],
) -> str:
    p = metrics["primary"]

    def show(value, digits=3):
        return "n/a" if value is None else f"{value:.{digits}f}"

    lines = [
        f"# {system} on {spec.project_id} ({split})",
        "",
        f"Configuration: `{config.config_id}` "
        f"({config.extraction}, {config.example_selection}, {config.oos_policy}).",
        f"Cases: {metrics['n_cases']} "
        f"({metrics['n_in_scope']} in-scope, {metrics['n_out_of_scope']} out-of-scope).",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Intent macro-F1 | {show(p['intent_macro_f1'])} |",
        f"| Entity span F1 | {show(p['entity_span_f1'])} |",
        f"| Out-of-scope F1 | {show(p['oos_f1'])} |",
        f"| In-scope false rejection | {show(p['false_rejection_rate_in_scope'])} |",
        f"| Schema validity after repair | {show(p['schema_validity_after_repair'])} |",
        f"| Schema validity before repair | {show(p['schema_validity_before_repair'])} |",
        f"| Unsupported extraction rate | {show(p['unsupported_extraction_rate'])} |",
        f"| Runtime failure rate | {show(p['runtime_failure_rate'])} |",
        f"| Latency median / p95 (s) | {show(p['latency_median_s'], 2)} / {show(p['latency_p95_s'], 2)} |",
        "",
        f"Design cost: {design_cost['logical_calls']} logical calls, "
        f"{design_cost['physical_calls']} physical, "
        f"{design_cost['cache_hits']} cache hits, "
        f"{design_cost['repair_retries']} repair retries.",
        "",
    ]
    if p["unsupported_extraction_rate"] is None:
        lines.append(
            "Unsupported extraction rate is N/A because no entity was predicted. "
            "Entity recall remains visible above; an empty output is not a solution."
        )
    if p["runtime_failure_rate"]:
        lines.append(
            f"Runtime failures: {p['runtime_failure_counts']}. "
            "Failed cases stay in every denominator."
        )
    if metrics["invalid_label_predictions"]:
        lines.append(
            f"Labels predicted outside the declared inventory: "
            f"{metrics['invalid_label_predictions']}."
        )
    if p["latency_median_s"] is None:
        lines.append(
            "No latency is reported: this run used the prediction cache. "
            "Latency comes only from a separate uncached timing run."
        )
    return "\n".join(lines)
