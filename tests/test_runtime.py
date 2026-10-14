"""G9 checks: export, reload in a fresh process, and explicit request outcomes.

The plan's G9 condition: a fresh process loads the artifact; normal,
out-of-scope and invalid requests work; failures are explicit. These use a
stubbed model, so they run without Ollama.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.analyzer.spec import Constraints, EntitySpec, IntentSpec, ProjectSpec
from src.llm import client as client_mod
from src.llm.client import LLMClient
from src.runtime.package import (
    EXAMPLES_FILE,
    PIPELINE_FILE,
    RESPONSE_ERROR,
    RESPONSE_INVALID_OUTPUT,
    RESPONSE_INVALID_REQUEST,
    RESPONSE_OK,
    RESPONSE_OOS,
    ModelMismatchError,
    PackageIntegrityError,
    export_pipeline,
    load_pipeline,
    spec_from_dict,
    spec_to_dict,
)

ROOT = Path(__file__).resolve().parents[1]

POOL = [
    {"case_id": "k1", "utt": "wake me up at six am", "true_intent": "alarm_set",
     "in_scope": True, "entities": [{"type": "time", "text": "six am", "start": 14, "end": 20}]},
    {"case_id": "k2", "utt": "cancel my alarm", "true_intent": "alarm_remove",
     "in_scope": True, "entities": []},
]

SPEC = ProjectSpec(
    project_id="PT", name="Test project",
    description_text="An assistant that sets and cancels alarms for people at home.",
    intents=[IntentSpec("alarm_set", "create an alarm"), IntentSpec("alarm_remove", "delete one")],
    entity_types=[EntitySpec("time", "a clock time")],
    slots_by_intent={"alarm_set": ["time"], "alarm_remove": []},
    constraints=Constraints(max_p95_latency_s=2.0),
    source={"kshot": "pool.jsonl"},
    enriched=True,
)


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Ollama:
    """Answers /api/tags with a digest and /api/generate with queued replies."""

    def __init__(self, replies=(), digest="digest-a", fail=False):
        self.replies = list(replies)
        self.digest = digest
        self.fail = fail
        self.generate_calls = 0
        self.tag_calls = 0

    def __call__(self, request, timeout=None):  # noqa: ARG002
        url = request if isinstance(request, str) else request.full_url
        if url.endswith("/api/tags"):
            self.tag_calls += 1
            return _Resp({"models": [{"name": "t", "digest": self.digest}]})
        self.generate_calls += 1
        if self.fail:
            raise ConnectionRefusedError("ollama is not running")
        text = self.replies.pop(0) if self.replies else '{"intent": "alarm_set", "entities": []}'
        return _Resp({"response": text, "prompt_eval_count": 100, "eval_count": 10})


def client() -> LLMClient:
    return LLMClient(model="t", model_digest="digest-a", cache=None)


def exported(tmp_path, config_id="joint-sim-llm", threshold=None) -> Path:
    return export_pipeline(
        spec=SPEC, config_id=config_id, oos_threshold=threshold,
        pool=POOL, client=client(), out_root=tmp_path,
        source={"system": "A1", "run_id": "test"},
    )


def served(monkeypatch, tmp_path, replies=(), **kwargs):
    stub = _Ollama(replies, **{k: v for k, v in kwargs.items() if k in ("digest", "fail")})
    monkeypatch.setattr(client_mod.urllib.request, "urlopen", stub)
    path = exported(tmp_path, **{k: v for k, v in kwargs.items() if k in ("config_id", "threshold")})
    return load_pipeline(path), stub


# -- export --------------------------------------------------------------


def test_the_specification_survives_a_round_trip():
    assert spec_from_dict(json.loads(json.dumps(spec_to_dict(SPEC)))) == SPEC


def test_an_export_writes_three_files_and_a_content_addressed_directory(tmp_path):
    path = exported(tmp_path)
    assert sorted(p.name for p in path.iterdir()) == ["examples.jsonl", "manifest.json", "pipeline.json"]
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    assert path.name == f"joint-sim-llm-{manifest['package_hash'][:12]}"
    pipeline = json.loads((path / "pipeline.json").read_text(encoding="utf-8"))
    assert pipeline["model"]["digest"] == "digest-a"
    assert pipeline["spec"]["intents"][0]["description"] == "create an alarm"


def test_exporting_the_same_pipeline_twice_gives_the_same_package(tmp_path):
    assert exported(tmp_path) == exported(tmp_path)


def test_no_eligible_candidate_means_nothing_is_exported(tmp_path):
    with pytest.raises(ValueError, match="no eligible candidate"):
        exported(tmp_path, config_id=None)


def test_an_id_outside_the_catalogue_cannot_be_exported(tmp_path):
    with pytest.raises(Exception):
        exported(tmp_path, config_id="magic-best-config")


def test_a_tfidf_pipeline_cannot_be_exported_without_its_threshold(tmp_path):
    with pytest.raises(ValueError, match="threshold"):
        exported(tmp_path, config_id="joint-sim-tfidf", threshold=None)


def test_out_of_scope_examples_are_refused_in_the_pool(tmp_path):
    with pytest.raises(ValueError, match="out-of-scope"):
        export_pipeline(spec=SPEC, config_id="joint-sim-llm", oos_threshold=None,
                        pool=[*POOL, {"case_id": "x", "utt": "news", "in_scope": False}],
                        client=client(), out_root=tmp_path)


# -- integrity -------------------------------------------------------------


@pytest.mark.parametrize("name", [PIPELINE_FILE, EXAMPLES_FILE])
def test_a_modified_file_refuses_to_load(tmp_path, name):
    path = exported(tmp_path)
    target = path / name
    target.write_bytes(target.read_bytes().replace(b"alarm", b"alerm", 1))
    with pytest.raises(PackageIntegrityError, match="modified"):
        load_pipeline(path)


def test_a_missing_file_refuses_to_load(tmp_path):
    path = exported(tmp_path)
    (path / EXAMPLES_FILE).unlink()
    with pytest.raises(PackageIntegrityError, match="missing"):
        load_pipeline(path)


def test_a_directory_that_is_not_a_package_refuses_to_load(tmp_path):
    with pytest.raises(PackageIntegrityError, match="not a pipeline package"):
        load_pipeline(tmp_path)


def test_loading_makes_no_network_call(monkeypatch, tmp_path):
    path = exported(tmp_path)
    stub = _Ollama()
    monkeypatch.setattr(client_mod.urllib.request, "urlopen", stub)
    load_pipeline(path)
    assert stub.tag_calls == 0 and stub.generate_calls == 0


# -- requests --------------------------------------------------------------


def test_a_normal_request_returns_intent_and_located_entities(monkeypatch, tmp_path):
    pipeline, _ = served(monkeypatch, tmp_path, [
        '{"intent": "alarm_set", "entities": [{"type": "time", "text": "seven am"}]}'])
    response = pipeline.handle("set an alarm for seven am")
    assert response["status"] == RESPONSE_OK
    assert response["intent"] == "alarm_set"
    assert response["entities"] == [{"type": "time", "text": "seven am", "start": 17, "end": 25}]
    assert response["model_calls"] == 1


def test_an_entity_not_in_the_request_is_reported_unsupported_not_dropped(monkeypatch, tmp_path):
    pipeline, _ = served(monkeypatch, tmp_path, [
        '{"intent": "alarm_set", "entities": [{"type": "time", "text": "noon"}]}'])
    response = pipeline.handle("set an alarm for seven am")
    assert response["entities"] == []
    assert response["unsupported_entities"] == [{"type": "time", "text": "noon"}]


def test_the_llm_out_of_scope_label_is_an_explicit_out_of_scope_response(monkeypatch, tmp_path):
    pipeline, _ = served(monkeypatch, tmp_path, ['{"intent": "none_of_the_above", "entities": []}'])
    response = pipeline.handle("what is the news today")
    assert response["status"] == RESPONSE_OOS and response["intent"] is None


def test_a_tfidf_rejection_spends_no_model_call(monkeypatch, tmp_path):
    pipeline, stub = served(monkeypatch, tmp_path, config_id="joint-sim-tfidf", threshold=0.99)
    response = pipeline.handle("what is the capital of peru")
    assert response["status"] == RESPONSE_OOS
    assert response["rejected_by_threshold"] is True
    assert stub.generate_calls == 0 and stub.tag_calls == 0


@pytest.mark.parametrize("request_", ["", "   ", None, 42, "x" * 501])
def test_invalid_requests_are_refused_before_any_model_call(monkeypatch, tmp_path, request_):
    pipeline, stub = served(monkeypatch, tmp_path)
    response = pipeline.handle(request_)
    assert response["status"] == RESPONSE_INVALID_REQUEST
    assert response["error"]
    assert stub.generate_calls == 0


def test_an_unusable_reply_after_repair_is_invalid_output_not_an_answer(monkeypatch, tmp_path):
    pipeline, _ = served(monkeypatch, tmp_path, ["not json", "still not json"])
    response = pipeline.handle("set an alarm for seven am")
    assert response["status"] == RESPONSE_INVALID_OUTPUT
    assert response["intent"] is None
    assert response["repaired"] is True and response["model_calls"] == 2


def test_a_failed_call_is_an_explicit_error(monkeypatch, tmp_path):
    pipeline, _ = served(monkeypatch, tmp_path, fail=True)
    response = pipeline.handle("set an alarm for seven am")
    assert response["status"] == RESPONSE_ERROR
    assert response["error"]


def test_a_different_installed_model_refuses_to_serve(monkeypatch, tmp_path):
    pipeline, stub = served(monkeypatch, tmp_path, digest="digest-b")
    with pytest.raises(ModelMismatchError):
        pipeline.handle("set an alarm for seven am")
    assert stub.generate_calls == 0


def test_the_model_digest_is_checked_once_not_per_request(monkeypatch, tmp_path):
    pipeline, stub = served(monkeypatch, tmp_path)
    pipeline.handle("set an alarm for seven am")
    pipeline.handle("cancel my alarm")
    assert stub.tag_calls == 1


def test_runtime_never_uses_the_evaluation_cache(tmp_path):
    pipeline = load_pipeline(exported(tmp_path))
    assert pipeline.runner.client.cache is None


# -- the fresh process -------------------------------------------------------


def test_a_fresh_process_loads_the_package_and_refuses_a_bad_request(tmp_path):
    path = exported(tmp_path)
    code = (
        "import json, sys\n"
        "from src.runtime.package import load_pipeline\n"
        # An unreachable host: proves loading and request validation need no model.
        "p = load_pipeline(sys.argv[1], host='http://127.0.0.1:9')\n"
        "print(json.dumps({'info': p.describe(), 'bad': p.handle('')}))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(path)],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    out = json.loads(result.stdout.strip().splitlines()[-1])
    assert out["info"]["config_id"] == "joint-sim-llm"
    assert out["info"]["intents"] == ["alarm_set", "alarm_remove"]
    assert out["bad"]["status"] == RESPONSE_INVALID_REQUEST
