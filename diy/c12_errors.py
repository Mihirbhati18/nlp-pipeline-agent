"""C12 yourself: error analysis. Sort a system's mistakes into kinds and count them.

Uses the answers the project saved for A1 on P2. No model needed.
Run:  python diy/c12_errors.py
"""

from collections import Counter
from pathlib import Path

from helpers import load_jsonl

folder = sorted(Path("runs").glob("*_P2_A1-selected_0"))[-1]
rows = load_jsonl(folder / "predictions.jsonl")
requests = {r["case_id"]: r["utt"] for r in load_jsonl("data/processed/P2/dev.jsonl")}

kinds = Counter()
mix_ups = Counter()
for r in rows:
    request = requests[r["case_id"]]
    if not r["gold_in_scope"]:
        if r["status"] == "ok":                  # should have been refused, but was answered
            kinds["answered an off-topic request"] += 1
            print(f"answered off-topic: {request!r} -> {r['predicted_intent']}")
    elif r["status"] == "oos":                   # should have been answered, but was refused
        kinds["wrongly refused"] += 1
        print(f"wrongly refused:    {request!r} (correct: {r['gold_intent']})")
    elif r["status"] != "ok":
        kinds["broken reply"] += 1
    elif r["predicted_intent"] != r["gold_intent"]:
        kinds["wrong intent"] += 1
        mix_ups[(r["gold_intent"], r["predicted_intent"])] += 1
        print(f"wrong intent:       {request!r} (correct: {r['gold_intent']}, said: {r['predicted_intent']})")

print("\ncounts:", dict(kinds))
print("most common mix-ups:", mix_ups.most_common(3))
