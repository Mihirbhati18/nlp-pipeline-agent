"""Export A1's selected pipeline for each project as a loadable package (G9).

Re-runs the A1 design through the prediction cache, so the Analyzer
enrichment, the Architect's choices and the candidate scores are the ones
already computed and recorded; a fully cached re-run costs no model calls.
It then checks that the selection matches the most recent A1 run folder, so
the package provably corresponds to recorded evidence, and writes the package
under ``artifacts/<project>/``.

Usage:
    python scripts/export_pipeline.py                 # P1 and P2
    python scripts/export_pipeline.py --projects P1
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
from src.llm.client import make_client, ollama_version  # noqa: E402
from src.runtime.package import export_pipeline, load_pipeline  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SINGLE_CALL_P95_S = 0.59  # same declared estimate the G8 design run used


def latest_a1_run(project: str) -> tuple[str, dict] | None:
    runs = sorted((ROOT / "runs").glob(f"*_{project}_A1_*"))
    for run in reversed(runs):
        config = run / "config.json"
        if config.is_file():
            return run.name, json.loads(config.read_text(encoding="utf-8"))
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Export A1's selected pipelines")
    parser.add_argument("--model", default="qwen2.5:3b")
    parser.add_argument("--projects", nargs="+", default=["P1", "P2"])
    parser.add_argument("--host", default="http://127.0.0.1:11434")
    parser.add_argument("--out", default=str(ROOT / "artifacts"))
    args = parser.parse_args()

    try:
        ollama_version(args.host)
    except Exception as exc:  # noqa: BLE001
        print(f"Cannot reach Ollama at {args.host}: {exc}", file=sys.stderr)
        return 2

    client = make_client(args.model, host=args.host, cache_dir=ROOT / "cache")

    for project in args.projects:
        if project == "P3":
            print("P3 is the held-out project and is not exported before the freeze", file=sys.stderr)
            return 1
        spec = load_spec(project)
        access = access_for(spec)
        before = client.counter.as_dict()
        design = run_design(
            spec, access,
            runtime_client=client, planning_client=client,
            load_cases=load_cases, single_call_p95_s=SINGLE_CALL_P95_S,
        )
        after = client.counter.as_dict()
        selected = design.selected_config_id

        recorded = latest_a1_run(project)
        if recorded is None:
            print(f"{project}: no A1 run folder to tie the export to; run scripts/run_design.py first",
                  file=sys.stderr)
            return 1
        run_id, run_config = recorded
        if run_config.get("selected_config_id") != selected:
            print(f"{project}: this design selected {selected}, but {run_id} recorded "
                  f"{run_config.get('selected_config_id')}. Refusing to export a pipeline "
                  "that does not match the evidence.", file=sys.stderr)
            return 1

        out_dir = export_pipeline(
            spec=design.analysis.spec,
            config_id=selected,
            oos_threshold=design.oos_threshold.threshold,
            pool=load_cases(access.train_path),
            client=client,
            out_root=args.out,
            source={
                "system": "A1",
                "run_id": run_id,
                "selection_split": "dev",
                "design_cost": design.as_dict()["design_cost"],
                "note": "development scores are selection scores; reported results come from the frozen test runs",
            },
        )
        loaded = load_pipeline(out_dir, host=args.host)  # proves it reloads
        physical = after["physical_calls"] - before["physical_calls"]
        print(f"{project}: exported {selected} -> {out_dir.relative_to(ROOT)}")
        print(f"     package {loaded.package_hash[:12]} | tied to {run_id} | "
              f"{physical} uncached model calls during re-design")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
