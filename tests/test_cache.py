"""G1 checks on the cache key and store.

The key must cover the full rendered prompt, the model name and digest, and
every generation setting (PROJECT_PLAN.md section 2A).
"""

from src.llm.cache import PredictionCache, cache_key

PROMPT = "Classify the request.\nRequest: cancel order 1234\n"
SETTINGS = {"temperature": 0.0, "seed": 0, "num_predict": 512, "format": "json", "stop": []}


def _key(**overrides):
    args = {
        "prompt": PROMPT,
        "model": "llama3.1:8b",
        "model_digest": "sha256:abc",
        "settings": dict(SETTINGS),
    }
    args.update(overrides)
    return cache_key(**args)


def test_identical_request_gives_identical_key():
    assert _key() == _key()


def test_one_character_of_prompt_changes_the_key():
    assert _key() != _key(prompt=PROMPT + " ")


def test_model_and_digest_change_the_key():
    assert _key() != _key(model="qwen2.5:3b")
    assert _key() != _key(model_digest="sha256:def")


def test_every_generation_setting_changes_the_key():
    for field, value in [
        ("temperature", 0.7),
        ("seed", 1),
        ("num_predict", 256),
        ("format", ""),
        ("stop", ["\n"]),
    ]:
        altered = dict(SETTINGS)
        altered[field] = value
        assert _key() != _key(settings=altered), field


def test_setting_order_does_not_change_the_key():
    reordered = {k: SETTINGS[k] for k in reversed(list(SETTINGS))}
    assert _key() == _key(settings=reordered)


def test_hit_and_miss_are_counted(tmp_path):
    cache = PredictionCache(tmp_path / "cache")
    key = _key()

    assert cache.get(key) is None
    assert cache.stats.as_dict() == {"hits": 0, "misses": 1, "writes": 0}

    cache.put(key, {"text": '{"intent": "cancel_order"}'})
    entry = cache.get(key)

    assert entry is not None
    assert entry["text"] == '{"intent": "cancel_order"}'
    assert cache.stats.as_dict() == {"hits": 1, "misses": 1, "writes": 1}
    assert cache.count_entries() == 1


def test_disabled_cache_neither_reads_nor_writes(tmp_path):
    cache = PredictionCache(tmp_path / "cache", enabled=False)
    key = _key()
    cache.put(key, {"text": "x"})
    assert cache.get(key) is None
    assert cache.stats.as_dict() == {"hits": 0, "misses": 0, "writes": 0}


def test_corrupt_entry_is_a_miss_not_a_prediction(tmp_path):
    cache = PredictionCache(tmp_path / "cache")
    key = _key()
    cache.put(key, {"text": "good"})
    path = cache._path(key)
    path.write_text("{not json", encoding="utf-8")
    assert cache.get(key) is None
