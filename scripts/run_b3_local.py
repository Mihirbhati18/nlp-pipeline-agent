"""Train and score B3 locally on the laptop GPU (part of G5).

Replaces the Kaggle route: same recipe, same frozen splits, same shared
scorer, but one command and no manual file shuffling. Where B3 trained is
recorded in each run manifest, so the change is traceable.

For each development project it runs two variants:

- **B3-k**, trained on the k = 10 per intent pool - the matched comparison
- **B3-full**, trained on the project's full official train split - an upper
  reference only

Then it tunes the out-of-scope threshold on development data by the same rule
B0 uses, scores with the shared scorer and span rule, and writes a run folder
per variant.

The held-out project P3 is refused outright before the freeze, by the same
access guard the rest of the pipeline uses.

Usage:
    python scripts/run_b3_local.py                      # P1 and P2, both variants
    python scripts/run_b3_local.py --projects P1 --variants B3-k
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analyzer.access import HeldOutProjectLockedError, access_for  # noqa: E402
from src.analyzer.spec import load_cases, load_spec  # noqa: E402
from src.baselines.b3_encoder import B3Hyperparameters, B3Trainer  # noqa: E402
from src.evaluation.runs import new_run  # noqa: E402
from src.evaluation.scorer import STATUS_OK, STATUS_OOS, Prediction, score  # noqa: E402
from src.evaluation.thresholds import tune_threshold  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OOS_LABEL = "none_of_the_above"


def full_train_cases(spec, raw_path: Path) -> list[dict]:
    """The project's full official train split, for B3-full.

    Built from the raw dataset rather than the k-shot pool, using the same
    span converter, and restricted to the project's own domains and the
    official train partition.
    """
    from src.evaluation.massive import parse_annotation

    import json as _json

    manifest = _json.loads(
        (ROOT / f"data/manifests/{spec.project_id}.json").read_text(encoding="utf-8")
    )
    domains = set(manifest["domains"])
    cases: list[dict] = []
    with open(raw_path, encoding="utf-8") as handle:
        for line in handle:
            row = _json.loads(line)
            if row["scenario"] not in domains or row["partition"] != "train":
                continue
            cases.append({
                "case_id": f"massive-{row['id']}",
                "utt": row["utt"],
                "true_intent": row["intent"],
                "scenario": row["scenario"],
                "in_scope": True,
                "entities": [e.as_dict() for e in parse_annotation(row["utt"], row["annot_utt"])],
                "partition": "train",
            })
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Train and score B3 locally")
    parser.add_argument("--projects", nargs="+", default=["P1", "P2"])
    parser.add_argument("--variants", nargs="+", default=["B3-k", "B3-full"],
                        choices=["B3-k", "B3-full"])
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--epochs-kshot", type=int, default=30)
    parser.add_argument("--epochs-full", type=int, default=5)
    args = parser.parse_args()

    import torch

    hp = B3Hyperparameters(
        seed=args.seed, epochs_kshot=args.epochs_kshot, epochs_full=args.epochs_full
    )
    device = "cuda" if torch.cuda.is_available() else "cpu"
    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    print(f"B3 local training on {gpu} | torch {torch.__version__} | {hp.model_name}")
    print("B3-k is the matched comparison; B3-full is an upper reference only.\n")

    raw_path = ROOT / "data/raw/1.1/data/en-US.jsonl"
    if "B3-full" in args.variants and not raw_path.exists():
        print(f"missing {raw_path}; run scripts/prepare_data.py first", file=sys.stderr)
        return 2

    for project in args.projects:
        spec = load_spec(project)
        access = access_for(spec)
        try:
            pool = load_cases(access.train_path)
            dev = load_cases(access.dev_path)
        except HeldOutProjectLockedError as exc:
            print(f"--- {project}: SKIPPED ---\n    {exc}\n", file=sys.stderr)
            continue

        for variant in args.variants:
            if variant == "B3-k":
                training, epochs = pool, hp.epochs_kshot
            else:
                training, epochs = full_train_cases(spec, raw_path), hp.epochs_full

            print(f"--- {project} {variant}: {len(training)} training cases, "
                  f"{epochs} epochs ---", flush=True)
            started = time.perf_counter()
            trainer = B3Trainer(
                intents=list(spec.intent_names),
                entity_types=list(spec.entity_type_names),
                hyperparameters=hp,
                device=device,
            )
            try:
                trainer.fit(training, epochs)
            except torch.cuda.OutOfMemoryError:
                print(f"    CUDA out of memory on {gpu}. Retry with a smaller "
                      f"--epochs or use the Kaggle notebook instead.", file=sys.stderr)
                trainer.release()
                return 1
            raw_predictions = trainer.predict(dev)
            train_seconds = time.perf_counter() - started
            trainer.release()

            gold = [
                c["true_intent"] if c["in_scope"] else OOS_LABEL
                for c in dev
            ]
            choice = tune_threshold(
                [p["confidence"] for p in raw_predictions],
                [p["closed_set_intent"] for p in raw_predictions],
                gold,
                spec.intent_names,
            )
            predictions = [
                Prediction(
                    case_id=p["case_id"],
                    status=STATUS_OOS if p["confidence"] < choice.threshold else STATUS_OK,
                    intent=None if p["confidence"] < choice.threshold else p["closed_set_intent"],
                    entities=[] if p["confidence"] < choice.threshold else p["entities"],
                    # Output is constructed from BIO tags, so it always conforms.
                    schema_valid_raw=True,
                    schema_valid_final=True,
                )
                for p in raw_predictions
            ]

            config = {
                "system": variant,
                "split": "dev",
                "model": hp.model_name,
                "model_digest": f"huggingface:{hp.model_name}",
                "settings": hp.as_dict(),
                "epochs": epochs,
                "n_training_cases": len(training),
                "training_seconds": round(train_seconds, 1),
                "device": gpu,
                "torch_version": torch.__version__,
                "cache_enabled": False,
                "threshold": choice.as_dict(),
                "data_sources": spec.source,
                "data_access": access.as_dict(),
                "trained_where": "laptop GPU (local), not Kaggle",
                "comparison_role": (
                    "matched comparison at k=10 per intent" if variant == "B3-k"
                    else "UPPER REFERENCE ONLY, trained on the full split; "
                         "never a matched comparison"
                ),
                "bias_note": (
                    "the out-of-scope threshold was tuned on this same development "
                    "split, so these development numbers are optimistic"
                ),
            }

            with new_run(
                project, variant, args.seed, config,
                data_paths={"pool": spec.source["kshot"], "dev": spec.source["dev"]},
            ) as log:
                for prediction, raw in zip(predictions, raw_predictions):
                    case = next(c for c in dev if c["case_id"] == prediction.case_id)
                    log.log_prediction(
                        case_id=prediction.case_id,
                        gold_intent=case["true_intent"],
                        gold_in_scope=case["in_scope"],
                        status=prediction.status,
                        predicted_intent=prediction.intent,
                        predicted_entities=prediction.entities,
                        closed_set_intent=raw["closed_set_intent"],
                        confidence=raw["confidence"],
                        schema_valid_raw=True,
                        schema_valid_final=True,
                        cache_hit=False,
                    )
                log.log_event("threshold_tuned", **choice.as_dict())
                log.log_event("training", n_cases=len(training), epochs=epochs,
                              seconds=round(train_seconds, 1), device=gpu)

                metrics = score(
                    dev, predictions, labels=spec.intent_names,
                    design_cost={"logical_calls": 0, "physical_calls": 0,
                                 "training_seconds": round(train_seconds, 1),
                                 "note": "B3 makes no LLM calls; its cost is GPU training time"},
                )
                log.write_metrics(metrics)

                p = metrics["primary"]
                fmt = lambda v, d=3: "n/a" if v is None else f"{v:.{d}f}"  # noqa: E731
                log.write_summary("\n".join([
                    f"# {variant} on {project} (development)",
                    "",
                    f"{hp.model_name} fine-tuned on {len(training)} cases for {epochs} "
                    f"epochs, seed {args.seed}, on {gpu} in {train_seconds:.0f} s.",
                    "",
                    f"**Role in the comparison:** {config['comparison_role']}",
                    "",
                    "| Metric | Value |",
                    "|---|---|",
                    f"| Intent macro-F1 | {fmt(p['intent_macro_f1'])} |",
                    f"| Entity span F1 | {fmt(p['entity_span_f1'])} |",
                    f"| Out-of-scope P / R / F1 | {fmt(p['oos_precision'])} / "
                    f"{fmt(p['oos_recall'])} / {fmt(p['oos_f1'])} |",
                    f"| In-scope false rejection | {fmt(p['false_rejection_rate_in_scope'])} |",
                    f"| Unsupported extraction rate | {p['unsupported_extraction_rate']} |",
                    "",
                    f"Out-of-scope threshold {choice.threshold:.4f}, chosen by "
                    f"{choice.criterion}.",
                    "",
                    config["bias_note"] + ".",
                    "",
                    "Scored with the shared scorer and span rule, so these numbers are "
                    "directly comparable with every other system's.",
                    "",
                ]))
                log.finish(status="complete", n_cases=len(dev))

                print(f"    {log.run_id}: intent macro-F1 {fmt(p['intent_macro_f1'])} | "
                      f"entity F1 {fmt(p['entity_span_f1'])} | OOS F1 {fmt(p['oos_f1'])} | "
                      f"{train_seconds:.0f}s")
                print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
