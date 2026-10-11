"""Checks on the B3 Kaggle assets (part of G5).

These guard the freeze discipline: the file uploaded to a third-party service
must not carry test labels or anything from the held-out project, and the
notebook must not reference them either.
"""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPLITS = ROOT / "data" / "manifests" / "b3_splits.json"
NOTEBOOK = ROOT / "notebooks" / "kaggle_b3_finetune.ipynb"

pytestmark = pytest.mark.skipif(not SPLITS.exists(), reason="run the G2 export first")


def splits() -> dict:
    return json.loads(SPLITS.read_text(encoding="utf-8"))


def notebook() -> dict:
    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))


def test_the_uploaded_file_carries_no_test_case_ids():
    data = splits()

    for project, spec in data["projects"].items():
        assert set(spec["case_ids"]) == {"kshot", "dev"}, project
        assert "test" not in spec["counts"], project
    assert "test" not in json.dumps(data["projects"])


def test_the_uploaded_file_excludes_the_held_out_project():
    assert set(splits()["projects"]) == {"P1", "P2"}
    assert "P3" not in json.dumps(splits()["projects"])


def test_the_uploaded_case_ids_match_the_frozen_manifests_exactly():
    for project, spec in splits()["projects"].items():
        manifest = json.loads(
            (ROOT / "data" / "manifests" / f"{project}.json").read_text(encoding="utf-8")
        )
        assert spec["case_ids"]["kshot"] == manifest["case_ids"]["kshot"]
        assert spec["case_ids"]["dev"] == manifest["case_ids"]["dev"]
        assert spec["intents"] == manifest["intents"]
        assert spec["entity_schema"] == manifest["entity_schema"]
        assert spec["sha256"]["kshot"] == manifest["sha256"]["kshot"]
        assert spec["sha256"]["dev"] == manifest["sha256"]["dev"]


def test_the_uploaded_file_states_what_it_deliberately_excludes():
    excluded = " ".join(splits()["deliberately_excluded"]).lower()

    assert "test" in excluded
    assert "p3" in excluded


def test_the_notebook_is_valid_json_with_runnable_code_cells():
    cells = notebook()["cells"]

    assert cells
    for index, cell in enumerate(cells):
        if cell["cell_type"] == "code":
            compile("".join(cell["source"]), f"cell{index}", "exec")


def test_the_notebook_never_mentions_the_held_out_project():
    text = "".join(
        "".join(cell["source"]) for cell in notebook()["cells"] if cell["cell_type"] == "code"
    )

    assert "P3" not in text


def test_the_notebook_trains_on_dev_and_kshot_only():
    code = "".join(
        "".join(cell["source"]) for cell in notebook()["cells"] if cell["cell_type"] == "code"
    )

    assert '"test"' not in code and "'test'" not in code
    assert '"dev"' in code or "'dev'" in code


def test_the_notebook_verifies_the_dataset_hash_recorded_at_g2():
    code = "".join(
        "".join(cell["source"]) for cell in notebook()["cells"] if cell["cell_type"] == "code"
    )
    manifest = json.loads(
        (ROOT / "data" / "manifests" / "P1.json").read_text(encoding="utf-8")
    )

    assert manifest["dataset"]["sha256_archive"] in code


def test_the_notebook_refuses_to_train_on_out_of_scope_examples():
    code = "".join(
        "".join(cell["source"]) for cell in notebook()["cells"] if cell["cell_type"] == "code"
    )

    assert 'all(c["in_scope"] for c in kshot + full)' in code


def test_the_notebook_exports_predictions_rather_than_metrics():
    """B3 must be scored by the shared scorer, not by notebook code."""
    code = "".join(
        "".join(cell["source"]) for cell in notebook()["cells"] if cell["cell_type"] == "code"
    )

    assert "b3_predictions.json" in code
    assert "f1_score" not in code and "classification_report" not in code


def test_the_notebook_marks_b3_full_as_an_upper_reference():
    markdown = "".join(
        "".join(cell["source"]) for cell in notebook()["cells"]
        if cell["cell_type"] == "markdown"
    ).lower()

    assert "upper reference" in markdown
    assert "never be presented as a matched comparison" in markdown
