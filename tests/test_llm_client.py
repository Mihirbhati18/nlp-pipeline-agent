"""G1 checks on the shared LLM client.

Covered: logical vs physical call counting, the cache-hit latency rule, the
prompt-size cap, retry counting, and failure recording. The model server is
replaced by a stub, so these tests need no Ollama.
"""

import json

import pytest

from src.llm import client as client_mod
from src.llm.cache import PredictionCache
from src.llm.client import LLMClient, PromptTooLargeError

RESPONSE = {"response": '{"intent": "cancel_order"}', "prompt_eval_count": 180, "eval_count": 12}


class _FakeHTTP:
    """Stands in for urllib.request.urlopen."""

    def __init__(self, payload=None, error=None):
        self.payload = payload if payload is not None else RESPONSE
        self.error = error
        self.calls = 0

    def __call__(self, request, timeout=None):  # noqa: ARG002
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def http(monkeypatch):
    stub = _FakeHTTP()
    monkeypatch.setattr(client_mod.urllib.request, "urlopen", stub)
    return stub


def _client(tmp_path, cache=True):
    store = PredictionCache(tmp_path / "cache") if cache else None
    return LLMClient(model="test:3b", model_digest="sha256:test", cache=store)


def test_first_call_is_physical_and_timed(tmp_path, http):
    llm = _client(tmp_path)
    record = llm.generate("prompt one")

    assert http.calls == 1
    assert record.cache_hit is False
    assert record.latency_s is not None
    assert record.prompt_tokens == 180
    assert llm.counter.as_dict()["logical_calls"] == 1
    assert llm.counter.as_dict()["physical_calls"] == 1


def test_repeat_is_a_logical_call_but_not_a_physical_one(tmp_path, http):
    llm = _client(tmp_path)
    llm.generate("prompt one")
    record = llm.generate("prompt one")

    assert http.calls == 1, "the second request must be served from cache"
    assert record.cache_hit is True
    assert llm.counter.logical_calls == 2
    assert llm.counter.physical_calls == 1, "cache hits are not free design cost"


def test_cache_hit_carries_no_latency(tmp_path, http):
    llm = _client(tmp_path)
    llm.generate("prompt one")
    record = llm.generate("prompt one")

    assert record.latency_s is None
    assert record.as_dict()["latency_s"] is None


def test_timing_client_bypasses_the_cache(tmp_path, http):
    llm = _client(tmp_path)
    llm.generate("prompt one")
    timed = llm.with_cache_disabled()
    record = timed.generate("prompt one")

    assert http.calls == 2
    assert record.cache_hit is False
    assert record.latency_s is not None
    assert timed.cache_enabled is False


def test_different_prompts_are_separate_entries(tmp_path, http):
    llm = _client(tmp_path)
    llm.generate("prompt one")
    llm.generate("prompt two")
    assert http.calls == 2
    assert llm.cache.count_entries() == 2


def test_oversized_prompt_is_rejected_before_a_call(tmp_path, http):
    llm = _client(tmp_path)
    with pytest.raises(PromptTooLargeError):
        llm.generate("x" * (client_mod.MAX_INPUT_TOKENS * 4 + 100))
    assert http.calls == 0


def test_too_many_examples_is_rejected(tmp_path, http):
    llm = _client(tmp_path)
    with pytest.raises(PromptTooLargeError):
        llm.generate("short prompt", max_examples_used=client_mod.MAX_EXAMPLES + 1)
    assert http.calls == 0


def test_repair_retry_is_a_new_counted_call(tmp_path, http):
    llm = _client(tmp_path)
    llm.generate("prompt one")
    llm.generate_repair("prompt one, repaired")

    assert http.calls == 2
    assert llm.counter.retries == 1
    assert llm.counter.physical_calls == 2
    assert llm.cache.count_entries() == 2, "a repair has its own cache entry"


def test_failure_is_recorded_and_not_cached(tmp_path, monkeypatch):
    stub = _FakeHTTP(error=TimeoutError("read timed out"))
    monkeypatch.setattr(client_mod.urllib.request, "urlopen", stub)
    llm = _client(tmp_path)
    record = llm.generate("prompt one")

    assert record.error is not None
    assert record.text == ""
    assert llm.cache.count_entries() == 0, "a failure must not be cached as a prediction"
    assert llm.counter.physical_calls == 1


def test_temperature_zero_is_the_default(tmp_path):
    llm = _client(tmp_path, cache=False)
    assert llm.settings["temperature"] == 0.0
    assert llm.settings["format"] == "json"
