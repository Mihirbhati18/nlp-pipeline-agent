"""Save per-request predictions for A1's and A2's selected pipelines.

The A1 and A2 design runs record the metrics of their selected configuration
but not its per-request predictions, so the independent checks
(`reproduce_metrics.py`, `verify_with_sklearn.py`) could not cover the two
headline systems. This replays each selected configuration over the
development split through the prediction cache (the same answers the design
run scored, no new model calls) and writes one run folder per system and
project with the predictions, so both checks now cover A1 and A2 too.

Usage:
    python scripts/record_selected_predictions.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analyzer.access import access_for  # noqa: E402
from src.analyzer.spec import load_cases, load_spec  # noqa: E402
from src.architect.design_run import run_design  # noqa: E402
from src.evaluation.runs import new_run  # noqa: E402
from src.evaluation.scorer import score  # noqa: E402
from src.llm.client import make_client  # noqa: E402
from src.pipelines.catalogue import ConfigRunner, get_config  # noqa: E402
from src.pipelines.examples import ExampleSelector  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    client = make_client("qwen2.5:3b", cache_dir=ROOT / "cache")
    for project in ("P1", "P2"):
        spec = load_spec(project)
        access = access_for(spec)
        pool, dev = load_cases(access.train_path), load_cases(access.dev_path)
        for system, version in (("A1", "v1"), ("A2", "v2")):
            design = run_design(spec, access, runtime_client=client, planning_client=client,
                                load_cases=load_cases, single_call_p95_s=0.59, architect_version=version)
            selected = design.selected_config_id
            recorded = sorted((ROOT / "runs").glob(f"*_{project}_{system}_0"))[-1]
            assert json.loads((recorded / "config.json").read_text(encoding="utf-8"))["selected_config_id"] == selected
            before = client.counter.physical_calls
            runner = ConfigRunner(config=get_config(selected), spec=design.analysis.spec, client=client,
                                  selector=ExampleSelector(list(pool)),
                                  oos_threshold=design.oos_threshold.threshold)
            predictions = [runner.run_case(c).prediction for c in dev]
            metrics = score(dev, predictions, labels=spec.intent_names)
            with new_run(project, f"{system}-selected", 0, {
                "split": "dev", "system": system, "selected_config_id": selected,
                "design_run": recorded.name,
                "purpose": "per-request predictions of the selected pipeline, replayed from the cache",
                "model": client.model, "model_digest": client.model_digest,
            }, data_paths={"pool": spec.source["kshot"], "dev": spec.source["dev"]}) as log:
                for case, p in zip(dev, predictions):
                    log.log_prediction(case_id=case["case_id"], gold_intent=case["true_intent"],
                                       gold_in_scope=case["in_scope"], status=p.status,
                                       predicted_intent=p.intent, predicted_entities=p.entities,
                                       schema_valid_raw=p.schema_valid_raw,
                                       schema_valid_final=p.schema_valid_final,
                                       retries=p.retries, error=p.error)
                log.write_metrics(metrics)
                log.finish(status="complete", n_cases=len(dev))
            design_metrics = json.loads((recorded / "metrics.json").read_text(encoding="utf-8"))["primary"]
            same = design_metrics["intent_macro_f1"] == metrics["primary"]["intent_macro_f1"]
            print(f"{project} {system} {selected}: intent {metrics['primary']['intent_macro_f1']:.3f} "
                  f"(design run recorded {design_metrics['intent_macro_f1']:.3f}, {'same' if same else 'DIFFERENT'}), "
                  f"{client.counter.physical_calls - before} new model calls")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
