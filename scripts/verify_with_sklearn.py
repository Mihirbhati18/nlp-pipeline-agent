"""Recompute the headline metrics with scikit-learn, independently of our scorer.

Our own scorer (`src/evaluation/scorer.py`) is tested against hand-computed
fixtures, but a sceptical reader may still ask whether it computes F1 the
standard way. This script answers that by recomputing, from each run's saved
predictions, the metrics scikit-learn can compute directly, using only
scikit-learn's own functions:

- intent macro-F1 over in-scope requests, on the project's declared intents
  (`sklearn.metrics.f1_score(average="macro", labels=...)`)
- in-scope intent accuracy (`sklearn.metrics.accuracy_score`)
- out-of-scope precision, recall and F1, out-of-scope as the positive class
  (`sklearn.metrics.precision_recall_fscore_support(average="binary")`)

It then compares each with the value recorded in the run's `metrics.json`.
Nothing from our scorer is imported. Entity span F1 is not covered here,
because scikit-learn has no span-level F1; it is covered by the hand-computed
unit tests and by `scripts/reproduce_metrics.py`.

Usage:
    python scripts/verify_with_sklearn.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support

ROOT = Path(__file__).resolve().parents[1]
OOS = "none_of_the_above"
FAILED = "__no_answer__"  # an invalid, failed or missing reply asserts no label


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def project_cases(project: str, variant: str | None) -> list[dict]:
    manifest = json.loads((ROOT / "data" / "manifests" / f"{project}.json").read_text(encoding="utf-8"))
    cases = load_jsonl(ROOT / "data" / "processed" / project / "dev.jsonl")
    if variant:
        sys.path.insert(0, str(ROOT / "scripts"))
        from run_robustness import perturb  # rewrites only the request text; labels unchanged

        cases = perturb(cases, variant)
    return cases, manifest


def predicted_label(row: dict) -> str:
    if row["status"] == "oos":
        return OOS
    if row["status"] == "ok" and row.get("predicted_intent"):
        return row["predicted_intent"]
    return FAILED


def check(run: Path) -> tuple[str, str]:
    config = json.loads((run / "config.json").read_text(encoding="utf-8"))
    project = config.get("project")
    if project not in ("P1", "P2") or config.get("split", "dev") != "dev":
        return "skipped", "not a development run of P1 or P2"
    recorded = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    cases, _ = project_cases(project, config.get("variant"))
    by_id = {r["case_id"]: r for r in load_jsonl(run / "predictions.jsonl")}
    labels = recorded["intent_label_set"]

    in_scope = [c for c in cases if c["in_scope"]]
    y_true = [c["true_intent"] for c in in_scope]
    y_pred = [predicted_label(by_id[c["case_id"]]) if c["case_id"] in by_id else FAILED for c in in_scope]

    ours = recorded["primary"]
    theirs = {
        "intent_macro_f1": f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0),
        "intent_accuracy_in_scope": accuracy_score(y_true, y_pred),
    }
    oos_true = [not c["in_scope"] for c in cases]
    oos_pred = [by_id.get(c["case_id"], {}).get("status") == "oos" for c in cases]
    p, r, f, _ = precision_recall_fscore_support(oos_true, oos_pred, average="binary", zero_division=0)
    theirs.update({"oos_precision": p, "oos_recall": r, "oos_f1": f})

    bad = [f"{k}: ours {ours[k]:.6f}, sklearn {v:.6f}" for k, v in theirs.items()
           if not math.isclose(ours[k], v, abs_tol=1e-9)]
    if bad:
        return "DIFFERENT", "; ".join(bad)
    return "agrees", (f"intent F1 {theirs['intent_macro_f1']:.3f}, accuracy {theirs['intent_accuracy_in_scope']:.3f}, "
                      f"OOS F1 {theirs['oos_f1']:.3f}")


def main() -> int:
    counts: dict[str, int] = {}
    for run in sorted(p for p in (ROOT / "runs").iterdir() if p.is_dir()):
        if not (run / "predictions.jsonl").is_file() or not (run / "metrics.json").is_file():
            continue
        status, detail = check(run)
        counts[status] = counts.get(status, 0) + 1
        print(f"{status:10} {run.name:44} {detail}")
    print(f"\n{counts}")
    print("Each 'agrees' means scikit-learn computed exactly the number our scorer recorded "
          "(5 metrics per run, to 9 decimal places).")
    return 1 if counts.get("DIFFERENT") else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
