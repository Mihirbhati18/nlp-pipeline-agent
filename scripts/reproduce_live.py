"""G12 reproduction: re-run experiments from scratch and compare with the recorded results.

1. B0 on P1 test, retrained from nothing (no model, no cache): every metric must match.
2. A2 on the first 50 P1 test requests, asked LIVE with the prediction cache disabled:
   every answer is compared with the recorded test prediction, which shows the model
   really reproduces the answers rather than the cache replaying them.

Writes reports/reproduction_live.json. Run after the freeze:
    python scripts/reproduce_live.py --freeze-commit <hash>
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analyzer.access import access_for  # noqa: E402
from src.analyzer.spec import load_cases, load_spec  # noqa: E402
from src.architect.design_run import run_design  # noqa: E402
from src.baselines.b0_tfidf import B0TfidfClassifier  # noqa: E402
from src.evaluation.scorer import score  # noqa: E402
from src.llm.client import make_client  # noqa: E402
from src.pipelines.catalogue import ConfigRunner, get_config  # noqa: E402
from src.pipelines.examples import ExampleSelector  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
N_LIVE = 50


def recorded(project: str, system: str):
    run = sorted((ROOT / "runs").glob(f"*_{project}_{system}-final_0"))[-1]
    metrics = json.loads((run / "metrics.json").read_text(encoding="utf-8"))["primary"]
    preds = {json.loads(l)["case_id"]: json.loads(l) for l in open(run / "predictions.jsonl", encoding="utf-8") if l.strip()}
    return run.name, metrics, preds


def main() -> int:
    parser = argparse.ArgumentParser(description="Live reproduction check")
    parser.add_argument("--freeze-commit", required=True)
    args = parser.parse_args()

    spec = load_spec("P1")
    access = access_for(spec).release_after_freeze(commit=args.freeze_commit)
    pool, dev, test = load_cases(access.train_path), load_cases(access.dev_path), load_cases(access.test_path)
    report = {"freeze_commit": args.freeze_commit}

    # 1. B0 from scratch
    run, rec, _ = recorded("P1", "B0")
    b0 = B0TfidfClassifier(labels=spec.intent_names).fit(pool)
    b0.tune(dev)
    fresh = score(test, b0.predict(test), labels=spec.intent_names)["primary"]
    keys = [k for k, v in rec.items() if isinstance(v, (int, float)) and v is not None]
    same = all(math.isclose(rec[k], fresh[k], abs_tol=1e-9) for k in keys if fresh.get(k) is not None)
    report["B0"] = {"recorded_run": run, "metrics_compared": len(keys), "identical": same,
                    "intent_macro_f1": fresh["intent_macro_f1"]}
    print(f"B0 retrained from scratch on P1 test: intent {fresh['intent_macro_f1']:.4f} "
          f"(recorded {rec['intent_macro_f1']:.4f}) -> {'identical' if same else 'DIFFERENT'} on {len(keys)} metrics")

    # 2. A2 asked live, cache disabled
    run, _, rec_preds = recorded("P1", "A2")
    cached = make_client("qwen2.5:3b", cache_dir=ROOT / "cache")
    live = cached.with_cache_disabled()
    design = run_design(spec, access, runtime_client=cached, planning_client=cached, load_cases=load_cases,
                        single_call_p95_s=0.59, architect_version="v2")
    runner = ConfigRunner(get_config(design.selected_config_id), design.analysis.spec, live,
                          ExampleSelector(list(pool)), design.oos_threshold.threshold)
    agree = 0
    differences = []
    for case in test[:N_LIVE]:
        p = runner.run_case(case).prediction
        r = rec_preds[case["case_id"]]
        match = (p.status == r["status"] and p.intent == r["predicted_intent"]
                 and p.entities == (r["predicted_entities"] or []))
        agree += match
        if not match:
            differences.append({"case_id": case["case_id"], "live": [p.status, p.intent, p.entities],
                                "recorded": [r["status"], r["predicted_intent"], r["predicted_entities"]]})
    report["A2_live"] = {"recorded_run": run, "design": design.selected_config_id, "requests": N_LIVE,
                         "identical_answers": agree, "physical_calls": live.counter.physical_calls,
                         "differences": differences}
    print(f"A2 asked live ({live.counter.physical_calls} real model calls, cache off) on {N_LIVE} P1 test requests: "
          f"{agree} of {N_LIVE} answers identical to the recorded ones")

    out = ROOT / "reports" / "reproduction_live.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
