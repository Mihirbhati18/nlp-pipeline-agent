"""A small pipeline with two design switches, used by the C7 to C14 scripts.

It is c04_b1.py turned into functions, with two choices you can change:

  examples: "fixed"   = one example per intent, always the same
            "similar" = the 6 examples most similar to the request
  refusal:  "model"   = the model may answer none_of_the_above
            "cutoff"  = refuse before asking if the request is unlike every example

2 x 2 = 4 designs, a small version of the project's 12.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import f1_score
from sklearn.metrics.pairwise import cosine_similarity

from helpers import ask_model, load_jsonl, read_intent

EXAMPLES = load_jsonl("data/processed/P1/kshot.jsonl")
DEV = load_jsonl("data/processed/P1/dev.jsonl")
INTENTS = sorted({r["true_intent"] for r in EXAMPLES})
DESIGNS = [("fixed", "model"), ("fixed", "cutoff"), ("similar", "model"), ("similar", "cutoff")]
CUTOFF = 0.30   # similarity below this = refuse without asking the model

_vectorizer = TfidfVectorizer(ngram_range=(1, 2)).fit([r["utt"] for r in EXAMPLES])
_example_vectors = _vectorizer.transform([r["utt"] for r in EXAMPLES])


def similarities(request):
    """How similar the request is to each example (0 = nothing in common, 1 = identical)."""
    return cosine_similarity(_vectorizer.transform([request]), _example_vectors)[0]


def build_prompt(request, examples="fixed", show_examples=True, allow_refusal=True):
    if examples == "fixed":
        chosen = [next(r for r in EXAMPLES if r["true_intent"] == i) for i in INTENTS]
    else:
        best = similarities(request).argsort()[::-1][:6]
        chosen = [EXAMPLES[i] for i in best]
    lines = ["Label this request for a home assistant. Reply with JSON only.", "", "Allowed intents:"]
    lines += [f"- {i}" for i in INTENTS]
    if allow_refusal:
        lines.append("- none_of_the_above  (use this if the request is about anything else)")
    if show_examples:
        lines += ["", "Examples:"]
        lines += [f'Request: {e["utt"]}\nAnswer: {{"intent": "{e["true_intent"]}"}}' for e in chosen]
    lines += ["", f"Request: {request}", "Answer:"]
    return "\n".join(lines)


def answer(request, examples="fixed", refusal="model", show_examples=True):
    """One request through one design. Returns the intent, or none_of_the_above if refused."""
    if refusal == "cutoff" and similarities(request).max() < CUTOFF:
        return "none_of_the_above"                       # refused without asking the model
    prompt = build_prompt(request, examples, show_examples, allow_refusal=(refusal == "model"))
    return read_intent(ask_model(prompt)) or "BROKEN REPLY"


def evaluate(requests, **design):
    """Run a design over requests; return intent macro-F1 on the in-scope ones, and every answer."""
    answers = [answer(r["utt"], **design) for r in requests]
    gold = [r["true_intent"] for r in requests if r["in_scope"]]
    pred = [a for r, a in zip(requests, answers) if r["in_scope"]]
    return f1_score(gold, pred, labels=INTENTS, average="macro", zero_division=0), answers
