"""One LLM client wrapper for every LLM-based system (B1, B2, B4, A1, ablations).

Responsibilities, from PROJECT_PLAN.md sections 2A and 10:

- Talk to one runtime model through Ollama's HTTP API at temperature 0.
- Cache predictions by the full rendered prompt + model digest + settings.
- Count *logical* calls (what the method would have made on its own) separately
  from *physical* calls (what was actually sent to the model). Cache hits are
  not free design cost.
- Never let cached output contribute a latency number: a cache hit returns
  ``latency_s=None``. Latency comes from timing runs with ``cache_enabled``
  false.
- Enforce the prompt-size cap and log actual token counts per request.
- Count JSON-repair retries as new calls with their own cache entries.

No secret is read from the environment for Ollama (it is local and unauthenticated).
Architect planning calls use a separate client, added at G7.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .cache import PredictionCache, cache_key

DEFAULT_HOST = "http://127.0.0.1:11434"

# Prompt-size cap (section 2A). Enforced here as a hard guard; prompt builders
# in src/pipelines drop examples to stay under it.
MAX_INPUT_TOKENS = 2000
MAX_EXAMPLES = 16


class PromptTooLargeError(ValueError):
    """Raised when a rendered prompt exceeds the declared cap."""


@dataclass
class CallRecord:
    """What happened for one logical request. Written to predictions.jsonl."""

    cache_hit: bool
    text: str
    model: str
    model_digest: str
    prompt_tokens: int | None
    output_tokens: int | None
    latency_s: float | None
    attempts: int
    error: str | None
    cache_key: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "cache_hit": self.cache_hit,
            "text": self.text,
            "model": self.model,
            "model_digest": self.model_digest,
            "prompt_tokens": self.prompt_tokens,
            "output_tokens": self.output_tokens,
            # None on a cache hit: a cached output must never become a latency
            # figure. See the timing-run rule in section 2A.
            "latency_s": self.latency_s,
            "attempts": self.attempts,
            "error": self.error,
            "cache_key": self.cache_key,
        }


@dataclass
class CallCounter:
    """Logical vs physical calls, plus tokens and retries."""

    logical_calls: int = 0
    physical_calls: int = 0
    retries: int = 0
    prompt_tokens: int = 0
    output_tokens: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "logical_calls": self.logical_calls,
            "physical_calls": self.physical_calls,
            "retries": self.retries,
            "prompt_tokens": self.prompt_tokens,
            "output_tokens": self.output_tokens,
        }


def estimate_tokens(text: str) -> int:
    """Rough token estimate used only for the pre-flight cap check.

    The authoritative count is whatever the model server reports
    (``prompt_eval_count``); that is what gets logged. This estimate exists so
    an oversized prompt is rejected before a call is spent on it.
    """
    return max(1, len(text) // 4)


@dataclass
class LLMClient:
    model: str
    model_digest: str = ""
    host: str = DEFAULT_HOST
    settings: dict[str, Any] = field(default_factory=dict)
    cache: PredictionCache | None = None
    timeout_s: float = 120.0
    counter: CallCounter = field(default_factory=CallCounter)

    def __post_init__(self) -> None:
        base = {
            "temperature": 0.0,
            "seed": 0,
            "num_predict": 512,
            "format": "json",
            "stop": [],
        }
        base.update(self.settings or {})
        self.settings = base

    # -- cache control -------------------------------------------------

    @property
    def cache_enabled(self) -> bool:
        return self.cache is not None and self.cache.enabled

    def with_cache_disabled(self) -> "LLMClient":
        """Return a sibling client for timing runs (no cache reads or writes)."""
        twin = LLMClient(
            model=self.model,
            model_digest=self.model_digest,
            host=self.host,
            settings=dict(self.settings),
            cache=None,
            timeout_s=self.timeout_s,
            counter=self.counter,
        )
        return twin

    # -- the one entry point -------------------------------------------

    def generate(self, prompt: str, *, max_examples_used: int | None = None) -> CallRecord:
        """Run one logical request and return its record.

        Raises ``PromptTooLargeError`` before spending a call if the prompt
        breaks the declared cap.
        """
        self._check_cap(prompt, max_examples_used)
        key = cache_key(prompt, self.model, self.model_digest, self.settings)

        self.counter.logical_calls += 1

        if self.cache is not None:
            entry = self.cache.get(key)
            if entry is not None:
                return CallRecord(
                    cache_hit=True,
                    text=entry.get("text", ""),
                    model=self.model,
                    model_digest=self.model_digest,
                    prompt_tokens=entry.get("prompt_tokens"),
                    output_tokens=entry.get("output_tokens"),
                    latency_s=None,
                    attempts=entry.get("attempts", 1),
                    error=entry.get("error"),
                    cache_key=key,
                )

        record = self._call_model(prompt, key)
        if self.cache is not None and record.error is None:
            self.cache.put(
                key,
                {
                    "text": record.text,
                    "prompt_tokens": record.prompt_tokens,
                    "output_tokens": record.output_tokens,
                    "attempts": record.attempts,
                    "error": None,
                    "model": self.model,
                    "model_digest": self.model_digest,
                    "settings": self.settings,
                },
            )
        return record

    def generate_repair(self, repair_prompt: str) -> CallRecord:
        """A JSON-repair retry: a new call, its own cache entry, counted."""
        self.counter.retries += 1
        return self.generate(repair_prompt)

    # -- internals -----------------------------------------------------

    def _check_cap(self, prompt: str, max_examples_used: int | None) -> None:
        tokens = estimate_tokens(prompt)
        if tokens > MAX_INPUT_TOKENS:
            raise PromptTooLargeError(
                f"rendered prompt is about {tokens} tokens, cap is {MAX_INPUT_TOKENS}"
            )
        if max_examples_used is not None and max_examples_used > MAX_EXAMPLES:
            raise PromptTooLargeError(
                f"{max_examples_used} examples in prompt, cap is {MAX_EXAMPLES}"
            )

    def _call_model(self, prompt: str, key: str) -> CallRecord:
        body = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.settings["temperature"],
                "seed": self.settings["seed"],
                "num_predict": self.settings["num_predict"],
                "stop": self.settings["stop"] or None,
            },
        }
        if self.settings.get("format"):
            body["format"] = self.settings["format"]

        request = urllib.request.Request(
            f"{self.host}/api/generate",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        self.counter.physical_calls += 1
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError) as exc:
            # A runtime failure is a recorded result, not a dropped case.
            return CallRecord(
                cache_hit=False,
                text="",
                model=self.model,
                model_digest=self.model_digest,
                prompt_tokens=None,
                output_tokens=None,
                latency_s=time.perf_counter() - started,
                attempts=1,
                error=f"{type(exc).__name__}: {exc}",
                cache_key=key,
            )
        elapsed = time.perf_counter() - started

        prompt_tokens = payload.get("prompt_eval_count")
        output_tokens = payload.get("eval_count")
        self.counter.prompt_tokens += prompt_tokens or 0
        self.counter.output_tokens += output_tokens or 0

        return CallRecord(
            cache_hit=False,
            text=payload.get("response", ""),
            model=self.model,
            model_digest=self.model_digest,
            prompt_tokens=prompt_tokens,
            output_tokens=output_tokens,
            latency_s=elapsed,
            attempts=1,
            error=None,
            cache_key=key,
        )


def resolve_model_digest(model: str, host: str = DEFAULT_HOST) -> str:
    """Ask Ollama for the model's digest, recorded in every run manifest."""
    request = urllib.request.Request(
        f"{host}/api/show",
        data=json.dumps({"model": model}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    details = payload.get("details", {}) or {}
    return (
        payload.get("digest")
        or details.get("digest")
        or details.get("parent_model")
        or ""
    )


def ollama_version(host: str = DEFAULT_HOST) -> str:
    with urllib.request.urlopen(f"{host}/api/version", timeout=10) as response:
        return json.loads(response.read().decode("utf-8")).get("version", "")


def make_client(
    model: str,
    *,
    cache_dir: str | Path | None = "cache",
    host: str = DEFAULT_HOST,
    settings: dict[str, Any] | None = None,
    digest: str | None = None,
) -> LLMClient:
    """Build the shared runtime client. ``cache_dir=None`` disables caching."""
    cache = PredictionCache(Path(cache_dir)) if cache_dir is not None else None
    return LLMClient(
        model=model,
        model_digest=digest if digest is not None else resolve_model_digest(model, host),
        host=host,
        settings=settings or {},
        cache=cache,
    )
