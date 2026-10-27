"""Figures for the IEEE paper (vector PDF, no titles inside the image, print-friendly).

Values come from reports/final_test.json and the B3 test run folders, as in
scripts/make_final_figures.py. Writes paper/figures/*.pdf.

    python scripts/make_paper_figures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper" / "figures"
FINAL = json.loads((ROOT / "reports" / "final_test.json").read_text(encoding="utf-8"))
plt.rcParams.update({"font.family": "serif", "font.size": 8, "axes.spines.top": False,
                     "axes.spines.right": False, "pdf.fonttype": 42})
INK, EDGE = "#111111", "#444444"
EXT = "png" if "--preview" in sys.argv else "pdf"


def box(ax, x, y, w, h, title, lines=(), fill="white", bold_edge=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.015,rounding_size=0.06",
                                fc=fill, ec=INK, lw=1.3 if bold_edge else 0.8))
    ax.text(x + w / 2, y + h - 0.2, title, ha="center", va="center", fontsize=7.6, fontweight="bold", color=INK)
    for i, line in enumerate(lines):
        ax.text(x + w / 2, y + h - 0.45 - i * 0.2, line, ha="center", va="center", fontsize=6.5, color=INK)


def arrow(ax, x1, y1, x2, y2, rad=0.0, text=None, dx=0, dy=0.1):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=9, color=EDGE, lw=0.8,
                                 connectionstyle=f"arc3,rad={rad}"))
    if text:
        ax.text((x1 + x2) / 2 + dx, (y1 + y2) / 2 + dy, text, ha="center", fontsize=6.2, style="italic", color=INK)


def architecture():
    fig = plt.figure(figsize=(7.1, 2.6))
    ax = fig.add_axes((0, 0, 1, 1))  # use the full width so box text fits
    ax.set_xlim(0, 14.2)
    ax.set_ylim(0, 5.2)
    ax.axis("off")
    y, h, w = 2.9, 1.45, 2.05
    box(ax, 0.05, y, w, h, "Project input", ["description D", "intents I", "schema E, pool K"], fill="#eeeeee")
    box(ax, 2.4, y, w, h, "1. Analysis", ["validate inputs;", "describe each", "intent and slot"], fill="#e3e3e3", bold_edge=True)
    box(ax, 4.75, y, w, h, "2. Planning", ["rank options", "per factor;", "build c1, c2, c3"], fill="#e3e3e3", bold_edge=True)
    box(ax, 7.1, y, w, h, "3. Evaluation", ["run candidate", "on dev set;", "score it"])
    box(ax, 9.45, y, w, h, "5. Selection", ["lexicographic", "rule under", "constraints"])
    box(ax, 11.8, y, 2.3, h, "6. Export", ["versioned,", "hashed package;", "model identity"])
    for x in (2.1, 4.45, 6.8, 9.15, 11.5):
        arrow(ax, x, y + h / 2, x + 0.3, y + h / 2)
    box(ax, 7.1, 0.55, w, 1.35, "4. Revision", ["change one", "factor of c*;", "evaluate c4"], fill="#e3e3e3", bold_edge=True)
    arrow(ax, 8.4, y, 8.4, 1.9, text="scores", dx=0.35, dy=0.0)
    arrow(ax, 7.8, 1.9, 7.8, y, dx=0)
    box(ax, 0.05, 0.45, 6.55, 1.45, "Design space Θ = X × S × O  (|Θ| = 12)", [
        "X: joint | two-stage | schema-guided",
        "S: fixed | similarity-ranked examples",
        "O: model rejects | similarity threshold"], fill="#f7f7f7")
    arrow(ax, 4.0, 2.0, 5.3, y, rad=-0.15)
    box(ax, 9.45, 0.55, 4.65, 1.35, "Runtime", ["request → prompt (frozen design) → LM", "→ schema check, one repair", "→ span location → output"])
    arrow(ax, 12.95, y, 12.95, 1.9)
    ax.text(0.05, 4.85, "Shaded phases use the language model; evaluation budget: 3 initial + 1 revised candidate.",
            fontsize=6.5, style="italic", color=INK)
    fig.savefig(OUT / f"architecture.{EXT}", bbox_inches="tight", dpi=250)
    plt.close(fig)


def metric(project, system, key):
    systems = FINAL["projects"][project]["systems"]
    if system in systems:
        return systems[system][key]
    if system == "B4-random":
        return FINAL["projects"][project]["b4_random"]["mean_intent_macro_f1"]
    run = sorted((ROOT / "runs").glob(f"*_{project}_{system}-final_0"))
    return json.loads((run[-1] / "metrics.json").read_text(encoding="utf-8"))["primary"][key] if run else None


def intent_bars():
    systems = [("B0", "B0", "#ffffff", "//"), ("B1", "B1", "#bbbbbb", ""), ("B2", "B2", "#ffffff", ".."),
               ("B3-k", "B3-k", "#777777", ""), ("B4-random", "B4", "#dddddd", "xx"), ("A1", "A1", "#999999", "\\\\"),
               ("A2", "A2", "#222222", "")]
    fig, ax = plt.subplots(figsize=(3.45, 2.0))
    width = 0.11
    for i, (sid, label, fill, hatch) in enumerate(systems):
        for j, p in enumerate(("P1", "P2", "P3")):
            v = metric(p, sid, "intent_macro_f1")
            if v is None:
                continue
            ax.bar(j + (i - 3) * width, v, width * 0.92, color=fill, edgecolor=INK, lw=0.5, hatch=hatch,
                   label=label if j == 0 else None)
    ax.set_xticks([0, 1, 2], ["P1", "P2", "P3 (held out)"])
    ax.set_ylim(0.6, 0.95)
    ax.set_ylabel("Intent macro-F1 (test)")
    ax.legend(ncol=4, fontsize=6.2, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.28))
    fig.savefig(OUT / f"intent_test.{EXT}", bbox_inches="tight", dpi=250)
    plt.close(fig)


def forest():
    pairs = ["A2 vs B1", "A1 vs B1", "A2 vs B2", "A2 vs A1"]
    fig, ax = plt.subplots(figsize=(3.45, 2.25))
    y, ticks = 0, []
    for p in ("P1", "P2", "P3"):
        boot = FINAL["projects"][p]["bootstrap"]
        for pair in pairs:
            if pair not in boot:
                continue
            ci = boot[pair]["intent_macro_f1"]
            sig = ci["ci_low"] > 0 or ci["ci_high"] < 0
            d, lo, hi = (100 * ci[k] for k in ("difference", "ci_low", "ci_high"))  # percentage points
            ax.errorbar(d, y, xerr=[[d - lo], [hi - d]],
                        fmt="s" if sig else "o", color=INK, mfc=INK if sig else "white", capsize=2, lw=0.8, ms=3.5)
            ticks.append((y, f"{p}: {pair}"))
            y -= 1
        y -= 0.5
    ax.axvline(0, color=INK, lw=0.6, ls="--")
    ax.set_yticks([t[0] for t in ticks], [t[1] for t in ticks], fontsize=6.5)
    ax.set_xticks([-5, -2.5, 0, 2.5, 5, 7.5, 10])
    ax.set_xlabel("Δ intent macro-F1 (points, 95% CI)")
    fig.savefig(OUT / f"ci_test.{EXT}", bbox_inches="tight", dpi=250)
    plt.close(fig)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    architecture()
    intent_bars()
    forest()
    print("wrote paper/figures/architecture.pdf, intent_test.pdf, ci_test.pdf")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
