"""Interleaved latency timing: B1, A1 and A2 take turns on the same requests.

Timings taken on different days drifted by about 2x on this laptop (GPU
temperature, other programs using the GPU, an Ollama update), so comparing a
system timed today with one timed last week is not fair. Here every request is
sent to each system in turn, with the cache disabled, so any slowdown hits all
of them equally. The plan's settings are kept: 5 warm-up requests (not
counted), then 50 fixed development requests; requests refused before
reaching the model are excluded.

The success rule's latency limit is L_max = 2 x B1's p95 from the same session.

    python scripts/run_timing.py                  # P1 and P2
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analyzer.access import access_for  # noqa: E402
from src.analyzer.spec import load_cases, load_spec  # noqa: E402
from src.architect.design_run import run_design  # noqa: E402
from src.evaluation.runs import new_run  # noqa: E402
from src.llm.client import make_client  # noqa: E402
from src.pipelines.catalogue import B1_CONFIG_ID, ConfigRunner, get_config  # noqa: E402
from src.pipelines.examples import ExampleSelector  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
WARMUP, N_CASES = 5, 50


def summary(values):
    s = sorted(values)
    return {"n": len(s), "median_s": s[len(s) // 2], "p95_s": s[min(len(s) - 1, int(0.95 * len(s)))]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Interleaved timing of B1, A1 and A2")
    parser.add_argument("--projects", nargs="+", default=["P1", "P2"])
    args = parser.parse_args()

    cached = make_client("qwen2.5:3b", cache_dir=ROOT / "cache")   # for the (cached) design runs
    live = cached.with_cache_disabled()                             # for timing: never served from cache
    report = {"generated": time.strftime("%Y-%m-%d %H:%M"), "method": "interleaved, cache disabled",
              "warmup": WARMUP, "n_cases": N_CASES, "projects": {}}

    for project in args.projects:
        spec = load_spec(project)
        access = access_for(spec)
        pool, dev = load_cases(access.train_path), load_cases(access.dev_path)
        kw = dict(load_cases=load_cases, single_call_p95_s=0.59)
        a1 = run_design(spec, access, runtime_client=cached, planning_client=cached, **kw)
        a2 = run_design(spec, access, runtime_client=cached, planning_client=cached, architect_version="v2", **kw)
        selector = ExampleSelector(list(pool))
        threshold = a1.oos_threshold.threshold
        systems = {
            "B1": ConfigRunner(get_config(B1_CONFIG_ID), spec, live, selector, threshold),
            "A1": ConfigRunner(get_config(a1.selected_config_id), a1.analysis.spec, live, selector, threshold),
            "A2": ConfigRunner(get_config(a2.selected_config_id), a2.analysis.spec, live, selector, threshold),
        }
        times = {name: [] for name in systems}
        excluded = {name: 0 for name in systems}

        for case in dev[:WARMUP]:                          # warm-up, not counted
            for runner in systems.values():
                runner.run_case(case)
        for case in dev[WARMUP:WARMUP + N_CASES]:
            for name, runner in systems.items():           # every system on the same request, in turn
                start = time.perf_counter()
                outcome = runner.run_case(case)
                elapsed = time.perf_counter() - start
                if outcome.rejected_by_threshold:
                    excluded[name] += 1
                else:
                    times[name].append(elapsed)

        result = {}
        for name, runner in systems.items():
            stats = summary(times[name])
            with new_run(project, f"{name}-timing-interleaved", 0, {
                "system": name, "split": "dev-timing", "config_id": runner.config.config_id,
                "method": "interleaved with the other systems, cache disabled", "warmup": WARMUP,
                "model": live.model, "model_digest": live.model_digest, "cache_enabled": False,
            }) as log:
                for value in times[name]:
                    log.log_timing(latency_s=value, warmup=False)
                log.write_metrics({**stats, "excluded_threshold_rejections": excluded[name]})
                log.finish(status="complete")
                stats["run_id"] = log.run_id
            stats["config_id"] = runner.config.config_id
            result[name] = stats
        l_max = 2 * result["B1"]["p95_s"]
        result["L_max_s"] = l_max
        report["projects"][project] = result
        for name in systems:
            r = result[name]
            ok = "" if name == "B1" else (" within L_max" if r["p95_s"] <= l_max else " EXCEEDS L_max")
            print(f"{project} {name} {r['config_id']:20} median {r['median_s']:.2f} s  p95 {r['p95_s']:.2f} s{ok}")
        print(f"{project} L_max = 2 x B1 p95 = {l_max:.2f} s")

    out = ROOT / "reports" / "timing_interleaved.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
