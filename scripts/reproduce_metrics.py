"""Recompute every run's metrics from its saved predictions and compare (G12 check).

The plan's reproduction condition: metrics recompute from saved predictions.
For each run folder that has ``predictions.jsonl``, this rebuilds the
predictions, re-scores them with the shared scorer against the project's
cases, and compares every primary metric with the run's ``metrics.json``.
A mismatch means a number was produced some other way than the code says.

Runs with no saved predictions (timing runs, the throughput test, design runs
whose candidates are scored inside the run) are listed as not checkable,
never silently skipped.

Usage:
    python scripts/reproduce_metrics.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analyzer.spec import load_cases, load_spec  # noqa: E402
from src.evaluation.scorer import Prediction, score  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TOLERANCE = 1e-9


def rebuild(row: dict) -> Prediction:
    # B0 and B3 produce no generated text, so their raw output cannot be
    # malformed and their runners set raw validity equal to final validity.
    # Runs before 16 Oct did not write that field to the log; the same rule
    # recovers it. Systems with a repair stage always logged it.
    raw = row["schema_valid_raw"] if "schema_valid_raw" in row else row.get("schema_valid_final")
    return Prediction(
        case_id=row["case_id"],
        status=row["status"],
        intent=row.get("predicted_intent"),
        entities=row.get("predicted_entities") or [],
        schema_valid_raw=raw,
        schema_valid_final=bool(row.get("schema_valid_final", False)),
        retries=int(row.get("retries") or 0),
        error=row.get("error"),
    )


def same(a, b) -> bool:
    if a is None or b is None:
        return a is b
    if isinstance(a, float) or isinstance(b, float):
        return math.isclose(a, b, abs_tol=TOLERANCE)
    return a == b


def check_run(run: Path) -> tuple[str, str]:
    config = json.loads((run / "config.json").read_text(encoding="utf-8"))
    metrics_path = run / "metrics.json"
    project = config.get("project")
    if project not in ("P1", "P2", "P3") or not metrics_path.is_file():
        return "not checkable", "no project metrics"
    split = config.get("split", "dev")
    if split != "dev":
        return "not checkable", f"split {split}"

    spec = load_spec(project)
    cases = load_cases(spec.source["dev"])
    variant = config.get("variant")
    if variant:
        # Robustness runs were scored on rewritten requests. Rebuild exactly
        # the same rewrites (fixed seed) so the gold spans match what was scored.
        sys.path.insert(0, str(ROOT / "scripts"))
        from run_robustness import perturb

        cases = perturb(cases, variant)
    with open(run / "predictions.jsonl", encoding="utf-8") as handle:
        predictions = [rebuild(json.loads(line)) for line in handle if line.strip()]

    recorded = json.loads(metrics_path.read_text(encoding="utf-8"))
    recomputed = score(cases, predictions, labels=recorded.get("intent_label_set") or spec.intent_names)

    diffs = []
    for key, value in recorded["primary"].items():
        if isinstance(value, (int, float)) or value is None:
            if not same(value, recomputed["primary"].get(key)):
                diffs.append(f"{key}: recorded {value}, recomputed {recomputed['primary'].get(key)}")
    if diffs:
        return "MISMATCH", "; ".join(diffs[:3])
    p = recorded["primary"]
    return "match", f"intent {p['intent_macro_f1']:.3f}, entity {p['entity_span_f1']:.3f}, {len(predictions)} predictions"


def main() -> int:
    rows = []
    for run in sorted(p for p in (ROOT / "runs").iterdir() if p.is_dir()):
        if not (run / "predictions.jsonl").is_file():
            rows.append((run.name, "not checkable", "no saved predictions"))
            continue
        try:
            status, detail = check_run(run)
        except Exception as exc:  # noqa: BLE001
            status, detail = "ERROR", f"{type(exc).__name__}: {exc}"
        rows.append((run.name, status, detail))

    for name, status, detail in rows:
        print(f"{status:14} {name:42} {detail}")
    counts = {s: sum(1 for _, st, _ in rows if st == s) for s in {st for _, st, _ in rows}}
    print(f"\n{counts}")
    return 1 if counts.get("MISMATCH") or counts.get("ERROR") else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
