"""The reproduction check must catch a recorded number that the code did not produce."""

import importlib.util
import json
from pathlib import Path

from src.analyzer.spec import load_cases, load_spec
from src.evaluation.scorer import Prediction, score

_spec = importlib.util.spec_from_file_location(
    "reproduce_metrics", Path(__file__).resolve().parents[1] / "scripts" / "reproduce_metrics.py"
)
reproduce = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reproduce)


def make_run(tmp_path: Path) -> Path:
    spec = load_spec("P1")
    cases = load_cases(spec.source["dev"])
    # A deliberately imperfect system: every third in-scope case gets the wrong intent.
    predictions = []
    for i, c in enumerate(cases):
        if not c["in_scope"]:
            predictions.append(Prediction(c["case_id"], "oos", None, [], True, True))
        else:
            intent = spec.intent_names[0] if i % 3 == 0 else c["true_intent"]
            predictions.append(Prediction(c["case_id"], "ok", intent,
                                          [{"type": e["type"], "text": e["text"]} for e in c["entities"]],
                                          True, True))
    run = tmp_path / "20990101_0000_P1_TEST_0"
    run.mkdir()
    (run / "config.json").write_text(json.dumps({"project": "P1", "split": "dev"}), encoding="utf-8")
    (run / "metrics.json").write_text(json.dumps(score(cases, predictions, labels=spec.intent_names)),
                                      encoding="utf-8")
    with open(run / "predictions.jsonl", "w", encoding="utf-8") as handle:
        for p in predictions:
            handle.write(json.dumps({"case_id": p.case_id, "status": p.status,
                                     "predicted_intent": p.intent, "predicted_entities": p.entities,
                                     "schema_valid_raw": True, "schema_valid_final": True}) + "\n")
    return run


def test_an_untouched_run_reproduces(tmp_path):
    status, _ = reproduce.check_run(make_run(tmp_path))
    assert status == "match"


def test_an_edited_score_is_caught(tmp_path):
    run = make_run(tmp_path)
    metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    metrics["primary"]["intent_macro_f1"] += 0.01  # a hand-edited "better" number
    (run / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    status, detail = reproduce.check_run(run)
    assert status == "MISMATCH" and "intent_macro_f1" in detail


def test_an_edited_prediction_is_caught(tmp_path):
    run = make_run(tmp_path)
    rows = (run / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
    first = json.loads(rows[0])
    first["status"], first["predicted_intent"] = "ok", "definitely_not_an_intent"
    rows[0] = json.dumps(first)
    (run / "predictions.jsonl").write_text("\n".join(rows) + "\n", encoding="utf-8")
    status, _ = reproduce.check_run(run)
    assert status == "MISMATCH"
