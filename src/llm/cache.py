"""Prediction cache for LLM calls.

Cache rules (PROJECT_PLAN.md section 2A):

- The key is a hash of the full rendered prompt, the model name and digest, and
  every generation setting. Two prompts differing in any character are
  different entries.
- Cached outputs are used for scoring only, never for latency. Every hit is
  flagged so ``predictions.jsonl`` can record it.
- A JSON-repair retry is a separate call with its own entry.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CACHE_VERSION = 1


def cache_key(prompt: str, model: str, model_digest: str, settings: dict[str, Any]) -> str:
    """Return the cache key for one request.

    ``prompt`` must be the *fully rendered* prompt: instructions, label and
    entity definitions, and the exact examples included. ``settings`` must
    contain every generation setting that can change the output (temperature,
    seed, maximum tokens, output format, stop sequences, ...).
    """
    payload = {
        "cache_version": CACHE_VERSION,
        "prompt": prompt,
        "model": model,
        "model_digest": model_digest,
        # sort_keys makes the key independent of dict insertion order.
        "settings": settings,
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    writes: int = 0

    def as_dict(self) -> dict[str, int]:
        return {"hits": self.hits, "misses": self.misses, "writes": self.writes}


@dataclass
class PredictionCache:
    """A content-addressed cache of raw model responses on disk.

    One JSON file per entry under ``root/<key[:2]>/<key>.json``. Entries are
    written atomically so an interrupted overnight batch cannot leave a
    half-written entry that would later be read as a valid prediction.
    """

    root: Path
    enabled: bool = True
    stats: CacheStats = field(default_factory=CacheStats)

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        if self.enabled:
            self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / key[:2] / f"{key}.json"

    def get(self, key: str) -> dict[str, Any] | None:
        """Return the cached entry, or None on a miss (or when disabled).

        Latency timing runs disable the cache; see ``LLMClient``.
        """
        if not self.enabled:
            return None
        path = self._path(key)
        if not path.exists():
            self.stats.misses += 1
            return None
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # A corrupt entry is treated as a miss, never as a prediction.
            self.stats.misses += 1
            return None
        self.stats.hits += 1
        return entry

    def put(self, key: str, entry: dict[str, Any]) -> None:
        if not self.enabled:
            return
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        record = dict(entry)
        record["cached_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        record["cache_key"] = key
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(record, handle, ensure_ascii=False)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        self.stats.writes += 1

    def count_entries(self) -> int:
        if not self.root.exists():
            return 0
        return sum(1 for _ in self.root.glob("*/*.json"))
