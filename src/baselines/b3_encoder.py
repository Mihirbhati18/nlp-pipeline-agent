"""B3: the fine-tuned encoder baseline (PROJECT_PLAN.md section 3).

B3 is the project's **published reference baseline**: the MASSIVE paper
(FitzGerald et al., ACL 2023) reports XLM-R results with released code, so this
has a published, reproducible basis. Publication alone does not make it state of
the art, and it must be described as "the dataset's published reference
baseline" unless the literature check at G5 supports more.

Two variants:

- **B3-k** trains on the same k = 10 examples per intent every LLM system gets.
  This is the fair supervised comparison.
- **B3-full** trains on the project's full official train split. An **upper
  reference only**; it must never be presented as a matched comparison.

Architecture follows the MASSIVE reference recipe: one encoder with two heads,
intent classification over the pooled representation and slot BIO tagging per
token.

Rules this module keeps:

- **No out-of-scope example is ever trained on**, in any variant, matching
  every other system. The out-of-scope decision is a maximum-softmax
  confidence threshold tuned on development data only, by the same shared rule
  B0 uses.
- It **predicts, and does not score**. Entity predictions are emitted as the
  utterance's own substrings and located by the shared span rule, so B3 is
  scored by exactly the same code as every other system.
- Training is seeded and the seed, device and hyperparameters are recorded.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Sequence

import numpy as np

MODEL_NAME = "xlm-roberta-base"
MAX_LENGTH = 64


@dataclass
class B3Hyperparameters:
    model_name: str = MODEL_NAME
    learning_rate: float = 3e-5
    batch_size: int = 16
    max_length: int = MAX_LENGTH
    epochs_kshot: int = 30
    epochs_full: int = 5
    seed: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "learning_rate": self.learning_rate,
            "batch_size": self.batch_size,
            "max_length": self.max_length,
            "epochs_kshot": self.epochs_kshot,
            "epochs_full": self.epochs_full,
            "seed": self.seed,
        }


def bio_labels(entity_types: Sequence[str]) -> list[str]:
    """``O`` plus a B- and I- tag per declared entity type."""
    labels = ["O"]
    for entity_type in entity_types:
        labels += [f"B-{entity_type}", f"I-{entity_type}"]
    return labels


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    import torch

    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def encode_case(
    case: dict,
    tokenizer: Any,
    intent_to_id: dict[str, int],
    label_to_id: dict[str, int],
    max_length: int = MAX_LENGTH,
) -> dict[str, Any]:
    """Tokenize one case and align its gold character spans to BIO tags.

    A token is tagged only when it lies wholly inside a gold span, and ``B-`` is
    used when it starts exactly at the span's first character. A gold entity
    whose type is not in the declared schema produces no tag, which matches the
    scorer treating it as an unavoidable recall error.
    """
    encoded = tokenizer(
        case["utt"], truncation=True, max_length=max_length, return_offsets_mapping=True
    )
    tags: list[int] = []
    for start, end in encoded["offset_mapping"]:
        if start == end:  # special token
            tags.append(-100)
            continue
        tag = "O"
        for entity in case["entities"]:
            if start >= entity["start"] and end <= entity["end"]:
                prefix = "B" if start == entity["start"] else "I"
                candidate = f"{prefix}-{entity['type']}"
                if candidate in label_to_id:
                    tag = candidate
                break
        tags.append(label_to_id[tag])
    encoded.pop("offset_mapping")
    encoded["slot_labels"] = tags
    encoded["intent_label"] = intent_to_id.get(case["true_intent"], -100)
    return dict(encoded)


def decode_spans(utterance: str, offsets: Sequence[Sequence[int]], tags: Sequence[str]) -> list[dict]:
    """Merge BIO tags into entity substrings of the utterance.

    The text emitted is the utterance's own substring, so the shared span rule
    always locates it and B3 goes through the same evaluator as every other
    system.
    """
    entities: list[dict] = []
    current: dict | None = None
    for (start, end), tag in zip(offsets, tags):
        if start == end:
            continue
        if tag == "O":
            current = None
            continue
        prefix, _, entity_type = tag.partition("-")
        if prefix == "B" or current is None or current["type"] != entity_type:
            current = {"type": entity_type, "start": start, "end": end}
            entities.append(current)
        else:
            current["end"] = end
    return [
        {"type": e["type"], "text": utterance[e["start"] : e["end"]]}
        for e in entities
        if utterance[e["start"] : e["end"]].strip()
    ]


@dataclass
class B3Trainer:
    """Trains one variant for one project and returns closed-set predictions."""

    intents: list[str]
    entity_types: list[str]
    hyperparameters: B3Hyperparameters = field(default_factory=B3Hyperparameters)
    device: str = "cpu"
    _model: Any = field(default=None, repr=False)
    _tokenizer: Any = field(default=None, repr=False)
    _labels: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        import torch

        if self.device == "cpu" and torch.cuda.is_available():
            self.device = "cuda"
        self._labels = bio_labels(self.entity_types)

    # -- training ------------------------------------------------------

    def fit(self, cases: Sequence[dict], epochs: int) -> "B3Trainer":
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader
        from transformers import AutoModel, AutoTokenizer

        if any(not case["in_scope"] for case in cases):
            raise ValueError(
                "B3 must never be trained on out-of-scope examples; no system here is"
            )

        hp = self.hyperparameters
        set_seed(hp.seed)

        self._tokenizer = AutoTokenizer.from_pretrained(hp.model_name)
        intent_to_id = {name: i for i, name in enumerate(self.intents)}
        label_to_id = {name: i for i, name in enumerate(self._labels)}

        encoder = AutoModel.from_pretrained(hp.model_name)
        hidden = encoder.config.hidden_size

        class JointModel(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.encoder = encoder
                self.dropout = nn.Dropout(0.1)
                self.intent_head = nn.Linear(hidden, len(intent_to_id))
                self.slot_head = nn.Linear(hidden, len(label_to_id))

            def forward(self, input_ids, attention_mask):
                out = self.encoder(
                    input_ids=input_ids, attention_mask=attention_mask
                ).last_hidden_state
                return (
                    self.intent_head(self.dropout(out[:, 0])),
                    self.slot_head(self.dropout(out)),
                )

        model = JointModel().to(self.device)
        encoded = [
            encode_case(c, self._tokenizer, intent_to_id, label_to_id, hp.max_length)
            for c in cases
        ]
        pad = self._tokenizer.pad_token_id

        def collate(batch):
            width = max(len(b["input_ids"]) for b in batch)
            return {
                "input_ids": torch.tensor(
                    [b["input_ids"] + [pad] * (width - len(b["input_ids"])) for b in batch]
                ),
                "attention_mask": torch.tensor(
                    [b["attention_mask"] + [0] * (width - len(b["attention_mask"])) for b in batch]
                ),
                "slot_labels": torch.tensor(
                    [b["slot_labels"] + [-100] * (width - len(b["slot_labels"])) for b in batch]
                ),
                "intent_label": torch.tensor([b["intent_label"] for b in batch]),
            }

        loader = DataLoader(
            encoded, batch_size=hp.batch_size, shuffle=True, collate_fn=collate
        )
        optimiser = torch.optim.AdamW(model.parameters(), lr=hp.learning_rate)
        loss_fn = nn.CrossEntropyLoss(ignore_index=-100)

        model.train()
        for epoch in range(epochs):
            total = 0.0
            for batch in loader:
                batch = {k: v.to(self.device) for k, v in batch.items()}
                optimiser.zero_grad()
                intent_logits, slot_logits = model(batch["input_ids"], batch["attention_mask"])
                loss = loss_fn(intent_logits, batch["intent_label"]) + loss_fn(
                    slot_logits.reshape(-1, len(label_to_id)), batch["slot_labels"].reshape(-1)
                )
                loss.backward()
                optimiser.step()
                total += loss.item()
            if epoch == 0 or (epoch + 1) % 5 == 0 or epoch == epochs - 1:
                print(f"    epoch {epoch + 1}/{epochs} loss {total / max(1, len(loader)):.4f}",
                      flush=True)

        self._model = model
        return self

    # -- prediction ----------------------------------------------------

    def predict(self, cases: Sequence[dict]) -> list[dict]:
        """Closed-set intent, its softmax confidence, and entity substrings.

        The out-of-scope decision is *not* made here: it is a threshold applied
        afterwards, tuned on development data only.
        """
        import torch

        if self._model is None:
            raise ValueError("call fit() before predict()")

        hp = self.hyperparameters
        self._model.eval()
        results: list[dict] = []
        with torch.no_grad():
            for case in cases:
                encoded = self._tokenizer(
                    case["utt"], truncation=True, max_length=hp.max_length,
                    return_offsets_mapping=True, return_tensors="pt",
                )
                offsets = encoded.pop("offset_mapping")[0].tolist()
                encoded = {k: v.to(self.device) for k, v in encoded.items()}
                intent_logits, slot_logits = self._model(
                    encoded["input_ids"], encoded["attention_mask"]
                )
                probabilities = torch.softmax(intent_logits[0], dim=-1)
                best = int(probabilities.argmax())
                tags = [self._labels[i] for i in slot_logits[0].argmax(dim=-1).tolist()]
                results.append({
                    "case_id": case["case_id"],
                    "closed_set_intent": self.intents[best],
                    "confidence": float(probabilities[best]),
                    "entities": decode_spans(case["utt"], offsets, tags),
                })
        return results

    def release(self) -> None:
        """Free GPU memory between variants; 4 GB does not hold two models."""
        import torch

        self._model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
