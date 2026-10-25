"""C1 yourself: build a project's data split straight from the original MASSIVE file.

Run from the project folder:  python diy/c01_make_split.py
"""

import json
import random
from collections import Counter

# 1. Read the original dataset: one request per line, labelled by people.
records = []
with open("data/raw/1.1/data/en-US.jsonl", encoding="utf-8") as f:
    for line in f:
        records.append(json.loads(line))
print("requests in MASSIVE (English):", len(records))

# 2. Keep only the domains our home-assistant project handles.
project_domains = ["alarm", "iot"]
mine = [r for r in records if r["scenario"] in project_domains]
print("requests about alarms and smart-home devices:", len(mine))

# 3. MASSIVE already says which requests are for training, development and testing.
train = [r for r in mine if r["partition"] == "train"]
dev = [r for r in mine if r["partition"] == "dev"]
test = [r for r in mine if r["partition"] == "test"]
print("official split sizes: train", len(train), "| dev", len(dev), "| test", len(test))

# 4. Draw 10 examples per intent from the training part. A fixed seed means
#    the same "random" draw every time anyone runs this.
random.seed(42)
examples = []
for intent in sorted({r["intent"] for r in train}):
    candidates = [r for r in train if r["intent"] == intent]
    examples += random.sample(candidates, min(10, len(candidates)))
print("examples drawn:", len(examples), "(10 per intent)")

# 5. Draw 80 development requests the same way.
dev_sample = random.sample(dev, 80)
print("development requests drawn:", len(dev_sample))
print("intents in the development sample:", dict(Counter(r["intent"] for r in dev_sample)))

# 6. The leakage check: no request may be in two places.
example_ids = {r["id"] for r in examples}
dev_ids = {r["id"] for r in dev_sample}
print("requests in both examples and development (must be 0):", len(example_ids & dev_ids))

# 7. Save them, one request per line.
with open("diy/my_dev.jsonl", "w", encoding="utf-8") as f:
    for r in dev_sample:
        f.write(json.dumps({"id": r["id"], "utt": r["utt"], "intent": r["intent"]}) + "\n")
print("saved diy/my_dev.jsonl")
