"""Show, step by step, how the bootstrap intervals, the speed figures and the
error analysis were worked out (a teaching tool, like explain_f1.py).

    python scripts/explain_stats.py bootstrap   # A1 vs B1 on P1: resampling, shown draw by draw
    python scripts/explain_stats.py timing      # A1's 50 timed requests, sorted, median and p95 picked out
    python scripts/explain_stats.py errors      # A1's mistakes by category, with real examples

Each command reads the same files the experiments wrote and compares its
result with the recorded one. It changes nothing in the project.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.analyzer.spec import load_cases, load_spec  # noqa: E402
from src.evaluation.scorer import Prediction, score  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
LINE = "=" * 78


def latest(pattern: str) -> Path:
    found = sorted(RUNS.glob(pattern))
    if not found:
        raise SystemExit(f"no run folder matches {pattern}")
    return found[-1]


def predictions(run: Path) -> dict[str, Prediction]:
    out = {}
    with open(run / "predictions.jsonl", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            raw = row["schema_valid_raw"] if "schema_valid_raw" in row else row.get("schema_valid_final")
            out[row["case_id"]] = Prediction(
                case_id=row["case_id"], status=row["status"], intent=row.get("predicted_intent"),
                entities=row.get("predicted_entities") or [], schema_valid_raw=raw,
                schema_valid_final=bool(row.get("schema_valid_final", False)),
                retries=int(row.get("retries") or 0), error=row.get("error"))
    return out


def dev_analysis() -> dict:
    return json.loads((ROOT / "reports" / "dev_analysis.json").read_text(encoding="utf-8"))


# -- bootstrap ---------------------------------------------------------------


def cmd_bootstrap(project: str) -> int:
    spec = load_spec(project)
    cases = load_cases(spec.source["dev"])
    a_run, b_run = latest(f"*_{project}_A1-selected_0"), latest(f"*_{project}_B1_0")
    a, b = predictions(a_run), predictions(b_run)
    preds_a = [a[c["case_id"]] for c in cases]
    preds_b = [b[c["case_id"]] for c in cases]
    labels = spec.intent_names

    def f1(cs, ps):
        return score(cs, ps, labels=labels)["primary"]["intent_macro_f1"]

    print(LINE)
    print(f"Bootstrap: is A1 really better than B1 on {project}, or could it be luck?")
    print(f"  A1 answers: {a_run.relative_to(ROOT)}\\predictions.jsonl")
    print(f"  B1 answers: {b_run.relative_to(ROOT)}\\predictions.jsonl")
    print(LINE)
    real = f1(cases, preds_a) - f1(cases, preds_b)
    print(f"\nSTEP 1. On the real 100 requests: A1 {f1(cases, preds_a):.3f} - B1 {f1(cases, preds_b):.3f} "
          f"= difference {real:+.3f}")
    print("\nSTEP 2. Make a 'pretend' set of 100 requests by drawing request numbers at random,")
    print("        allowing repeats. Score BOTH systems on that same pretend set. Three examples:\n")
    rng = random.Random(7)
    for draw in range(1, 4):
        idx = [rng.randrange(len(cases)) for _ in range(len(cases))]
        cs = [dict(cases[i], case_id=f"{cases[i]['case_id']}#{k}") for k, i in enumerate(idx)]
        pa = [Prediction(**{**vars(preds_a[i]), "case_id": cs[k]["case_id"]}) for k, i in enumerate(idx)]
        pb = [Prediction(**{**vars(preds_b[i]), "case_id": cs[k]["case_id"]}) for k, i in enumerate(idx)]
        shown = ", ".join(f"#{i + 1}" for i in idx[:10])
        repeats = len(idx) - len(set(idx))
        print(f"  draw {draw}: requests {shown}, ... ({repeats} repeats, "
              f"{len(cases) - len(set(idx))} never drawn)")
        print(f"          A1 {f1(cs, pa):.3f}  B1 {f1(cs, pb):.3f}  difference {f1(cs, pa) - f1(cs, pb):+.3f}")

    spec_mod = importlib.util.spec_from_file_location("run_dev_analysis", ROOT / "scripts" / "run_dev_analysis.py")
    analysis = importlib.util.module_from_spec(spec_mod)
    spec_mod.loader.exec_module(analysis)
    print(f"\nSTEP 3. Do this {analysis.BOOTSTRAP_SAMPLES} times (fixed seed {analysis.BOOTSTRAP_SEED}), "
          "sort the 1,000 differences,")
    print("        and keep the middle 95%: that range is the 95% confidence interval.")
    ci = analysis.paired_bootstrap(cases, preds_a, preds_b, labels)["intent_macro_f1"]
    print(f"\n  interval = [{ci['ci_low']:+.3f}, {ci['ci_high']:+.3f}]   "
          f"A1 better in {ci['share_a_better'] * 100:.0f}% of the 1,000 draws")
    recorded = dev_analysis()["projects"][project]["bootstrap"]["A1 vs B1"]["intent_macro_f1"]
    print(f"  recorded in reports/dev_analysis.json: [{recorded['ci_low']:+.3f}, {recorded['ci_high']:+.3f}]"
          f"  -> {'same' if abs(recorded['ci_low'] - ci['ci_low']) < 1e-9 else 'DIFFERENT'}")
    print("\nSTEP 4. Read it: the interval includes 0, so with only 100 requests A1's lead over B1")
    print("        could still be luck. That is why the paper does not call it significant yet." if ci["ci_low"] <= 0 <= ci["ci_high"]
          else "        The interval is entirely above 0, so A1's lead is unlikely to be luck.")
    print(LINE)
    return 0


# -- timing --------------------------------------------------------------------


def cmd_timing(project: str) -> int:
    run = latest(f"*_{project}_A1-timing_0")
    rows = [json.loads(l) for l in open(run / "timing.jsonl", encoding="utf-8") if l.strip()]
    warm = [r for r in rows if r.get("warmup")]
    excluded = [r for r in rows if not r.get("warmup") and r.get("excluded")]
    timed = sorted(r["latency_s"] for r in rows if not r.get("warmup") and not r.get("excluded"))
    n = len(timed)
    median_i, p95_i = n // 2, min(n - 1, int(0.95 * n))
    print(LINE)
    print(f"Speed: how fast A1's chosen pipeline answers on {project}, with saved answers switched off")
    print(f"  file: {run.relative_to(ROOT)}\\timing.jsonl  (one line per request, time in seconds)")
    print(LINE)
    print(f"\nSTEP 1. {len(warm)} warm-up requests are ignored (the first one wakes the model up: "
          f"{warm[0]['latency_s']:.2f} s).")
    if excluded:
        print(f"        {len(excluded)} requests refused before reaching the model are left out.")
    print(f"\nSTEP 2. The {n} timed requests, sorted from fastest to slowest (seconds):\n")
    for start in range(0, n, 10):
        chunk = "  ".join(f"{start + j + 1:>2}:{v:.2f}" for j, v in enumerate(timed[start:start + 10]))
        print(f"   {chunk}")
    print(f"\nSTEP 3. Median = the middle value = number {median_i + 1} in the sorted list = {timed[median_i]:.2f} s")
    print(f"        p95 = the value 95% of requests are faster than = number {p95_i + 1} = {timed[p95_i]:.2f} s")
    recorded = dev_analysis()["projects"][project]["timing"]["A1"]
    print(f"\n  recorded in reports/dev_analysis.json: median {recorded['median_s']:.2f} s, p95 {recorded['p95_s']:.2f} s"
          f"  -> {'same' if abs(recorded['median_s'] - timed[median_i]) < 1e-9 else 'DIFFERENT'}")
    print(LINE)
    return 0


# -- errors ----------------------------------------------------------------------


def cmd_errors(project: str) -> int:
    errors = dev_analysis()["projects"][project]["errors"]
    print(LINE)
    print(f"Error analysis: A1's mistakes on the {project} development requests, by category")
    print("  source: reports/dev_analysis.json (written by scripts/run_dev_analysis.py)")
    print(LINE)
    for category, count in errors["counts"].items():
        print(f"\n{category}: {count}")
        for example in errors["examples"].get(category, [])[:3]:
            print(f"    e.g. {example}")
    if errors["top_confusions"]:
        print("\nIntents mixed up most often:")
        for c in errors["top_confusions"]:
            print(f"    correct {c['gold']} -> answered {c['predicted']} ({c['count']} times)")
    print(LINE)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Explain the bootstrap, timing and error analysis")
    parser.add_argument("what", choices=["bootstrap", "timing", "errors"])
    parser.add_argument("--project", choices=["P1", "P2"], default="P1")
    args = parser.parse_args()
    return {"bootstrap": cmd_bootstrap, "timing": cmd_timing, "errors": cmd_errors}[args.what](args.project)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
