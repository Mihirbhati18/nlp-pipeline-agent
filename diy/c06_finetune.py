"""C6 yourself: fine-tune the published baseline model (XLM-R) to recognise intents.

The project's B3 also learns entities; this simpler version learns intents only,
which is enough to see how fine-tuning works. No Ollama needed, but it trains on
the laptop's processor: about 5 to 10 minutes.  Run:  python diy/c06_finetune.py
"""

import os

os.environ["HF_HUB_OFFLINE"] = "1"   # the model is already downloaded; don't go online

import torch
from sklearn.metrics import accuracy_score, f1_score
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from helpers import load_jsonl

torch.manual_seed(0)                                  # same result every run

# 1. The data: 120 labelled examples to learn from, 80 in-scope development requests to test on.
examples = load_jsonl("data/processed/P1/kshot.jsonl")
dev = [r for r in load_jsonl("data/processed/P1/dev.jsonl") if r["in_scope"]]
intents = sorted({r["true_intent"] for r in examples})
number_of = {name: i for i, name in enumerate(intents)}   # the model works with numbers, not names

# 2. Load XLM-R and add a small "intent" layer on top, with one output per intent.
tokenizer = AutoTokenizer.from_pretrained("xlm-roberta-base")
model = AutoModelForSequenceClassification.from_pretrained("xlm-roberta-base", num_labels=len(intents))


def to_numbers(sentences):
    """Split sentences into word pieces and turn them into numbers the model reads."""
    return tokenizer(sentences, padding=True, truncation=True, max_length=48, return_tensors="pt")


# 3. Fine-tune: show the examples again and again; after each batch, nudge the model's
#    internal numbers so its guesses get closer to the correct intents.
optimizer = torch.optim.AdamW(model.parameters(), lr=3e-5)
model.train()
for epoch in range(30):                               # 30 passes over the examples
    order = torch.randperm(len(examples)).tolist()
    for start in range(0, len(order), 16):            # 16 examples at a time
        batch = [examples[i] for i in order[start:start + 16]]
        inputs = to_numbers([r["utt"] for r in batch])
        labels = torch.tensor([number_of[r["true_intent"]] for r in batch])
        loss = model(**inputs, labels=labels).loss    # how wrong the model is on this batch
        loss.backward()                               # work out which way to nudge each number
        optimizer.step()                              # nudge them
        optimizer.zero_grad()
    if (epoch + 1) % 5 == 0:
        print(f"pass {epoch + 1}/30, how wrong (loss): {loss.item():.3f}")

# 4. Test it on the development requests it has never seen.
model.eval()
with torch.no_grad():
    scores = model(**to_numbers([r["utt"] for r in dev])).logits
predicted = [intents[i] for i in scores.argmax(dim=1).tolist()]
correct = [r["true_intent"] for r in dev]
print("accuracy:", round(accuracy_score(correct, predicted), 3))
print("intent macro-F1:", round(f1_score(correct, predicted, labels=intents, average="macro", zero_division=0), 3))
