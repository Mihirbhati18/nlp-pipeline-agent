"""Export the chosen pipeline as a versioned package, and load it back (G9).

The plan's runtime rule: a backend loads the exported package and answers
requests *without* asking the Architect to redesign anything. So the package
carries everything a request needs and nothing the design needed:

- ``pipeline.json`` - the enriched ProjectSpec, the chosen configuration, the
  development-tuned out-of-scope threshold, the model name, digest and
  generation settings, and where the design came from
- ``examples.jsonl`` - the k-shot pool the configuration draws examples from
- ``manifest.json`` - format version, git commit, package versions, the
  SHA-256 of both files above, and the package hash derived from them

Three properties are enforced rather than hoped for:

1. **A modified package refuses to load.** Every file is re-hashed on load.
2. **A different model refuses to run.** Before the first model call the
   installed model's digest is compared with the exported one. The same
   weights are what make the exported scores mean anything.
3. **Every outcome is explicit.** A response always carries a status; a bad
   request, an unusable model reply and a failed call are all distinguishable,
   and none of them is dressed up as an answer.

Loading makes no network call. The model is contacted only when a request
actually needs it, so a package can be inspected, and bad requests rejected,
with Ollama stopped.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.analyzer.spec import Constraints, EntitySpec, IntentSpec, ProjectSpec
from src.evaluation.runs import git_state, package_versions
from src.evaluation.scorer import STATUS_ERROR, STATUS_INVALID, STATUS_OK, STATUS_OOS
from src.evaluation.span_rule import locate_entities
from src.llm.client import DEFAULT_HOST, LLMClient, resolve_model_digest
from src.pipelines.catalogue import ConfigRunner, get_config
from src.pipelines.examples import ExampleSelector

FORMAT_VERSION = "1"
PIPELINE_FILE = "pipeline.json"
EXAMPLES_FILE = "examples.jsonl"
MANIFEST_FILE = "manifest.json"

# Requests longer than this are refused before any model call. MASSIVE
# utterances are short (the longest en-US one is well under 300 characters),
# and an unbounded request would also bypass the prompt cap's intent.
MAX_REQUEST_CHARS = 500

# Response statuses. Runtime has one more than evaluation: a request that
# never reached the pipeline because it was malformed.
RESPONSE_OK = "ok"
RESPONSE_OOS = "out_of_scope"
RESPONSE_INVALID_OUTPUT = "invalid_output"
RESPONSE_ERROR = "error"
RESPONSE_INVALID_REQUEST = "invalid_request"

_STATUS_MAP = {
    STATUS_OK: RESPONSE_OK,
    STATUS_OOS: RESPONSE_OOS,
    STATUS_INVALID: RESPONSE_INVALID_OUTPUT,
    STATUS_ERROR: RESPONSE_ERROR,
}


class PackageIntegrityError(RuntimeError):
    """The package on disk does not match the hashes in its manifest."""


class ModelMismatchError(RuntimeError):
    """The installed model is not the one the pipeline was designed with."""


# -- specification round trip -------------------------------------------


def spec_to_dict(spec: ProjectSpec) -> dict[str, Any]:
    return asdict(spec)


def spec_from_dict(data: dict[str, Any]) -> ProjectSpec:
    return ProjectSpec(
        project_id=data["project_id"],
        name=data["name"],
        description_text=data["description_text"],
        intents=[IntentSpec(**i) for i in data["intents"]],
        entity_types=[EntitySpec(**e) for e in data["entity_types"]],
        slots_by_intent={k: list(v) for k, v in data.get("slots_by_intent", {}).items()},
        constraints=Constraints(**data.get("constraints", {})),
        source=dict(data.get("source", {})),
        enriched=bool(data.get("enriched", False)),
    )


# -- export --------------------------------------------------------------


def _canonical(obj: Any) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _package_hash(file_hashes: dict[str, str]) -> str:
    joined = "".join(f"{name}:{file_hashes[name]}\n" for name in sorted(file_hashes))
    return _sha256(joined.encode("utf-8"))


def export_pipeline(
    *,
    spec: ProjectSpec,
    config_id: str | None,
    oos_threshold: float | None,
    pool: list[dict],
    client: LLMClient,
    out_root: str | Path = "artifacts",
    source: dict[str, Any] | None = None,
) -> Path:
    """Write a package for one selected pipeline and return its directory.

    ``config_id=None`` means the design found no eligible candidate. There is
    nothing honest to export in that case, so this raises rather than writing
    a package around some fallback the design did not choose.
    """
    if config_id is None:
        raise ValueError("no eligible candidate was selected; there is no pipeline to export")
    config = get_config(config_id)  # raises on an id outside the catalogue
    if config.oos_policy == "tfidf_threshold" and oos_threshold is None:
        raise ValueError(f"{config_id} needs its development-tuned out-of-scope threshold")
    if not client.model_digest:
        raise ValueError("refusing to export without a model digest")
    if any(not case.get("in_scope", True) for case in pool):
        raise ValueError("the example pool contains out-of-scope cases; no system trains on them")

    pipeline = {
        "format_version": FORMAT_VERSION,
        "project_id": spec.project_id,
        "config": config.as_dict(),
        "config_id": config.config_id,
        "oos_threshold": oos_threshold,
        "spec": spec_to_dict(spec),
        "model": {
            "name": client.model,
            "digest": client.model_digest,
            "settings": dict(client.settings),
        },
        "max_request_chars": MAX_REQUEST_CHARS,
        "source": source or {},
    }
    pipeline_bytes = _canonical(pipeline)
    examples_bytes = "".join(
        json.dumps(case, sort_keys=True, ensure_ascii=False) + "\n" for case in pool
    ).encode("utf-8")

    file_hashes = {PIPELINE_FILE: _sha256(pipeline_bytes), EXAMPLES_FILE: _sha256(examples_bytes)}
    package_hash = _package_hash(file_hashes)

    out_dir = Path(out_root) / spec.project_id / f"{config.config_id}-{package_hash[:12]}"
    if out_dir.exists():
        # Same content gives the same directory, so an identical re-export is
        # a no-op; a hash collision with different bytes would be caught on load.
        return out_dir
    out_dir.mkdir(parents=True)

    manifest = {
        "format_version": FORMAT_VERSION,
        "package_hash": package_hash,
        "files": file_hashes,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git": git_state(),
        "packages": package_versions(),
        "note": (
            "Load with src.runtime.package.load_pipeline. Runtime never calls the "
            "Architect; the configuration below is fixed."
        ),
    }
    (out_dir / PIPELINE_FILE).write_bytes(pipeline_bytes)
    (out_dir / EXAMPLES_FILE).write_bytes(examples_bytes)
    (out_dir / MANIFEST_FILE).write_bytes(_canonical(manifest))
    return out_dir


# -- load and serve --------------------------------------------------------


@dataclass
class Pipeline:
    """A loaded, frozen pipeline. Call :meth:`handle` once per request."""

    path: Path
    package_hash: str
    spec: ProjectSpec
    config_id: str
    oos_threshold: float | None
    model: str
    model_digest: str
    max_request_chars: int
    runner: ConfigRunner
    verify_model: bool = True
    host: str = DEFAULT_HOST
    _model_verified: bool = field(default=False, repr=False)
    _requests: int = field(default=0, repr=False)

    def describe(self) -> dict[str, Any]:
        return {
            "project_id": self.spec.project_id,
            "project_name": self.spec.name,
            "config_id": self.config_id,
            "package_hash": self.package_hash,
            "model": self.model,
            "model_digest": self.model_digest,
            "intents": self.spec.intent_names,
            "entity_types": self.spec.entity_type_names,
            "oos_threshold": self.oos_threshold,
        }

    def _check_model(self) -> None:
        if self._model_verified or not self.verify_model:
            return
        installed = resolve_model_digest(self.model, self.host)
        if installed != self.model_digest:
            raise ModelMismatchError(
                f"installed {self.model} has digest {installed[:16]}, but this pipeline "
                f"was designed and scored with {self.model_digest[:16]}"
            )
        self._model_verified = True

    def _response(self, status: str, started: float, **extra: Any) -> dict[str, Any]:
        response = {
            "status": status,
            "intent": None,
            "entities": [],
            "unsupported_entities": [],
            "error": None,
            "model_calls": 0,
            "latency_s": round(time.perf_counter() - started, 4),
            "pipeline": {
                "project_id": self.spec.project_id,
                "config_id": self.config_id,
                "package_hash": self.package_hash[:12],
            },
        }
        response.update(extra)
        return response

    def handle(self, request: Any) -> dict[str, Any]:
        """Answer one request. Never raises for a bad request or a bad reply."""
        started = time.perf_counter()
        self._requests += 1

        if not isinstance(request, str):
            return self._response(RESPONSE_INVALID_REQUEST, started,
                                  error=f"request must be text, got {type(request).__name__}")
        utterance = " ".join(request.split())
        if not utterance:
            return self._response(RESPONSE_INVALID_REQUEST, started, error="request is empty")
        if len(utterance) > self.max_request_chars:
            return self._response(
                RESPONSE_INVALID_REQUEST, started,
                error=f"request is {len(utterance)} characters; the limit is {self.max_request_chars}",
            )

        would_call = not (
            self.runner.config.oos_policy == "tfidf_threshold"
            and self.runner.selector.max_similarity(utterance) < (self.oos_threshold or 0.0)
        )
        try:
            if would_call:
                self._check_model()
            outcome = self.runner.run_case({"case_id": f"req{self._requests}", "utt": utterance})
        except ModelMismatchError:
            # A wrong model is a deployment fault, not a per-request failure;
            # answering anyway would silently serve an unvalidated pipeline.
            raise
        except Exception as exc:  # noqa: BLE001
            return self._response(RESPONSE_ERROR, started, error=f"{type(exc).__name__}: {exc}")

        prediction = outcome.prediction
        status = _STATUS_MAP.get(prediction.status, RESPONSE_ERROR)
        located = locate_entities(utterance, prediction.entities) if status == RESPONSE_OK else []
        return self._response(
            status, started,
            intent=prediction.intent if status == RESPONSE_OK else None,
            entities=[
                {"type": e.type, "text": e.text, "start": e.start, "end": e.end}
                for e in located if e.supported
            ],
            # Strings the model returned that are not in the request. Reported,
            # never silently dropped and never fuzzy-matched into a span.
            unsupported_entities=[
                {"type": e.type, "text": e.text} for e in located if not e.supported
            ],
            error=prediction.error,
            model_calls=outcome.logical_calls,
            rejected_by_threshold=outcome.rejected_by_threshold,
            repaired=outcome.repaired,
            request=utterance,
        )


def verify_package(path: str | Path) -> dict[str, Any]:
    """Re-hash every file and return the manifest, or raise."""
    path = Path(path)
    manifest_path = path / MANIFEST_FILE
    if not manifest_path.is_file():
        raise PackageIntegrityError(f"{path} has no {MANIFEST_FILE}; not a pipeline package")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format_version") != FORMAT_VERSION:
        raise PackageIntegrityError(
            f"package format {manifest.get('format_version')!r}; this loader reads {FORMAT_VERSION!r}"
        )
    expected = manifest.get("files", {})
    if set(expected) != {PIPELINE_FILE, EXAMPLES_FILE}:
        raise PackageIntegrityError(f"manifest lists {sorted(expected)}; expected both package files")
    for name, digest in expected.items():
        file_path = path / name
        if not file_path.is_file():
            raise PackageIntegrityError(f"{name} is missing")
        actual = _sha256(file_path.read_bytes())
        if actual != digest:
            raise PackageIntegrityError(f"{name} was modified after export (hash {actual[:12]})")
    if _package_hash(expected) != manifest.get("package_hash"):
        raise PackageIntegrityError("package hash does not match its file hashes")
    return manifest


def load_pipeline(
    path: str | Path,
    *,
    host: str = DEFAULT_HOST,
    verify_model: bool = True,
    client: LLMClient | None = None,
) -> Pipeline:
    """Load an exported package. Makes no network call.

    The runtime client never uses the evaluation cache: a served request is a
    live call, and its latency is real.
    """
    path = Path(path)
    manifest = verify_package(path)
    pipeline = json.loads((path / PIPELINE_FILE).read_text(encoding="utf-8"))
    with open(path / EXAMPLES_FILE, encoding="utf-8") as handle:
        pool = [json.loads(line) for line in handle if line.strip()]

    spec = spec_from_dict(pipeline["spec"])
    config = get_config(pipeline["config_id"])
    model = pipeline["model"]
    runtime_client = client or LLMClient(
        model=model["name"],
        model_digest=model["digest"],
        host=host,
        settings=dict(model["settings"]),
        cache=None,
    )
    runner = ConfigRunner(
        config=config,
        spec=spec,
        client=runtime_client,
        selector=ExampleSelector(pool),
        oos_threshold=pipeline.get("oos_threshold"),
    )
    return Pipeline(
        path=path,
        package_hash=manifest["package_hash"],
        spec=spec,
        config_id=config.config_id,
        oos_threshold=pipeline.get("oos_threshold"),
        model=model["name"],
        model_digest=model["digest"],
        max_request_chars=int(pipeline.get("max_request_chars", MAX_REQUEST_CHARS)),
        runner=runner,
        verify_model=verify_model,
        host=host,
    )
