"""One helper creates every run folder (PROJECT_PLAN.md section 10).

``new_run(project, system, seed, config)`` generates the run ID, creates the
folder, writes ``config.json`` and ``manifest.json`` (git commit, Python and
package versions, model name and digest, data hashes) and returns a logger for
predictions, timings and events. No run folder is ever written by hand.

Run folder contents:
    config.json        system, project, model, settings and budgets
    manifest.json      code commit, environment, model digest, hashes, times
    predictions.jsonl  case IDs, outputs, status, cache hit/miss, tokens, errors
    metrics.json       scores, sample counts, definitions version, denominators
    timing.jsonl       uncached timing-run latencies (the only latency source)
    events.jsonl       candidate attempts, failures, retries, selection decisions
    summary.md         plain-language result and limitations
"""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, IO

METRIC_DEFINITIONS_VERSION = "1.2"
RUNS_ROOT = Path("runs")

TRACKED_PACKAGES = (
    "scikit-learn",
    "numpy",
    "scipy",
    "torch",
    "transformers",
    "pytest",
)


def _git(*args: str) -> str:
    try:
        out = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(Path(__file__).resolve().parents[2]),
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return out.stdout.strip() if out.returncode == 0 else "unknown"


def git_state() -> dict[str, str]:
    """Commit, branch and dirty flag. A dirty tree is recorded, not hidden."""
    status = _git("status", "--porcelain")
    return {
        "commit": _git("rev-parse", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": "unknown" if status == "unknown" else str(bool(status)).lower(),
    }


def package_versions() -> dict[str, str]:
    from importlib import metadata

    versions: dict[str, str] = {}
    for name in TRACKED_PACKAGES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = "not installed"
    return versions


def file_hash(path: str | Path) -> str:
    """SHA-256 of a data or split file, for the manifest."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_paths(paths: dict[str, str | Path]) -> dict[str, str]:
    out: dict[str, str] = {}
    for label, path in paths.items():
        try:
            out[label] = file_hash(path)
        except OSError as exc:
            out[label] = f"unavailable: {exc}"
    return out


@dataclass
class RunLogger:
    """Append-only writers for one run. Use as a context manager."""

    run_id: str
    path: Path
    _handles: dict[str, IO[str]] = field(default_factory=dict)

    def _handle(self, name: str) -> IO[str]:
        if name not in self._handles:
            self._handles[name] = open(self.path / name, "a", encoding="utf-8")
        return self._handles[name]

    def _append(self, name: str, record: dict[str, Any]) -> None:
        handle = self._handle(name)
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        handle.flush()

    def log_prediction(self, **record: Any) -> None:
        """One evaluated case. Failures are logged, never dropped."""
        self._append("predictions.jsonl", record)

    def log_timing(self, **record: Any) -> None:
        """One uncached timing observation: the only source of latency figures."""
        self._append("timing.jsonl", record)

    def log_event(self, kind: str, **record: Any) -> None:
        """A candidate attempt, failure, retry or selection decision."""
        self._append("events.jsonl", {"ts": time.time(), "kind": kind, **record})

    def write_metrics(self, metrics: dict[str, Any]) -> None:
        payload = dict(metrics)
        payload["metric_definitions_version"] = METRIC_DEFINITIONS_VERSION
        (self.path / "metrics.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )

    def write_summary(self, text: str) -> None:
        (self.path / "summary.md").write_text(text, encoding="utf-8")

    def finish(self, status: str = "complete", **extra: Any) -> None:
        """Stamp the manifest with the end time and outcome.

        An incomplete or failed run stays visible with its real status.
        """
        manifest_path = self.path / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        manifest["status"] = status
        manifest.update(extra)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        self.close()

    def close(self) -> None:
        for handle in self._handles.values():
            handle.close()
        self._handles.clear()

    def __enter__(self) -> "RunLogger":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is not None:
            self.log_event("run_exception", error=f"{exc_type.__name__}: {exc}")
            self.finish(status=f"failed: {exc_type.__name__}")
        else:
            self.close()


def new_run(
    project: str,
    system: str,
    seed: int | str,
    config: dict[str, Any],
    *,
    data_paths: dict[str, str | Path] | None = None,
    runs_root: str | Path = RUNS_ROOT,
    notes: str = "",
) -> RunLogger:
    """Create an immutable run folder and return its logger.

    Run IDs are ``YYYYMMDD_HHMM_project_system_seed`` and are never reused: a
    collision gets a numeric suffix rather than overwriting the earlier run.
    """
    stamp = time.strftime("%Y%m%d_%H%M")
    base = f"{stamp}_{project}_{system}_{seed}"
    root = Path(runs_root)
    path = root / base
    suffix = 1
    while path.exists():
        suffix += 1
        path = root / f"{base}_r{suffix}"
    path.mkdir(parents=True)
    run_id = path.name

    (path / "config.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "project": project,
                "system": system,
                "seed": seed,
                **config,
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    manifest = {
        "run_id": run_id,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "status": "running",
        "git": git_state(),
        "python": sys.version.split()[0],
        "platform": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "packages": package_versions(),
        "model": config.get("model"),
        "model_digest": config.get("model_digest"),
        "ollama_version": config.get("ollama_version"),
        "settings": config.get("settings"),
        "budgets": config.get("budgets"),
        "cache_enabled": config.get("cache_enabled"),
        "data_hashes": hash_paths(data_paths or {}),
        "metric_definitions_version": METRIC_DEFINITIONS_VERSION,
        "notes": notes,
    }
    (path / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    return RunLogger(run_id=run_id, path=path)
