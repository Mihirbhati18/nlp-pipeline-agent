"""C15 yourself: check a recorded result by recomputing it from the saved answers.

No model needed.  Run:  python diy/c15_check.py
                        python diy/c15_check.py 20261013_0110_P1_B1_0      (any run folder)
"""

import json
import sys
from pathlib import Path

from sklearn.metrics import accuracy_score, f1_score

from helpers import load_jsonl

folder = Path("runs") / sys.argv[1] if len(sys.argv) > 1 else sorted(Path("runs").glob("*_P1_A2-selected_0"))[-1]
recorded = json.loads((folder / "metrics.json").read_text(encoding="utf-8"))
rows = [r for r in load_jsonl(folder / "predictions.jsonl") if r["gold_in_scope"]]

gold = [r["gold_intent"] for r in rows]
said = [r["predicted_intent"] if r["status"] == "ok" else "REFUSED" for r in rows]

my_f1 = f1_score(gold, said, labels=recorded["intent_label_set"], average="macro", zero_division=0)
my_accuracy = accuracy_score(gold, said)
print("run:", folder.name)
print(f"intent macro-F1  recorded {recorded['primary']['intent_macro_f1']:.6f}   recomputed {my_f1:.6f}")
print(f"accuracy         recorded {recorded['primary']['intent_accuracy_in_scope']:.6f}   recomputed {my_accuracy:.6f}")
same = abs(my_f1 - recorded["primary"]["intent_macro_f1"]) < 1e-9
print("-> the same" if same else "-> DIFFERENT")
