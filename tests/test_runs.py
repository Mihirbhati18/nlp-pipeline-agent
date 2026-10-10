"""G1 checks on the run-folder helper (PROJECT_PLAN.md section 10)."""

import json

from src.evaluation.runs import new_run


CONFIG = {
    "model": "test:3b",
    "model_digest": "sha256:test",
    "settings": {"temperature": 0.0, "seed": 0},
    "budgets": {"candidates": 4},
    "cache_enabled": True,
}


def test_run_folder_has_config_and_manifest(tmp_path):
    with new_run("P1", "A1", 0, CONFIG, runs_root=tmp_path) as log:
        config = json.loads((log.path / "config.json").read_text(encoding="utf-8"))
        manifest = json.loads((log.path / "manifest.json").read_text(encoding="utf-8"))

    assert config["project"] == "P1"
    assert config["system"] == "A1"
    assert config["model"] == "test:3b"
    assert manifest["model_digest"] == "sha256:test"
    assert manifest["python"]
    assert "git" in manifest and "commit" in manifest["git"]
    assert manifest["metric_definitions_version"] == "1.2"


def test_run_id_format_and_no_reuse(tmp_path):
    first = new_run("P1", "B1", 0, CONFIG, runs_root=tmp_path)
    second = new_run("P1", "B1", 0, CONFIG, runs_root=tmp_path)
    first.close()
    second.close()

    assert first.run_id != second.run_id, "an ID is never reused"
    assert first.run_id.split("_")[2:] == ["P1", "B1", "0"]
    assert second.run_id.endswith("_r2")


def test_loggers_append_jsonl(tmp_path):
    with new_run("P1", "A1", 0, CONFIG, runs_root=tmp_path) as log:
        log.log_prediction(case_id="dev-1", status="ok", cache_hit=False, intent="alarm_set")
        log.log_prediction(case_id="dev-2", status="error", cache_hit=False, error="timeout")
        log.log_timing(case_id="dev-1", latency_s=1.23, warmup=False)
        log.log_event("candidate_attempt", config_id="c07", accepted=True)
        log.write_metrics({"intent_macro_f1": 0.71, "n_cases": 100})
        path = log.path

    predictions = [json.loads(line) for line in (path / "predictions.jsonl").read_text().splitlines()]
    assert len(predictions) == 2
    assert predictions[1]["status"] == "error", "failed cases stay in the record"

    timing = json.loads((path / "timing.jsonl").read_text().strip())
    assert timing["latency_s"] == 1.23

    event = json.loads((path / "events.jsonl").read_text().strip())
    assert event["kind"] == "candidate_attempt"

    metrics = json.loads((path / "metrics.json").read_text(encoding="utf-8"))
    assert metrics["intent_macro_f1"] == 0.71
    assert metrics["metric_definitions_version"] == "1.2"


def test_finish_stamps_status(tmp_path):
    log = new_run("P1", "A1", 0, CONFIG, runs_root=tmp_path)
    log.finish(status="complete", n_cases=100)
    manifest = json.loads((log.path / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["status"] == "complete"
    assert manifest["finished_at"]
    assert manifest["n_cases"] == 100


def test_exception_leaves_a_failed_run_visible(tmp_path):
    try:
        with new_run("P1", "A1", 0, CONFIG, runs_root=tmp_path) as log:
            path = log.path
            raise ValueError("boom")
    except ValueError:
        pass

    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"].startswith("failed")
    events = (path / "events.jsonl").read_text()
    assert "run_exception" in events


def test_data_hashes_are_recorded(tmp_path):
    data = tmp_path / "dev_ids.txt"
    data.write_text("dev-1\ndev-2\n", encoding="utf-8")

    log = new_run("P1", "A1", 0, CONFIG, runs_root=tmp_path, data_paths={"dev_ids": data})
    log.close()
    manifest = json.loads((log.path / "manifest.json").read_text(encoding="utf-8"))

    assert len(manifest["data_hashes"]["dev_ids"]) == 64


def test_missing_data_file_is_marked_unavailable_not_silently_skipped(tmp_path):
    log = new_run(
        "P1", "A1", 0, CONFIG, runs_root=tmp_path, data_paths={"absent": tmp_path / "nope.txt"}
    )
    log.close()
    manifest = json.loads((log.path / "manifest.json").read_text(encoding="utf-8"))

    assert manifest["data_hashes"]["absent"].startswith("unavailable")
