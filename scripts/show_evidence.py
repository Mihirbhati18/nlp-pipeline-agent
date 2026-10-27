"""Run every check in one go and print the evidence summary.

For showing the project: one command runs the automated tests, re-checks
every recorded result against its saved predictions, counts the run folders,
prints the headline results from them, lists the figures, and runs the live
demo if the model is available. The same summary is saved to
``reports/EVIDENCE_SUMMARY.md`` with the time it was produced.

Usage:
    python scripts/show_evidence.py
    python scripts/show_evidence.py --no-demo
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
lines: list[str] = []


def say(text: str = "") -> None:
    print(text)
    lines.append(text)


def run(cmd: list[str], timeout: int = 900) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout,
                            encoding="utf-8", errors="replace")
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def latest_primary(project: str, system: str) -> dict | None:
    found = sorted(RUNS.glob(f"*_{project}_{system}_0"))
    if not found or not (found[-1] / "metrics.json").is_file():
        return None
    return json.loads((found[-1] / "metrics.json").read_text(encoding="utf-8"))["primary"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run every check and summarise the evidence")
    parser.add_argument("--no-demo", action="store_true")
    args = parser.parse_args()
    py = sys.executable
    failures = 0

    say(f"# Evidence summary ({time.strftime('%d %b %Y %H:%M')})")
    commit = run(["git", "log", "-1", "--format=%h %s"])[1].strip()
    commits = run(["git", "rev-list", "--count", "HEAD"])[1].strip()
    say(f"\nCode version: `{commit}` ({commits} commits in the history)")

    # 1. automated tests
    say("\n## 1. Automated tests")
    code, out = run([py, "-m", "pytest", "tests"])
    summary = next((l for l in reversed(out.splitlines()) if re.search(r"passed|failed", l)), out[-200:])
    say(f"`python -m pytest tests` -> **{summary.strip().strip('=').strip()}**")
    failures += code != 0

    # 2. reproduction
    say("\n## 2. Results recomputed from saved predictions")
    code, out = run([py, "scripts/reproduce_metrics.py"])
    counts = out.strip().splitlines()[-1] if out.strip() else ""
    say(f"`python scripts/reproduce_metrics.py` -> {counts}")
    say("Every run with saved predictions was re-scored; a 'match' means the recorded number "
        "is exactly what the code computes.")
    failures += code != 0

    # 2b. independent recomputation with scikit-learn
    say("\n## 2b. Metrics recomputed independently with scikit-learn")
    code, out = run([py, "scripts/verify_with_sklearn.py"])
    tail = [l for l in out.strip().splitlines() if l.startswith("{")]
    say(f"`python scripts/verify_with_sklearn.py` -> {tail[-1] if tail else out[-200:]}")
    say("scikit-learn, the standard machine-learning library, recomputed intent macro-F1, accuracy and "
        "out-of-scope precision, recall and F1 from the saved predictions without using our scorer.")
    failures += code != 0

    # 3. run folders
    say("\n## 3. Recorded experiment runs")
    kinds = Counter()
    for run_dir in RUNS.iterdir():
        if run_dir.is_dir():
            parts = run_dir.name.split("_")
            kinds[parts[3] if len(parts) > 3 else run_dir.name] += 1
    say(f"{sum(kinds.values())} run folders in `runs/`, each with its config, manifest "
        "(git commit, model digest, data hashes) and metrics:")
    for kind, n in sorted(kinds.items()):
        say(f"- {kind}: {n}")

    # 4. final results on the locked test data (after the G10 freeze)
    final_path = ROOT / "reports" / "final_test.json"
    if final_path.is_file():
        final = json.loads(final_path.read_text(encoding="utf-8"))
        say(f"\n## 4. Final results on the locked test data (freeze commit `{final['freeze_commit'][:10]}`)")
        say("Intent macro-F1 / entity F1 / out-of-scope F1. P3 was held out until the freeze.")
        say("\n| System | P1 | P2 | P3 |\n|---|---|---|---|")
        for label, system in (("B0 word matching", "B0"), ("B1 generic prompt", "B1"), ("B2 human", "B2"),
                              ("B3-k XLM-R, same examples", "B3-k"), ("B3-full XLM-R, all data", "B3-full"),
                              ("A1 first agent", "A1"), ("A2 improved agent", "A2")):
            cells = []
            for project in ("P1", "P2", "P3"):
                m = final["projects"][project]["systems"].get(system) or latest_primary(project, f"{system}-final")
                cells.append("not run" if m is None else
                             f"{m['intent_macro_f1']:.3f} / {m['entity_span_f1']:.3f} / {m['oos_f1']:.3f}")
            say(f"| {label} | {' | '.join(cells)} |")
        cells = [f"{final['projects'][p]['b4_random']['mean_intent_macro_f1']:.3f} "
                 f"({final['projects'][p]['b4_random']['min']:.3f}-{final['projects'][p]['b4_random']['max']:.3f})"
                 for p in ("P1", "P2", "P3")]
        say(f"| B4 random search, mean intent (range) | {' | '.join(cells)} |")
        say("\nA2 against B1, intent macro-F1 difference with 95% paired bootstrap interval:")
        for project in ("P1", "P2", "P3"):
            ci = final["projects"][project]["bootstrap"]["A2 vs B1"]["intent_macro_f1"]
            say(f"- {project}: {ci['difference']:+.3f} [{ci['ci_low']:+.3f}, {ci['ci_high']:+.3f}]")
        say("Figures: `reports/figures/final/`; paper version: `paper/figures/`.")

    # 4b. live reproduction (model asked again with the cache off)
    live_path = ROOT / "reports" / "reproduction_live.json"
    if live_path.is_file():
        live = json.loads(live_path.read_text(encoding="utf-8"))
        a2 = live.get("A2_live", {})
        say("\n## 4b. Live reproduction (`python scripts/reproduce_live.py`)")
        say(f"- B0 retrained from scratch: {'identical' if live['B0']['identical'] else 'DIFFERENT'} on "
            f"{live['B0']['metrics_compared']} metrics")
        say(f"- A2 asked live, cache off: {a2.get('identical_answers')} of {a2.get('requests')} P1 test answers "
            f"identical to the recorded ones ({a2.get('physical_calls')} real model calls)")

    # 4c. development results, kept for comparison
    say("\n## 4c. Development results (before the freeze, intent macro-F1 / entity F1)")
    say("\n| System | P1 | P2 |\n|---|---|---|")
    for label, system in (("B0 word matching", "B0"), ("B1 generic prompt", "B1"),
                          ("B3-k published, matched", "B3-k"), ("A1 our agent", "A1"),
                          ("B3-full, all data (reference)", "B3-full")):
        cells = []
        for project in ("P1", "P2"):
            p = latest_primary(project, system)
            cells.append("n/a" if p is None else f"{p['intent_macro_f1']:.3f} / {p['entity_span_f1']:.3f}")
        say(f"| {label} | {cells[0]} | {cells[1]} |")
    say("\nFull analysis: `reports/DEV_ANALYSIS.md`; findings with caveats: `docs/FINDINGS.md`.")

    # 5. figures
    say("\n## 5. Figures")
    figures = sorted((ROOT / "reports" / "figures").glob("*.png")) + sorted(
        (ROOT / "reports" / "figures" / "final").glob("*.png"))
    for fig in figures:
        say(f"- `{fig.relative_to(ROOT).as_posix()}`")
    if not figures:
        say("none yet: run `python scripts/make_figures.py`")

    # 6. demo
    say("\n## 6. Live demo of the exported pipeline")
    if args.no_demo:
        say("skipped (--no-demo)")
    else:
        code, out = run([py, "scripts/demo.py", "--project", "P1"], timeout=600)
        if code == 0:
            say("```")
            for line in out.strip().splitlines():
                say(line)
            say("```")
        else:
            say("Demo could not run (is Ollama open?). Start the Ollama app and run "
                "`python scripts/demo.py --project P1`.")
            say(f"Detail: {out.strip().splitlines()[-1] if out.strip() else 'no output'}")

    say(f"\n**Overall: {'all checks passed' if failures == 0 else f'{failures} check(s) failed'}**")
    out_path = ROOT / "reports" / "EVIDENCE_SUMMARY.md"
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nsaved to {out_path.relative_to(ROOT)}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
