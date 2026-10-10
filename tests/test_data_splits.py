"""G2 checks on the prepared project splits.

These run against the committed manifests and processed files, so they guard
the data plan itself: sizes, official-split provenance, the out-of-scope
source rule, leakage and cross-project independence.
"""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "data" / "manifests"
PROJECTS = ("P1", "P2", "P3")

pytestmark = pytest.mark.skipif(
    not (MANIFESTS / "P1.json").exists(),
    reason="run scripts/prepare_data.py first",
)


def manifest(pid: str) -> dict:
    return json.loads((MANIFESTS / f"{pid}.json").read_text(encoding="utf-8"))


def cases(pid: str, split: str) -> list[dict]:
    path = ROOT / manifest(pid)["files"][split]
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


@pytest.mark.parametrize("pid", PROJECTS)
def test_counts_match_the_declared_sizes(pid):
    m = manifest(pid)
    counts, sampling = m["counts"], m["sampling"]

    assert counts["kshot"] == sampling["k_per_intent"] * m["n_intents"]
    assert counts["dev_total"] == sampling["dev_total"]
    assert counts["dev_oos"] == sampling["dev_oos"]
    assert counts["test_total"] == sampling["test_total"]
    assert counts["test_oos"] == sampling["test_oos"]


@pytest.mark.parametrize("pid", PROJECTS)
def test_every_intent_has_exactly_k_examples(pid):
    from collections import Counter

    m = manifest(pid)
    counts = Counter(c["true_intent"] for c in cases(pid, "kshot"))

    assert set(counts) == set(m["intents"])
    assert set(counts.values()) == {m["sampling"]["k_per_intent"]}
    assert not m["intents_with_fewer_than_k_train_examples"]


@pytest.mark.parametrize("pid", PROJECTS)
def test_official_split_provenance_is_preserved(pid):
    """A development case came from the official dev split, and so on."""
    assert {c["partition"] for c in cases(pid, "kshot")} == {"train"}
    assert {c["partition"] for c in cases(pid, "dev")} == {"dev"}
    assert {c["partition"] for c in cases(pid, "test")} == {"test"}


@pytest.mark.parametrize("pid", PROJECTS)
def test_in_scope_cases_come_only_from_the_project_domains(pid):
    m = manifest(pid)
    for split in ("kshot", "dev", "test"):
        scenarios = {c["scenario"] for c in cases(pid, split) if c["in_scope"]}
        assert scenarios <= set(m["domains"]), (split, scenarios)


@pytest.mark.parametrize("pid", PROJECTS)
def test_out_of_scope_cases_come_only_from_the_reserved_pool(pid):
    config = json.loads((ROOT / "configs" / "projects.json").read_text(encoding="utf-8"))
    pool = set(config["oos_pool"]["domains"])
    project_domains = {d for p in config["projects"] for d in p["domains"]}

    assert not pool & project_domains, "the reserved pool must not touch any project"
    for split in ("dev", "test"):
        oos = [c for c in cases(pid, split) if not c["in_scope"]]
        assert oos
        assert {c["scenario"] for c in oos} <= pool


@pytest.mark.parametrize("pid", PROJECTS)
def test_out_of_scope_cases_carry_the_oos_label_and_no_entities(pid):
    for split in ("dev", "test"):
        for case in cases(pid, split):
            if not case["in_scope"]:
                assert case["intent"] == "none_of_the_above"
                assert case["entities"] == []


@pytest.mark.parametrize("pid", PROJECTS)
def test_no_case_id_appears_in_two_splits(pid):
    ids = {split: {c["case_id"] for c in cases(pid, split)} for split in ("kshot", "dev", "test")}

    assert not ids["kshot"] & ids["dev"]
    assert not ids["kshot"] & ids["test"]
    assert not ids["dev"] & ids["test"]
    assert manifest(pid)["leakage"]["passes_id_check"]


def test_no_evaluation_case_is_shared_between_projects():
    seen: dict[str, str] = {}
    for pid in PROJECTS:
        for split in ("dev", "test"):
            for case in cases(pid, split):
                assert case["case_id"] not in seen, (
                    f"{case['case_id']} is in both {seen.get(case['case_id'])} and {pid}"
                )
                seen[case["case_id"]] = f"{pid}/{split}"


@pytest.mark.parametrize("pid", PROJECTS)
def test_gold_spans_index_the_utterance_correctly(pid):
    for split in ("kshot", "dev", "test"):
        for case in cases(pid, split):
            for entity in case["entities"]:
                assert case["utt"][entity["start"] : entity["end"]] == entity["text"]


@pytest.mark.parametrize("pid", PROJECTS)
def test_file_hashes_match_the_manifest(pid):
    import hashlib

    m = manifest(pid)
    for split, expected in m["sha256"].items():
        data = (ROOT / m["files"][split]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == expected, split


@pytest.mark.parametrize("pid", PROJECTS)
def test_near_duplicate_overlaps_are_declared_with_case_ids(pid):
    """Overlap is allowed to exist, but it must be named, not silently carried."""
    m = manifest(pid)
    for pair, info in m["leakage"]["near_duplicate_overlaps"].items():
        assert len(info["case_id_pairs"]) == info["count"], pair


@pytest.mark.parametrize("pid", PROJECTS)
def test_frozen_description_exists(pid):
    path = ROOT / "configs" / "descriptions" / f"{pid}.md"
    text = path.read_text(encoding="utf-8")

    assert "Frozen" in text
    assert len(text.split()) > 150, "a description should be a realistic paragraph set"
