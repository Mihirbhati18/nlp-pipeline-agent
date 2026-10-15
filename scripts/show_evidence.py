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

    # 4. headline results
    say("\n## 4. Headline results (development data, intent macro-F1 / entity F1)")
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
    figures = sorted((ROOT / "reports" / "figures").glob("*.png"))
    for fig in figures:
        say(f"- `reports/figures/{fig.name}`")
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
