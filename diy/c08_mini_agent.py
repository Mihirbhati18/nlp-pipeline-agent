"""C8 yourself: a mini agent that chooses its own pipeline design.

The AI ranks the 4 designs of mini_pipeline.py, the two it likes best are
tested, it sees their scores and picks one more, and the best of the three wins.
This is the same idea as the project's Architect, at a small scale.

Needs the Ollama app open. About a minute.  Run:  python diy/c08_mini_agent.py
"""

import json

from helpers import ask_model
from mini_pipeline import DESIGNS, DEV, evaluate

requests = DEV[:40]                        # a smaller set keeps it quick
names = [f"{e}-{r}" for e, r in DESIGNS]   # e.g. "similar-model"
EXPLAIN = (
    "examples=fixed: one example per intent, always the same. "
    "examples=similar: the 6 examples most similar to each request. "
    "refusal=model: the model may answer none_of_the_above. "
    "refusal=cutoff: requests unlike every example are refused before asking the model."
)

# 1. The agent plans: ask the AI to rank the 4 designs for this project, with reasons.
plan = ask_model(
    f"You design a pipeline for a home assistant that sets alarms and controls lights and plugs. "
    f"Users phrase things many ways; off-topic requests must be refused. Designs: {names}. {EXPLAIN} "
    'Rank all 4 designs from best to worst. Reply as JSON: {"ranking": [...], "why": "..."}'
)
plan = json.loads(plan)
print("AI's ranking, as it wrote it:", plan.get("ranking"))
ranking = [d for d in plan.get("ranking", []) if d in names] or names   # ignore anything invented
print("after removing names that are not real designs:", ranking)
print("AI's reason:", plan.get("why"))

# 2. Test the two designs it ranked highest.
scores = {}
for name in ranking[:2]:
    examples, refusal = name.split("-")
    scores[name], _ = evaluate(requests, examples=examples, refusal=refusal)
    print(f"tested {name}: intent macro-F1 {scores[name]:.3f}")

# 3. The agent revises: show it the scores and let it pick one more design to test.
remaining = [n for n in names if n not in scores]
revision = json.loads(ask_model(
    f"You tested these designs: {json.dumps({k: round(v, 3) for k, v in scores.items()})}. {EXPLAIN} "
    f'Which ONE of {remaining} should be tested next? Reply as JSON: {{"next": "...", "why": "..."}}'
))
next_design = revision.get("next") if revision.get("next") in remaining else remaining[0]
examples, refusal = next_design.split("-")
scores[next_design], _ = evaluate(requests, examples=examples, refusal=refusal)
print(f"AI chose next: {next_design} ({revision.get('why')})")
print(f"tested {next_design}: intent macro-F1 {scores[next_design]:.3f}")

# 4. Select: keep the best-scoring design.
best = max(scores, key=scores.get)
print(f"\nselected: {best} with intent macro-F1 {scores[best]:.3f}")
