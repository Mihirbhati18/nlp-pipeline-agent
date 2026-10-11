"""G6 checks on the data access guard.

The plan's G6 test condition requires that held-out test paths are not
accessible through the data interface. These checks assert the interface
*refuses*, rather than merely that nobody asked.
"""

import pytest

from src.analyzer.access import (
    DataAccess,
    HeldOutProjectLockedError,
    FinalTestLockedError,
    access_for,
)
from src.analyzer.spec import load_spec

SOURCES = {
    "kshot": "data/processed/P1/kshot.jsonl",
    "dev": "data/processed/P1/dev.jsonl",
    "test": "data/processed/P1/holdout/test.jsonl",
}


def dev_project(**kwargs) -> DataAccess:
    return DataAccess(project_id="P1", sources=dict(SOURCES), **kwargs)


def held_out_project(**kwargs) -> DataAccess:
    return DataAccess(project_id="P3", sources=dict(SOURCES), held_out=True, **kwargs)


# -- development projects ----------------------------------------------


def test_train_and_dev_are_available_before_the_freeze():
    access = dev_project()

    assert access.train_path.endswith("kshot.jsonl")
    assert access.dev_path.endswith("dev.jsonl")


def test_the_test_split_is_locked_before_the_freeze():
    access = dev_project()

    with pytest.raises(FinalTestLockedError, match="locked until the G10"):
        access.test_path


def test_the_test_split_is_locked_by_name_too():
    """There must be no back door through the generic accessor."""
    with pytest.raises(FinalTestLockedError):
        dev_project().path("test")


def test_an_unknown_split_is_refused_clearly():
    with pytest.raises(KeyError, match="not a split of P1"):
        dev_project().path("validation")


# -- the held-out project ----------------------------------------------


def test_every_split_of_the_held_out_project_is_locked():
    """The plan excludes P3 from every pre-freeze step, not just testing."""
    access = held_out_project()

    for split in ("kshot", "dev", "test"):
        with pytest.raises(HeldOutProjectLockedError, match="held-out project"):
            access.path(split)


def test_the_held_out_lock_explains_what_is_still_permitted():
    with pytest.raises(HeldOutProjectLockedError, match="frozen description"):
        held_out_project().dev_path


# -- releasing the freeze ----------------------------------------------


def test_release_requires_a_commit_hash_so_it_is_traceable():
    with pytest.raises(ValueError, match="freeze commit hash"):
        dev_project().release_after_freeze("")

    with pytest.raises(ValueError, match="freeze commit hash"):
        dev_project().release_after_freeze("abc")


def test_a_released_handle_grants_test_access():
    released = dev_project().release_after_freeze("5df4c93aaaa")

    assert released.test_path.endswith("test.jsonl")
    assert released.freeze_commit == "5df4c93aaaa"
    assert released.freeze_released is True


def test_release_returns_a_new_handle_and_leaves_the_original_locked():
    """A released handle must not leak back into locked code."""
    locked = dev_project()
    released = locked.release_after_freeze("5df4c93aaaa")

    assert released is not locked
    with pytest.raises(FinalTestLockedError):
        locked.test_path


def test_releasing_the_freeze_unlocks_the_held_out_project_too():
    released = held_out_project().release_after_freeze("5df4c93aaaa")

    assert released.dev_path.endswith("dev.jsonl")
    assert released.test_path.endswith("test.jsonl")


# -- the record --------------------------------------------------------


def test_which_splits_were_actually_read_is_recorded():
    access = dev_project()
    access.train_path
    access.dev_path
    access.train_path

    assert access.splits_accessed == ["kshot", "dev", "kshot"]


def test_a_refused_access_is_not_recorded_as_an_access():
    access = dev_project()
    with pytest.raises(FinalTestLockedError):
        access.test_path

    assert "test" not in access.splits_accessed


def test_the_handle_reports_its_state_for_the_run_record():
    record = dev_project().as_dict()

    assert record["project_id"] == "P1"
    assert record["freeze_released"] is False
    assert record["freeze_commit"] is None
    assert "test" in record["available_splits"]


# -- built from a real project specification ---------------------------


def test_access_for_a_real_development_project_permits_dev_and_locks_test():
    access = access_for(load_spec("P1"))

    assert access.held_out is False
    assert access.dev_path
    with pytest.raises(FinalTestLockedError):
        access.test_path


def test_access_for_the_real_held_out_project_is_locked_entirely():
    """P3's role comes from its manifest, so this cannot be forgotten."""
    access = access_for(load_spec("P3"))

    assert access.held_out is True
    with pytest.raises(HeldOutProjectLockedError):
        access.dev_path
