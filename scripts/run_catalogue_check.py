"""G4 completion check: every catalogue configuration runs on real cases.

The gate condition from PROJECT_PLAN.md section 7 is that all 12 configurations
run on 10 P1/P2 development cases. This script does exactly that and reports,
per configuration, whether it produced a scoreable result.

It is a *plumbing* check, not an experiment: 10 cases cannot measure quality,
and the script says so in its output. Scores are printed only to show the
pipeline end to end.

Usage:
    python scripts/run_catalogue_check.py --model qwen2.5:3b
    python scripts/run_catalogue_check.py --model qwen2.5:3b --n 10 --projects P1 P2
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analyzer.spec import load_cases, load_spec  # noqa: E402
from src.evaluation.scorer import score  # noqa: E402
from src.evaluation.thresholds import tune_binary_threshold  # noqa: E402
from src.llm.client import make_client, ollama_version  # noqa: E402
from src.pipelines.catalogue import CATALOGUE  # noqa: E402
from src.pipelines.examples import ExampleSelector  # noqa: E402
from src.pipelines.catalogue import ConfigRunner  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="G4 catalogue plumbing check")
    parser.add_argument("--model", required=True, help="Ollama model, e.g. qwen2.5:3b")
    parser.add_argument("--n", type=int, default=10, help="development cases per project")
    parser.add_argument("--projects", nargs="+", default=["P1", "P2"])
    parser.add_argument("--host", default="http://127.0.0.1:11434")
    args = parser.parse_args()

    try:
        version = ollama_version(args.host)
    except Exception as exc:  # noqa: BLE001
        print(f"Cannot reach Ollama at {args.host}: {exc}", file=sys.stderr)
        return 2

    client = make_client(args.model, host=args.host)
    print(f"Ollama {version}, model {args.model} (digest {client.model_digest[:19] or 'unknown'})")
    print(f"{args.n} development cases per project. This is a plumbing check, not a result.\n")

    failures = 0
    for project in args.projects:
        spec = load_spec(project)
        pool = load_cases(spec.source["kshot"])
        dev_all = load_cases(spec.source["dev"])
        # Keep both in-scope and out-of-scope cases in the sample, so the
        # out-of-scope path is exercised too.
        in_scope = [c for c in dev_all if c["in_scope"]][: max(1, args.n - 2)]
        oos = [c for c in dev_all if not c["in_scope"]][:2]
        cases = in_scope + oos

        selector = ExampleSelector(pool)
        confidences = [selector.max_similarity(c["utt"]) for c in dev_all]
        threshold = tune_binary_threshold(confidences, [c["in_scope"] for c in dev_all])

        print(f"--- {project} {spec.name}: {len(cases)} cases "
              f"({len(in_scope)} in-scope + {len(oos)} out-of-scope) ---")
        print(f"    TF-IDF out-of-scope threshold tuned on the full dev split: "
              f"{threshold.threshold:.4f} (dev binary F1 {threshold.macro_f1:.3f})")
        print(f"    {'configuration':22} {'intentF1':>9} {'entF1':>7} {'schema':>7} "
              f"{'fail':>5} {'calls':>6}  status")

        for config in CATALOGUE:
            runner = ConfigRunner(
                config=config, spec=spec, client=client, selector=selector,
                oos_threshold=threshold.threshold,
            )
            predictions = []
            logical = physical = 0
            error: str | None = None
            try:
                for case in cases:
                    outcome = runner.run_case(case)
                    predictions.append(outcome.prediction)
                    logical += outcome.logical_calls
                    physical += outcome.physical_calls
            except Exception as exc:  # noqa: BLE001
                error = f"{type(exc).__name__}: {exc}"

            if error:
                failures += 1
                print(f"    {config.config_id:22} {'-':>9} {'-':>7} {'-':>7} "
                      f"{'-':>5} {'-':>6}  CRASHED {error}")
                continue

            metrics = score(cases, predictions, labels=spec.intent_names)
            p = metrics["primary"]
            fmt = lambda v: "n/a" if v is None else f"{v:.3f}"  # noqa: E731
            # The gate condition is that every configuration *runs*. A recorded
            # runtime failure is data about that configuration, not a gate
            # failure: the plan requires failures to stay in the denominators
            # rather than be eliminated. Only a crash means a configuration
            # cannot run at all.
            note = "ok"
            if p["runtime_failure_rate"]:
                note = f"ran, {p['runtime_failure_counts']} recorded"
            print(f"    {config.config_id:22} {fmt(p['intent_macro_f1']):>9} "
                  f"{fmt(p['entity_span_f1']):>7} {fmt(p['schema_validity_after_repair']):>7} "
                  f"{fmt(p['runtime_failure_rate']):>5} {logical:>6}  {note}")
        print()

    print(f"cache entries now: {client.cache.count_entries() if client.cache else 0}")
    print(f"client totals: {client.counter.as_dict()}")
    if failures:
        print(f"\n{failures} configuration(s) CRASHED and could not run", file=sys.stderr)
        return 1
    print("\nGate condition met: all 12 configurations ran on every project.")
    print("Any recorded runtime failures above are properties of those "
          "configurations and stay in every denominator; they are not gate failures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
