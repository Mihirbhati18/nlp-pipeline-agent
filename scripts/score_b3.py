"""Score B3's Kaggle predictions locally with the shared scorer (part of G5).

The notebook exports predictions and deliberately computes no metrics, so that
B3 is scored by exactly the same code as every other system. This script:

1. loads ``b3_predictions.json`` from the Kaggle run,
2. checks the predictions cover the frozen development split exactly,
3. tunes the out-of-scope threshold on development data by the same documented
   rule B0 uses (maximum softmax confidence; macro-F1 over intents plus the
   out-of-scope class),
4. applies the shared span rule and scorer,
5. writes one run folder per variant.

Usage:
    python scripts/score_b3.py --predictions b3_predictions.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analyzer.spec import load_cases, load_spec  # noqa: E402
from src.evaluation.runs import new_run  # noqa: E402
from src.evaluation.scorer import STATUS_OK, STATUS_OOS, Prediction, score  # noqa: E402
from src.evaluation.thresholds import tune_threshold  # noqa: E402

OOS_LABEL = "none_of_the_above"


def main() -> int:
    parser = argparse.ArgumentParser(description="Score B3 predictions from Kaggle")
    parser.add_argument("--predictions", required=True, help="b3_predictions.json")
    parser.add_argument("--split", default="dev", choices=["dev", "test"])
    args = parser.parse_args()

    payload = json.loads(Path(args.predictions).read_text(encoding="utf-8"))
    print(f"B3 predictions from {payload['model_name']} on {payload.get('device')}")
    print(f"hyperparameters: {payload['hyperparameters']}")
    print(f"split: {payload.get('split')}\n")

    if payload.get("split") != args.split:
        print(f"file says split={payload.get('split')!r} but --split={args.split!r}",
              file=sys.stderr)
        return 2

    failures = 0
    for key, run in payload["runs"].items():
        project, variant = run["project"], run["variant"]
        spec = load_spec(project)
        cases = load_cases(spec.source[args.split])
        by_id = {c["case_id"]: c for c in cases}

        predicted = run["predictions"]
        missing = sorted({c["case_id"] for c in cases} - {p["case_id"] for p in predicted})
        extra = sorted({p["case_id"] for p in predicted} - set(by_id))
        if missing or extra:
            failures += 1
            print(f"--- {key}: SPLIT MISMATCH ---")
            print(f"    {len(missing)} missing, {len(extra)} unexpected case IDs")
            print("    The notebook did not run on the frozen split. Not scored.")
            continue

        # The declared inventory must match what the notebook trained on.
        if run["intents"] != spec.intent_names:
            failures += 1
            print(f"--- {key}: INTENT INVENTORY MISMATCH, not scored ---")
            continue

        order = [p for p in sorted(predicted, key=lambda p: list(by_id).index(p["case_id"]))]
        confidences = [p["confidence"] for p in order]
        closed_set = [p["closed_set_intent"] for p in order]
        gold = [
            by_id[p["case_id"]]["true_intent"] if by_id[p["case_id"]]["in_scope"] else OOS_LABEL
            for p in order
        ]

        if args.split == "dev":
            choice = tune_threshold(confidences, closed_set, gold, spec.intent_names)
        else:
            # After the freeze the threshold is read from protocol.md, never retuned.
            print("test scoring requires the frozen threshold; add it to protocol.md first",
                  file=sys.stderr)
            return 2

        predictions = [
            Prediction(
                case_id=p["case_id"],
                status=STATUS_OOS if p["confidence"] < choice.threshold else STATUS_OK,
                intent=None if p["confidence"] < choice.threshold else p["closed_set_intent"],
                # A rejected request asserts no entities.
                entities=[] if p["confidence"] < choice.threshold else p["entities"],
                # Output is constructed from BIO tags, so it always conforms.
                schema_valid_raw=True,
                schema_valid_final=True,
            )
            for p in order
        ]

        config = {
            "system": variant,
            "split": args.split,
            "model": payload["model_name"],
            "model_digest": f"huggingface:{payload['model_name']}",
            "settings": payload["hyperparameters"],
            "seed": payload["seed"],
            "cache_enabled": False,
            "n_training_cases": run["n_training_cases"],
            "epochs": run["epochs"],
            "gpu": payload.get("device"),
            "torch_version": payload.get("torch_version"),
            "threshold": choice.as_dict(),
            "data_sources": spec.source,
            "comparison_role": (
                "matched comparison at k=10 per intent" if variant == "B3-k"
                else "UPPER REFERENCE ONLY, trained on the full split; never a matched comparison"
            ),
            "bias_note": (
                "the out-of-scope threshold was tuned on this same development split, "
                "so these development numbers are optimistic"
            ),
        }

        with new_run(
            project, variant, payload["seed"], config,
            data_paths={"pool": spec.source["kshot"], args.split: spec.source[args.split]},
        ) as log:
            for prediction, p in zip(predictions, order):
                case = by_id[prediction.case_id]
                log.log_prediction(
                    case_id=prediction.case_id,
                    gold_intent=case["true_intent"],
                    gold_in_scope=case["in_scope"],
                    status=prediction.status,
                    predicted_intent=prediction.intent,
                    predicted_entities=prediction.entities,
                    closed_set_intent=p["closed_set_intent"],
                    confidence=p["confidence"],
                    schema_valid_final=True,
                    cache_hit=False,
                )
            log.log_event("threshold_tuned", **choice.as_dict())

            metrics = score(
                cases, predictions, labels=spec.intent_names,
                design_cost={"logical_calls": 0, "physical_calls": 0,
                             "note": "B3 makes no LLM calls; its cost is GPU training time"},
            )
            log.write_metrics(metrics)

            p_m = metrics["primary"]
            fmt = lambda v, d=3: "n/a" if v is None else f"{v:.{d}f}"  # noqa: E731
            lines = [
                f"# {variant} on {project} ({args.split})",
                "",
                f"{payload['model_name']} fine-tuned on {run['n_training_cases']} cases "
                f"for {run['epochs']} epochs, seed {payload['seed']}, on "
                f"{payload.get('device')}.",
                "",
                f"**Role in the comparison:** {config['comparison_role']}",
                "",
                "| Metric | Value |",
                "|---|---|",
                f"| Intent macro-F1 | {fmt(p_m['intent_macro_f1'])} |",
                f"| Entity span F1 | {fmt(p_m['entity_span_f1'])} |",
                f"| Out-of-scope P / R / F1 | {fmt(p_m['oos_precision'])} / "
                f"{fmt(p_m['oos_recall'])} / {fmt(p_m['oos_f1'])} |",
                f"| In-scope false rejection | {fmt(p_m['false_rejection_rate_in_scope'])} |",
                f"| Unsupported extraction rate | {p_m['unsupported_extraction_rate']} |",
                "",
                f"Out-of-scope threshold {choice.threshold:.4f}, chosen by "
                f"{choice.criterion}.",
                "",
                config["bias_note"] + ".",
                "",
                "Scored with the shared `src/evaluation/scorer.py` and span rule, so these "
                "numbers are directly comparable with every other system's.",
                "",
            ]
            log.write_summary("\n".join(lines))
            log.finish(status="complete", n_cases=len(cases))

            print(f"--- {key} ({log.run_id}) ---")
            print(f"    training cases {run['n_training_cases']}, threshold "
                  f"{choice.threshold:.4f}")
            print(f"    intent macro-F1 {fmt(p_m['intent_macro_f1'])} | entity F1 "
                  f"{fmt(p_m['entity_span_f1'])} | OOS F1 {fmt(p_m['oos_f1'])}")
            print(f"    unsupported extraction {p_m['unsupported_extraction_rate']} | "
                  f"role: {variant == 'B3-k' and 'matched' or 'upper reference only'}")
            print()

    if failures:
        print(f"{failures} run(s) not scored", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
