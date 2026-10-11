"""Controlled access to a project's split files (PROJECT_PLAN.md section 4).

The plan's rule:

    Candidate-building tools receive only train/development file paths. The
    independent final evaluator has test access.

and the G6 test condition requires that held-out test paths are **not
accessible through the data interface**. So candidate-building code is handed a
``DataAccess`` rather than raw paths, and asking it for the test split raises
unless the freeze has been explicitly released.

This turns the freeze from a rule someone has to remember into a thing the code
refuses to do. Releasing it takes a deliberate call naming the freeze commit,
which is recorded in the run config.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

TRAIN_SPLITS = ("kshot",)
DEV_SPLITS = ("dev",)
TEST_SPLITS = ("test",)


class FinalTestLockedError(PermissionError):
    """Raised when candidate-building code reaches for the test split."""


class HeldOutProjectLockedError(PermissionError):
    """Raised when anything reaches for the held-out project before the freeze."""


@dataclass
class DataAccess:
    """A project's permitted file paths, with the test split withheld.

    ``held_out`` marks the project the plan excludes from every pre-freeze
    step. For such a project, *every* split is locked until release, not only
    the test split, because the plan allows no development predictions,
    threshold tuning, prompt checks or smoke tests on it.
    """

    project_id: str
    sources: dict[str, str]
    held_out: bool = False
    freeze_released: bool = False
    freeze_commit: str | None = None
    _accessed: list[str] = field(default_factory=list)

    # -- permitted access ----------------------------------------------

    def path(self, split: str) -> str:
        """The file path for a split, if the caller is permitted it."""
        if split not in self.sources:
            raise KeyError(
                f"{split!r} is not a split of {self.project_id}; "
                f"available: {', '.join(sorted(self.sources))}"
            )

        if self.held_out and not self.freeze_released:
            raise HeldOutProjectLockedError(
                f"{self.project_id} is the held-out project: no split of it may be "
                f"read before the freeze (requested {split!r}). Only its frozen "
                f"description may be used. Release with release_after_freeze()."
            )

        if split in TEST_SPLITS and not self.freeze_released:
            raise FinalTestLockedError(
                f"the test split of {self.project_id} is locked until the G10 "
                "freeze. Design-time evaluation must never query final test "
                "labels. Release with release_after_freeze(commit=...)."
            )

        self._accessed.append(split)
        return self.sources[split]

    @property
    def train_path(self) -> str:
        return self.path("kshot")

    @property
    def dev_path(self) -> str:
        return self.path("dev")

    @property
    def test_path(self) -> str:
        """Locked before the freeze; see ``release_after_freeze``."""
        return self.path("test")

    # -- the deliberate release ----------------------------------------

    def release_after_freeze(self, commit: str) -> "DataAccess":
        """Return a copy with test access, naming the freeze commit.

        Returns a new object rather than mutating this one, so a released
        handle cannot leak back into code that was given a locked one.
        """
        if not commit or len(commit) < 7:
            raise ValueError(
                "releasing the freeze requires the freeze commit hash, so the "
                "release is traceable in the run record"
            )
        return DataAccess(
            project_id=self.project_id,
            sources=dict(self.sources),
            held_out=self.held_out,
            freeze_released=True,
            freeze_commit=commit,
        )

    # -- the record ----------------------------------------------------

    @property
    def splits_accessed(self) -> list[str]:
        """Which splits this handle actually served, in order."""
        return list(self._accessed)

    def as_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "held_out": self.held_out,
            "freeze_released": self.freeze_released,
            "freeze_commit": self.freeze_commit,
            "available_splits": sorted(self.sources),
            "splits_accessed": self.splits_accessed,
        }


def access_for(spec: Any, *, freeze_released: bool = False, freeze_commit: str | None = None) -> DataAccess:
    """Build a ``DataAccess`` from a ProjectSpec.

    A project whose role is held out is locked entirely until release.
    """
    held_out = str(getattr(spec, "role", "")).lower() == "held-out"
    if not held_out:
        # ProjectSpec does not carry role; fall back to the manifest.
        import json

        manifest_path = Path(spec.source.get("manifest", ""))
        if manifest_path.name:
            root = Path(__file__).resolve().parents[2]
            full = root / manifest_path
            if full.exists():
                held_out = (
                    json.loads(full.read_text(encoding="utf-8")).get("role") == "held-out"
                )

    return DataAccess(
        project_id=spec.project_id,
        sources={k: v for k, v in spec.source.items() if k in ("kshot", "dev", "test")},
        held_out=held_out,
        freeze_released=freeze_released,
        freeze_commit=freeze_commit,
    )
