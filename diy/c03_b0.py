"""C3 yourself: build the word-matching baseline (B0) from scratch.

No AI model needed.  Run:  python diy/c03_b0.py
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score

from helpers import load_jsonl

# 1. Load the 120 labelled examples (to learn from) and the 100 development requests (to test on).
examples = load_jsonl("data/processed/P1/kshot.jsonl")
dev = load_jsonl("data/processed/P1/dev.jsonl")
in_scope = [r for r in dev if r["in_scope"]]      # the 80 that have a real intent

# 2. Turn sentences into numbers: each word gets a weight (TF-IDF).
#    ngram_range=(1, 2) also counts pairs of words, like "turn off".
vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
X_train = vectorizer.fit_transform([r["utt"] for r in examples])
y_train = [r["true_intent"] for r in examples]

# 3. Train a classifier that learns which word weights point to which intent.
classifier = LogisticRegression(max_iter=2000, C=10.0, random_state=0)
classifier.fit(X_train, y_train)

# 4. Predict the intent of every development request.
X_dev = vectorizer.transform([r["utt"] for r in in_scope])
predicted = classifier.predict(X_dev)

# 5. Refuse a request when the classifier is unsure (its top probability is low).
#    The project chose this cut-off on development data; here we just pick 0.35.
confidence = classifier.predict_proba(X_dev).max(axis=1)
predicted = ["REFUSED" if c < 0.35 else p for p, c in zip(predicted, confidence)]

# 6. Score it.
correct = [r["true_intent"] for r in in_scope]
labels = sorted(set(correct))
print("first 5:", list(zip([r["utt"] for r in in_scope[:5]], predicted[:5])))
print("accuracy:", round(accuracy_score(correct, predicted), 3))
print("intent macro-F1:", round(f1_score(correct, predicted, labels=labels, average="macro", zero_division=0), 3))
