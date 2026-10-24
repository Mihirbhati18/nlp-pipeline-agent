"""Run A2 (decision 42) on development data and apply the keep-or-drop rule.

A2 = A1 with the improved Architect (factor-wise reasoning, one-factor
revision), using the same runtime model for planning as every system uses for
answers (decision 43). A2 is compared with A1, B1, B2, B3 and B4 on equal terms.

``--planning-model`` runs the same search with a different planner as an
ablation; such runs are recorded under a different system name.

The keep-or-drop rule from decision 42 is applied and printed: A2 goes to the
test set only if its development intent macro-F1 is at least A1's on every
project run. The run folders record the outcome either way.

Usage:
    python scripts/run_a2.py                                # A2
    python scripts/run_a2.py --planning-model qwen2.5:7b    # larger planner (ablation)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analyzer.access import access_for  # noqa: E402
from src.analyzer.spec import load_cases, load_spec  # noqa: E402
from src.architect.design_run import run_design  # noqa: E402
from src.evaluation.runs import new_run  # noqa: E402
from src.llm.client import make_client, model_details, ollama_version  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SINGLE_CALL_P95_S = 0.59  # same declared estimate the A1 design run used


def fmt(value, digits=3):
    return "n/a" if value is None else f"{value:.{digits}f}"


def a1_intent(project: str) -> float | None:
    runs = sorted((ROOT / "runs").glob(f"*_{project}_A1_0"))
    if not runs:
        return None
    return json.loads((runs[-1] / "metrics.json").read_text(encoding="utf-8"))["primary"]["intent_macro_f1"]


def main() -> int:
    parser = argparse.ArgumentParser(description="A2 design runs on development data")
    parser.add_argument("--model", default="qwen2.5:3b", help="runtime model (shared by every system)")
    parser.add_argument("--planning-model", default="qwen2.5:3b")
    parser.add_argument("--projects", nargs="+", default=["P1", "P2"])
    parser.add_argument("--host", default="http://127.0.0.1:11434")
    args = parser.parse_args()

    try:
        ollama_version(args.host)
    except Exception as exc:  # noqa: BLE001
        print(f"Cannot reach Ollama at {args.host}: {exc}", file=sys.stderr)
        return 2

    runtime = make_client(args.model, host=args.host, cache_dir=ROOT / "cache")
    planner = make_client(args.planning_model, host=args.host, cache_dir=ROOT / "cache")
    system = "A2" if args.planning_model == args.model else f"A2-planner-{args.planning_model.replace(':', '-')}"
    print(f"{system}: runtime {args.model} ({runtime.model_digest[:12]}), "
          f"planner {args.planning_model} ({planner.model_digest[:12]})\n")

    verdicts = {}
    for project in args.projects:
        spec = load_spec(project)
        access = access_for(spec)
        design = run_design(
            spec, access, runtime_client=runtime, planning_client=planner,
            load_cases=load_cases, single_call_p95_s=SINGLE_CALL_P95_S, architect_version="v2",
        )
        selected = design.selected_config_id
        chosen = next((e for e in design.evaluations if e.config_id == selected), None)
        intent = chosen.metrics["primary"]["intent_macro_f1"] if chosen else None
        with new_run(project, system, 0, {
            "system": system, "split": "dev", "architect_version": "v2",
            "model": runtime.model, "model_digest": runtime.model_digest,
            "model_details": model_details(runtime.model),
            "planning_model": planner.model, "planning_model_digest": planner.model_digest,
            "planning_model_details": model_details(planner.model),
            "settings": runtime.settings, "cache_enabled": True,
            "score_note": ("A2 was designed after seeing these development results (decision 42); "
                           "its development scores are not evidence of improvement. Only the frozen "
                           "test comparison counts."),
            "selected_config_id": selected, "oos_threshold": design.oos_threshold.as_dict(),
            "data_access": design.data_access, "data_sources": spec.source, **design.as_dict(),
        }, data_paths={"pool": spec.source["kshot"], "dev": spec.source["dev"]}) as log:
            for event in design.design.events:
                log.log_event(event.get("kind", "event"), **{k: v for k, v in event.items() if k != "kind"})
            if chosen:
                log.write_metrics(chosen.metrics)
            log.finish(status="complete", n_cases=len(load_cases(access.dev_path)))
            run_id = log.run_id

        print(f"=== {project}: {run_id} ===")
        rankings = next((e for e in design.design.events if e.get("kind") == "factor_rankings"), {})
        for factor, order in rankings.get("rankings", {}).items():
            print(f"  ranked {factor:18} {' > '.join(order)}  ({rankings['reasons'][factor][:70]})")
        for attempt in design.design.attempts:
            row = attempt.as_dict()
            print(f"  tried {row['config_id']:22} intent {fmt(row['intent_macro_f1'])} "
                  f"entity {fmt(row['entity_span_f1'])} [{row['source']}/{row['stage']}]")
        baseline = a1_intent(project)
        keep = intent is not None and baseline is not None and intent >= baseline
        verdicts[project] = keep
        print(f"  selected {selected}: intent {fmt(intent)} vs A1 {fmt(baseline)} -> "
              f"{'meets' if keep else 'FAILS'} the keep rule | "
              f"{design.design.reasoned_choices}/{design.design.budget_used} reasoned, "
              f"{design.design.planning_calls} planning calls\n")

    if system == "A2":
        verdict = all(verdicts.values()) and len(verdicts) == 2
        detail = ", ".join(f"{p}: {'meets' if v else 'fails'}" for p, v in verdicts.items())
        outcome = "GOES to the test set" if verdict else "is DROPPED"
        print(f"Decision 42 keep-or-drop rule: A2 {outcome} ({detail})")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
