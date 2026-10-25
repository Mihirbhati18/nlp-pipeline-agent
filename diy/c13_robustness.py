"""C13 yourself: robustness. Make the requests messy and see whether the score holds.

Tests the word-matching baseline from c03 (with the same refusal rule), so it needs no model and runs in seconds.
Run:  python diy/c13_robustness.py
"""

import random

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score

from helpers import load_jsonl

examples = load_jsonl("data/processed/P1/kshot.jsonl")
dev = [r for r in load_jsonl("data/processed/P1/dev.jsonl") if r["in_scope"]]


def add_typo(sentence, rng):
    """Swap two neighbouring letters in one word of 4 or more letters."""
    words = sentence.split()
    long_words = [i for i, w in enumerate(words) if len(w) >= 4]
    if not long_words:
        return sentence
    i = rng.choice(long_words)
    w = words[i]
    j = rng.randrange(len(w) - 1)
    words[i] = w[:j] + w[j + 1] + w[j] + w[j + 2:]
    return " ".join(words)


def add_filler(sentence, rng):
    return "hey, could you please " + sentence + ", thanks"


# Train the word-matching classifier once, as in c03.
vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
classifier = LogisticRegression(max_iter=2000, C=10.0, random_state=0)
classifier.fit(vectorizer.fit_transform([r["utt"] for r in examples]), [r["true_intent"] for r in examples])
labels = sorted({r["true_intent"] for r in examples})
correct = [r["true_intent"] for r in dev]

for name, rewrite in [("clean", lambda s, rng: s), ("typos", add_typo),
                      ("CAPITALS", lambda s, rng: s.upper()), ("filler words", add_filler)]:
    rng = random.Random(0)
    messy = [rewrite(r["utt"], rng) for r in dev]
    vectors = vectorizer.transform(messy)
    predicted = classifier.predict(vectors)
    # Refuse when unsure, exactly as in c03: messy words make the classifier less sure.
    confidence = classifier.predict_proba(vectors).max(axis=1)
    predicted = ["REFUSED" if c < 0.35 else p for p, c in zip(predicted, confidence)]
    f1 = f1_score(correct, predicted, labels=labels, average="macro", zero_division=0)
    refused = predicted.count("REFUSED")
    print(f"{name:13} e.g. {messy[0]!r:50} macro-F1 {f1:.3f}  refused {refused} of {len(dev)}")
