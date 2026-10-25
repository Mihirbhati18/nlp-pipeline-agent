"""C7 yourself: random search. Pick 4 of the 12 designs at random, keep the best, repeat for 5 seeds.

Uses the scores of all 12 designs that the project already measured, so it needs no model.
Run:  python diy/c07_random_search.py
"""

import json
import random
from math import comb
from pathlib import Path

# 1. The development score of each of the 12 designs on P1 (measured by B4-exhaustive).
folder = sorted(Path("runs").glob("*_P1_B4-exhaustive_0"))[-1]
ranking = json.loads((folder / "config.json").read_text(encoding="utf-8"))["selection"]["ranking"]
score_of = {row["config_id"]: row["intent_macro_f1"] for row in ranking}
designs = sorted(score_of)
for d in designs:
    print(f"  {d:22} {score_of[d]:.3f}")

# 2. Random search: draw 4 designs, keep the best of those 4. Do it with 5 different seeds.
winners = []
for seed in range(5):
    random.seed(seed)
    drawn = random.sample(designs, 4)
    best = max(drawn, key=lambda d: score_of[d])
    winners.append(score_of[best])
    print(f"seed {seed}: drew {drawn} -> kept {best} ({score_of[best]:.3f})")

print("average of the 5 winners:", round(sum(winners) / len(winners), 3))
print("best possible (all 12):", round(max(score_of.values()), 3))

# 3. Why random search does well here: the chance that 4 random picks include the single best design.
chance = 1 - comb(11, 4) / comb(12, 4)
print(f"chance 4 random picks include the best design: {chance:.0%}")
good = [d for d in designs if score_of[d] >= max(score_of.values()) - 0.06]
print(f"designs within 0.06 of the best: {len(good)} of 12, so a random 4 usually contains a good one")
