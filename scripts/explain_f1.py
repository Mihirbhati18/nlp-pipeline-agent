"""Show, step by step, how one run's intent F1 is calculated from the real files.

This is the hand calculation done on real data, so every number in a result
can be traced back to individual requests:

  1. reads the correct answers  (data/processed/<project>/dev.jsonl)
  2. reads the system's answers (runs/<run>/predictions.jsonl)
  3. prints them side by side, one request per line
  4. counts TP, FP and FN for each intent, naming the requests behind each count
  5. works out precision, recall and F1 for each intent, showing the sum
  6. averages them into macro-F1 and compares with the run's metrics.json
     and with scikit-learn

It also saves the side-by-side table as a CSV file that opens in Excel, so the
counting can be checked by hand. It changes nothing in the project.

Usage:
    python scripts/explain_f1.py                                   # A2 on P1
    python scripts/explain_f1.py --run 20261013_0110_P1_B1_0        # any run with predictions
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from sklearn.metrics import f1_score

ROOT = Path(__file__).resolve().parents[1]
OOS = "none_of_the_above"


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def said(row: dict | None) -> str:
    """What the system answered, in words."""
    if row is None:
        return "(no answer)"
    if row["status"] == "oos":
        return "REFUSED (off-topic)"
    if row["status"] == "ok":
        return row["predicted_intent"]
    return f"(broken reply: {row['status']})"


def main() -> int:
    parser = argparse.ArgumentParser(description="Explain one run's intent F1 step by step")
    parser.add_argument("--run", help="run folder name (default: the latest P1 A2-selected run)")
    parser.add_argument("--rows", type=int, default=15, help="how many request lines to print (all go in the CSV)")
    args = parser.parse_args()

    run = ROOT / "runs" / args.run if args.run else sorted((ROOT / "runs").glob("*_P1_A2-selected_0"))[-1]
    config = json.loads((run / "config.json").read_text(encoding="utf-8"))
    project = config.get("project") or run.name.split("_")[2]
    gold_path = ROOT / "data" / "processed" / project / "dev.jsonl"
    pred_path = run / "predictions.jsonl"
    if not pred_path.is_file():
        print(f"{run.name} has no predictions.jsonl, so it cannot be explained request by request.")
        return 1

    cases = load_jsonl(gold_path)
    answers = {row["case_id"]: row for row in load_jsonl(pred_path)}
    recorded = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    labels = recorded["intent_label_set"]

    print("=" * 78)
    print(f"STEP 1. Correct answers:  {gold_path.relative_to(ROOT)}  ({len(cases)} requests)")
    print(f"STEP 2. System's answers: {pred_path.relative_to(ROOT)}")
    in_scope = [c for c in cases if c["in_scope"]]
    print(f"        {len(in_scope)} requests are in scope (they have a real intent); "
          f"{len(cases) - len(in_scope)} are off-topic and are scored")
    print("        separately (off-topic F1), so intent F1 uses only the in-scope ones.")
    print("=" * 78)

    # STEP 3: side by side
    rows = []
    for number, case in enumerate(in_scope, 1):
        answer = said(answers.get(case["case_id"]))
        right = answer == case["true_intent"]
        # Robustness runs log the rewritten request they were asked; show that one.
        utt = (answers.get(case["case_id"]) or {}).get("utt", case["utt"])
        rows.append((number, case["case_id"], utt, case["true_intent"], answer, right))

    print(f"\nSTEP 3. Side by side (first {min(args.rows, len(rows))} of {len(rows)}; "
          "all of them are in the CSV file)\n")
    print(f"  {'#':>3}  {'request':38} {'correct intent':20} {'system said':22} right?")
    for number, _, utt, gold, answer, right in rows[: args.rows]:
        print(f"  {number:>3}  {utt[:37]:38} {gold[:19]:20} {answer[:21]:22} {'yes' if right else 'NO'}")

    csv_path = ROOT / "reports" / f"f1_explained_{run.name}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["#", "case_id", "request", "correct intent", "system said", "right?"])
        for number, case_id, utt, gold, answer, right in rows:
            writer.writerow([number, case_id, utt, gold, answer, "yes" if right else "no"])
    print(f"\n  Saved all {len(rows)} lines to {csv_path.relative_to(ROOT)} (open it in Excel).")

    # STEP 4 and 5: per intent
    print("\nSTEP 4 and 5. For each intent, count and calculate\n")
    print("  TP = system said this intent and it was right")
    print("  FP = system said this intent but the correct one was different")
    print("  FN = this was the correct intent but the system said something else")
    print("  precision = TP/(TP+FP)   recall = TP/(TP+FN)   F1 = 2*P*R/(P+R)\n")
    f1s = {}
    for label in labels:
        tp = [n for n, _, _, g, a, _ in rows if g == label and a == label]
        fp = [n for n, _, _, g, a, _ in rows if a == label and g != label]
        fn = [n for n, _, _, g, a, _ in rows if g == label and a != label]
        precision = len(tp) / (len(tp) + len(fp)) if tp or fp else 0.0
        recall = len(tp) / (len(tp) + len(fn)) if tp or fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        f1s[label] = f1

        def names(numbers):
            return "" if not numbers else " (#" + ", #".join(map(str, numbers[:6])) + (", ..." if len(numbers) > 6 else "") + ")"

        print(f"  {label}")
        print(f"     TP {len(tp)}{names(tp)}   FP {len(fp)}{names(fp)}   FN {len(fn)}{names(fn)}")
        print(f"     precision {len(tp)}/{len(tp) + len(fp)} = {precision:.3f}   "
              f"recall {len(tp)}/{len(tp) + len(fn)} = {recall:.3f}   F1 = {f1:.3f}")

    # STEP 6: average and compare
    macro = sum(f1s.values()) / len(f1s)
    sum_text = " + ".join(f"{v:.3f}" for v in f1s.values())
    correct = sum(1 for r in rows if r[5])
    y_true = [r[3] for r in rows]
    y_pred = [r[4] for r in rows]
    sk = f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)
    print("\nSTEP 6. Average the F1 of every intent (macro-F1)\n")
    print(f"  ({sum_text}) / {len(f1s)}")
    print(f"  = {macro:.4f}")
    print(f"\n  accuracy = {correct} right / {len(rows)} = {correct / len(rows):.4f}")
    print("\n  Check against the other two ways of computing it:")
    print(f"    recorded in {run.name}/metrics.json : {recorded['primary']['intent_macro_f1']:.4f}")
    print(f"    scikit-learn f1_score              : {sk:.4f}")
    same = abs(macro - recorded["primary"]["intent_macro_f1"]) < 1e-9 and abs(macro - sk) < 1e-9
    print(f"    -> {'all three are the same' if same else 'THEY DIFFER'}")
    print("=" * 78)
    return 0 if same else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
