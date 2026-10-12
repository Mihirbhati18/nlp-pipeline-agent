"""G8: run the full A1 design, and B4 at the same budget, on development data.

This is the comparison the project turns on. For each development project it
runs, all through the same catalogue, the same development cases and the same
selection rule:

- **A1** - Analyzer enriches the specification, Architect picks 3 candidates
  then 1 revision after reading the error report.
- **B4-random** - 4 candidates drawn at random, across 5 seeds.
- **B4-exhaustive** (optional) - all 12, the development-score ceiling.
- **B1** - the single predeclared configuration, no search at all.

Every run gets its own immutable folder. Latency is deliberately absent from
all of them: these runs use the prediction cache, and latency comes only from
the separate uncached timing runs at G11.

Development scores here are *selection* scores, not results. The honest figures
come from the frozen test runs after G10.

Usage:
    python scripts/run_design.py --model qwen2.5:3b
    python scripts/run_design.py --model qwen2.5:3b --systems A1 B1
    python scripts/run_design.py --model qwen2.5:3b --exhaustive
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analyzer.access import access_for  # noqa: E402
from src.analyzer.spec import load_cases, load_spec  # noqa: E402
from src.architect.design_run import (  # noqa: E402
    estimate_p95,
    make_config_evaluator,
    run_design,
)
from src.baselines.b4_search import (  # noqa: E402
    DEFAULT_SEEDS,
    run_random_seeds,
    run_search,
    summarise_random,
)
from src.evaluation.runs import new_run  # noqa: E402
from src.evaluation.scorer import score  # noqa: E402
from src.evaluation.thresholds import tune_binary_threshold  # noqa: E402
from src.llm.client import make_client, model_details, ollama_version  # noqa: E402
from src.pipelines.catalogue import B1_CONFIG_ID, ConfigRunner, get_config  # noqa: E402
from src.pipelines.examples import ExampleSelector  # noqa: E402

# Measured at G0 for the chosen runtime model; used only to filter a declared
# latency constraint before anything is timed.
SINGLE_CALL_P95_S = 0.59


def fmt(value, digits=3):
    return "n/a" if value is None else f"{value:.{digits}f}"


def base_config(client, project, system, split, extra=None):
    config = {
        "system": system,
        "split": split,
        "model": client.model,
        "model_digest": client.model_digest,
        "model_details": model_details(client.model),
        "settings": client.settings,
        "cache_enabled": client.cache_enabled,
        "latency_note": (
            "no latency is reported: this run uses the prediction cache. "
            "Latency comes only from the uncached timing runs."
        ),
        "score_note": (
            "development scores are selection scores, not results. The reported "
            "figures come from the frozen test runs after G10."
        ),
    }
    config.update(extra or {})
    return config


def main() -> int:
    parser = argparse.ArgumentParser(description="G8 design and search runs")
    parser.add_argument("--model", default="qwen2.5:3b")
    parser.add_argument("--projects", nargs="+", default=["P1", "P2"])
    parser.add_argument(
        "--systems", nargs="+", default=["A1", "B1", "B4-random"],
        choices=["A1", "B1", "B4-random", "B4-exhaustive"],
    )
    parser.add_argument("--exhaustive", action="store_true",
                        help="also run B4-exhaustive, the development ceiling")
    parser.add_argument("--host", default="http://127.0.0.1:11434")
    parser.add_argument("--min-entity-f1", type=float, default=None)
    parser.add_argument("--max-p95-latency-s", type=float, default=None)
    parser.add_argument("--min-schema-validity", type=float, default=None)
    args = parser.parse_args()

    systems = list(args.systems)
    if args.exhaustive and "B4-exhaustive" not in systems:
        systems.append("B4-exhaustive")

    try:
        version = ollama_version(args.host)
    except Exception as exc:  # noqa: BLE001
        print(f"Cannot reach Ollama at {args.host}: {exc}", file=sys.stderr)
        return 2

    client = make_client(args.model, host=args.host)
    print(f"Ollama {version}, model {args.model} (digest {client.model_digest[:16]})")
    print(f"systems: {', '.join(systems)} | projects: {', '.join(args.projects)}")
    print("Development scores below are selection scores, not results.\n")

    constraints = {
        "min_entity_f1": args.min_entity_f1,
        "max_p95_latency_s": args.max_p95_latency_s,
        "min_schema_validity": args.min_schema_validity,
    }

    for project in args.projects:
        spec = load_spec(project)
        access = access_for(spec)
        pool = load_cases(access.train_path)
        dev = load_cases(access.dev_path)
        print(f"=== {project} {spec.name}: {len(dev)} development cases, "
              f"{len(spec.intents)} intents ===")

        selector = ExampleSelector(list(pool))
        threshold = tune_binary_threshold(
            [selector.max_similarity(c["utt"]) for c in dev],
            [c["in_scope"] for c in dev],
        )

        # ---- B1: one predeclared configuration, no search ----------
        if "B1" in systems:
            config = get_config(B1_CONFIG_ID)
            runner = ConfigRunner(
                config=config, spec=spec, client=client, selector=selector,
                oos_threshold=threshold.threshold,
            )
            predictions, logical, physical = [], 0, 0
            for case in dev:
                outcome = runner.run_case(case)
                predictions.append(outcome.prediction)
                logical += outcome.logical_calls
                physical += outcome.physical_calls
            metrics = score(dev, predictions, labels=spec.intent_names)

            with new_run(
                project, "B1", 0,
                base_config(client, project, "B1", "dev", {
                    "config": config.as_dict(),
                    "oos_threshold": threshold.as_dict(),
                    "search": "none: B1 is fixed to one predeclared configuration",
                    "data_access": access.as_dict(),
                    "data_sources": spec.source,
                }),
                data_paths={"pool": spec.source["kshot"], "dev": spec.source["dev"]},
            ) as log:
                for case, prediction in zip(dev, predictions):
                    log.log_prediction(
                        case_id=case["case_id"], gold_intent=case["true_intent"],
                        gold_in_scope=case["in_scope"], status=prediction.status,
                        predicted_intent=prediction.intent,
                        predicted_entities=prediction.entities,
                        schema_valid_raw=prediction.schema_valid_raw,
                        schema_valid_final=prediction.schema_valid_final,
                        retries=prediction.retries, error=prediction.error,
                    )
                log.write_metrics(metrics)
                log.finish(status="complete", n_cases=len(dev))
                p = metrics["primary"]
                print(f"  B1  {config.config_id:22} intent {fmt(p['intent_macro_f1'])} "
                      f"entity {fmt(p['entity_span_f1'])} oos {fmt(p['oos_f1'])} "
                      f"schema {fmt(p['schema_validity_after_repair'])} "
                      f"({logical} logical, {physical} physical calls)")

        # ---- A1: the full design ------------------------------------
        if "A1" in systems:
            design = run_design(
                spec, access,
                runtime_client=client,
                planning_client=client,
                load_cases=load_cases,
                single_call_p95_s=SINGLE_CALL_P95_S,
                **constraints,
            )
            selected = design.selected_config_id
            with new_run(
                project, "A1", 0,
                base_config(client, project, "A1", "dev", {
                    "selected_config_id": selected,
                    "constraints": constraints,
                    "oos_threshold": design.oos_threshold.as_dict(),
                    "data_access": design.data_access,
                    "data_sources": spec.source,
                    **design.as_dict(),
                }),
                data_paths={"pool": spec.source["kshot"], "dev": spec.source["dev"]},
            ) as log:
                for event in design.design.events:
                    log.log_event(event.get("kind", "event"),
                                  **{k: v for k, v in event.items() if k != "kind"})
                for finding in design.analysis.findings:
                    record = finding.as_dict()
                    log.log_event(
                        "analyzer_finding",
                        finding_kind=record.pop("kind"),
                        **record,
                    )
                chosen = next(
                    (e for e in design.evaluations if e.config_id == selected), None
                )
                if chosen:
                    log.write_metrics(chosen.metrics)
                log.finish(status="complete", n_cases=len(dev))

                print(f"  A1  selected {selected or 'NONE ELIGIBLE':22} "
                      f"{'' if chosen is None else 'intent ' + fmt(chosen.metrics['primary']['intent_macro_f1'])} "
                      f"| {design.design.reasoned_choices}/{design.design.budget_used} choices reasoned "
                      f"| {design.total_logical_calls} logical calls "
                      f"({design.design.planning_calls} planning)")
                for attempt in design.design.attempts:
                    row = attempt.as_dict()
                    print(f"        tried {row['config_id']:22} intent {fmt(row['intent_macro_f1'])} "
                          f"entity {fmt(row['entity_span_f1'])} [{row['source']}/{row['stage']}] "
                          f"{row['rationale'][:60]}")
                for finding in design.design.findings:
                    print(f"        note: {finding}")

        # ---- B4: plain search at the same budget --------------------
        if "B4-random" in systems or "B4-exhaustive" in systems:
            evaluate = make_config_evaluator(
                spec, client, pool, dev, threshold.threshold
            )
            estimator = lambda c: estimate_p95(c, SINGLE_CALL_P95_S)  # noqa: E731

            if "B4-random" in systems:
                results = run_random_seeds(
                    evaluate_config=evaluate, seeds=DEFAULT_SEEDS,
                    estimate_p95=estimator, **constraints,
                )
                summary = summarise_random(results)
                with new_run(
                    project, "B4-random", "seeds",
                    base_config(client, project, "B4-random", "dev", {
                        "seeds": list(DEFAULT_SEEDS),
                        "constraints": constraints,
                        "oos_threshold": threshold.as_dict(),
                        "summary": summary,
                        "per_seed": [r.as_dict() for r in results],
                        "data_sources": spec.source,
                    }),
                    data_paths={"pool": spec.source["kshot"], "dev": spec.source["dev"]},
                ) as log:
                    for result in results:
                        for event in result.events:
                            log.log_event(event.get("kind", "event"),
                                          **{k: v for k, v in event.items() if k != "kind"})
                    log.write_metrics({"b4_random_summary": summary})
                    log.finish(status="complete")
                print(f"  B4-random over {summary['n_seeds']} seeds: intent macro-F1 "
                      f"mean {fmt(summary['mean_intent_macro_f1'])} "
                      f"sd {fmt(summary['stdev_intent_macro_f1'])} "
                      f"range {fmt(summary['min_intent_macro_f1'])}-"
                      f"{fmt(summary['max_intent_macro_f1'])}")
                print(f"        selected: {summary['selected_config_ids']}")

            if "B4-exhaustive" in systems:
                result = run_search(
                    variant="B4-exhaustive", evaluate_config=evaluate,
                    estimate_p95=estimator, **constraints,
                )
                with new_run(
                    project, "B4-exhaustive", 0,
                    base_config(client, project, "B4-exhaustive", "dev", {
                        "constraints": constraints,
                        "oos_threshold": threshold.as_dict(),
                        "role": "development-score ceiling, not a fair comparison",
                        **result.as_dict(),
                        "data_sources": spec.source,
                    }),
                    data_paths={"pool": spec.source["kshot"], "dev": spec.source["dev"]},
                ) as log:
                    for event in result.events:
                        log.log_event(event.get("kind", "event"),
                                      **{k: v for k, v in event.items() if k != "kind"})
                    log.finish(status="complete")
                best = result.selection.selected
                print(f"  B4-exhaustive (ceiling): best of 12 is "
                      f"{best.config_id if best else 'NONE ELIGIBLE'} "
                      f"intent {fmt(best.intent_macro_f1) if best else 'n/a'}")

        print(f"  cache now holds {client.cache.count_entries() if client.cache else 0} answers")
        print()

    print(f"client totals: {client.counter.as_dict()}")
    print("\nReminder: these are development selection scores. Nothing here is a "
          "reportable result until the frozen test runs at G11.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
