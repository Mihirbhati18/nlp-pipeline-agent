"""Run the B0 baseline on development data (part of G4).

B0 makes no model calls, so this needs no Ollama and can run at any time.

The threshold is tuned on the same development split it is then scored on, so
these development numbers are optimistically biased. That is the normal
meaning of a development score and it is labelled as such here. The figure
that counts is the frozen test run at G11, where the threshold is fixed
beforehand.

Usage:
    python scripts/run_b0.py                 # P1 and P2 development
    python scripts/run_b0.py --projects P1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analyzer.spec import load_cases, load_spec  # noqa: E402
from src.baselines.b0_tfidf import B0TfidfClassifier  # noqa: E402
from src.evaluation.runs import new_run  # noqa: E402
from src.evaluation.scorer import score  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="B0 TF-IDF baseline")
    parser.add_argument("--projects", nargs="+", default=["P1", "P2"])
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    print("B0: TF-IDF + logistic regression intent classifier, 0 model calls.")
    print("It extracts no entities by design, so its entity F1 is 0.")
    print("Development scores below are tuned-on-the-same-split and so optimistic.\n")

    for project in args.projects:
        spec = load_spec(project)
        pool = load_cases(spec.source["kshot"])
        dev = load_cases(spec.source["dev"])

        classifier = B0TfidfClassifier(labels=spec.intent_names, random_state=args.seed)
        classifier.fit(pool)
        choice = classifier.tune(dev)
        predictions = classifier.predict(dev)

        config = {
            **classifier.config(),
            "split": "dev",
            "project": project,
            "n_cases": len(dev),
            "pool_size": len(pool),
            "cache_enabled": False,
            "model": "none (no LLM)",
            "data_sources": spec.source,
            "bias_note": (
                "the out-of-scope threshold was tuned on this same development "
                "split, so these numbers are optimistic"
            ),
        }

        with new_run(
            project, "B0", args.seed, config,
            data_paths={"pool": spec.source["kshot"], "dev": spec.source["dev"]},
        ) as log:
            for case, prediction in zip(dev, predictions):
                log.log_prediction(
                    case_id=case["case_id"],
                    gold_intent=case["true_intent"],
                    gold_in_scope=case["in_scope"],
                    status=prediction.status,
                    predicted_intent=prediction.intent,
                    predicted_entities=[],
                    schema_valid_final=True,
                    cache_hit=False,
                )
            log.log_event("threshold_tuned", **choice.as_dict())

            metrics = score(
                dev, predictions, labels=spec.intent_names,
                design_cost={"logical_calls": 0, "physical_calls": 0, "wall_time_s": 0.0},
            )
            log.write_metrics(metrics)

            p = metrics["primary"]
            fmt = lambda v, d=3: "n/a" if v is None else f"{v:.{d}f}"  # noqa: E731
            summary = [
                f"# B0 on {project} (development)",
                "",
                f"TF-IDF + logistic regression, {len(pool)} training examples "
                f"(k=10 per intent), 0 model calls.",
                f"Out-of-scope threshold {choice.threshold:.4f}, chosen by "
                f"{choice.criterion}.",
                "",
                "| Metric | Value |",
                "|---|---|",
                f"| Intent macro-F1 | {fmt(p['intent_macro_f1'])} |",
                f"| Intent accuracy (in-scope) | {fmt(p['intent_accuracy_in_scope'])} |",
                f"| Entity span F1 | {fmt(p['entity_span_f1'])} (no entity extraction by design) |",
                f"| Out-of-scope precision / recall / F1 | {fmt(p['oos_precision'])} / "
                f"{fmt(p['oos_recall'])} / {fmt(p['oos_f1'])} |",
                f"| In-scope false rejection | {fmt(p['false_rejection_rate_in_scope'])} |",
                f"| Schema validity | {fmt(p['schema_validity_after_repair'])} "
                "(output is constructed, not generated) |",
                f"| Unsupported extraction rate | {p['unsupported_extraction_rate']} "
                "(N/A: nothing predicted) |",
                "",
                "These are development numbers with the threshold tuned on this same "
                "split, so they are optimistic. B0 is a sanity reference, not a "
                "state-of-the-art claim.",
                "",
            ]
            log.write_summary("\n".join(summary))
            log.finish(status="complete", n_cases=len(dev))

            print(f"--- {project} ({log.run_id}) ---")
            print(f"    threshold {choice.threshold:.4f} | intent macro-F1 "
                  f"{fmt(p['intent_macro_f1'])} | accuracy {fmt(p['intent_accuracy_in_scope'])}")
            print(f"    OOS P/R/F1 {fmt(p['oos_precision'])}/{fmt(p['oos_recall'])}/"
                  f"{fmt(p['oos_f1'])} | false rejection "
                  f"{fmt(p['false_rejection_rate_in_scope'])}")
            print(f"    entity F1 {fmt(p['entity_span_f1'])} (none extracted), "
                  f"unsupported rate {p['unsupported_extraction_rate']}")
            thin = {k: v["support"] for k, v in metrics["per_intent"].items() if v["support"] < 6}
            if thin:
                print(f"    thin per-intent support: {thin}")
            print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
