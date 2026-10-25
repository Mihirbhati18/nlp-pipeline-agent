"""C4 yourself: build a one-prompt AI pipeline (like B1) and score it.

Needs the Ollama app open.  Run:  python diy/c04_b1.py          (all 100 requests, about a minute)
                                   python diy/c04_b1.py 20       (only the first 20)
"""

import sys

from sklearn.metrics import accuracy_score, f1_score

from helpers import ask_model, load_jsonl, read_intent

examples = load_jsonl("data/processed/P1/kshot.jsonl")
dev = load_jsonl("data/processed/P1/dev.jsonl")
limit = int(sys.argv[1]) if len(sys.argv) > 1 else len(dev)
dev = dev[:limit]

# 1. The list of intents the app supports, and one worked example for each.
intents = sorted({r["true_intent"] for r in examples})
one_example_each = [next(r for r in examples if r["true_intent"] == i) for i in intents]


# 2. Build the prompt: instructions, the allowed intents, the examples, then the request.
def build_prompt(request):
    lines = ["Label this request for a home assistant. Reply with JSON only.", "", "Allowed intents:"]
    lines += [f"- {i}" for i in intents]
    lines += ["- none_of_the_above  (use this if the request is about anything else)", "", "Examples:"]
    lines += [f'Request: {e["utt"]}\nAnswer: {{"intent": "{e["true_intent"]}"}}' for e in one_example_each]
    lines += ["", f"Request: {request}", "Answer:"]
    return "\n".join(lines)


# 3. Ask the model about every development request and read its answer.
correct, answered = [], []
for number, r in enumerate(dev, 1):
    intent = read_intent(ask_model(build_prompt(r["utt"])))
    correct.append(r["true_intent"] if r["in_scope"] else "none_of_the_above")
    answered.append(intent or "BROKEN REPLY")
    if number <= 5:
        print(f'{r["utt"]!r:45} correct: {correct[-1]:20} model: {answered[-1]}')

# 4. Score: intent F1 over the in-scope requests (refusing one counts as wrong),
#    and how many off-topic requests were correctly refused.
pairs = [(c, a) for c, a in zip(correct, answered) if c != "none_of_the_above"]
gold, pred = [c for c, _ in pairs], [a for _, a in pairs]
off_topic = [(c, a) for c, a in zip(correct, answered) if c == "none_of_the_above"]
print("\nrequests:", len(dev))
print("intent accuracy:", round(accuracy_score(gold, pred), 3))
print("intent macro-F1:", round(f1_score(gold, pred, labels=intents, average="macro", zero_division=0), 3))
print("off-topic requests correctly refused:", sum(a == c for c, a in off_topic), "of", len(off_topic))
