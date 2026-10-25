"""C10 yourself: a bootstrap confidence interval for "is A1 really better than B1?".

Uses the answers the project saved for A1 and B1 on P1. No model needed.
Run:  python diy/c10_bootstrap.py
"""

import random
from pathlib import Path

from sklearn.metrics import f1_score

from helpers import load_jsonl


def intent_answers(run_pattern):
    """Each in-scope request's correct intent and the system's answer, from a saved run."""
    folder = sorted(Path("runs").glob(run_pattern))[-1]
    rows = [r for r in load_jsonl(folder / "predictions.jsonl") if r["gold_in_scope"]]
    said = [r["predicted_intent"] if r["status"] == "ok" else "REFUSED" for r in rows]
    return [r["gold_intent"] for r in rows], said


gold, a1 = intent_answers("*_P1_A1-selected_0")
_, b1 = intent_answers("*_P1_B1_0")
labels = sorted(set(gold))


def macro_f1(indices, answers):
    return f1_score([gold[i] for i in indices], [answers[i] for i in indices],
                    labels=labels, average="macro", zero_division=0)


everyone = list(range(len(gold)))
print(f"real difference (A1 - B1): {macro_f1(everyone, a1) - macro_f1(everyone, b1):+.3f}")

# 1000 times: draw a pretend set of the same size, with repeats allowed, and score both on it.
random.seed(0)
differences = []
for _ in range(1000):
    drawn = [random.randrange(len(gold)) for _ in everyone]
    differences.append(macro_f1(drawn, a1) - macro_f1(drawn, b1))

differences.sort()
low, high = differences[25], differences[974]          # cut 2.5% off each end: the middle 95%
print(f"95% confidence interval: [{low:+.3f}, {high:+.3f}]")
print(f"A1 better in {sum(d > 0 for d in differences) / 10:.0f}% of the 1000 draws")
print("includes 0, so it could be luck" if low <= 0 <= high else "entirely above 0, so it is unlikely to be luck")
