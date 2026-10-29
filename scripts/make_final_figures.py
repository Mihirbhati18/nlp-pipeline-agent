"""Draw the final-result figures from the locked test runs (G11).

Every value is read from reports/final_test.json or a *-final_0 run folder.
Writes PNGs (300 dpi) to reports/figures/final/ and SOURCES.md listing the run
behind each value.

    python scripts/make_final_figures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "figures" / "final"
FINAL = json.loads((ROOT / "reports" / "final_test.json").read_text(encoding="utf-8"))
PROJECTS = ["P1", "P2", "P3"]
NAMES = {"P1": "P1 Home assistant", "P2": "P2 Productivity", "P3": "P3 Ordering & travel (held out)"}
AGENT, A1_COL, OTHER, DARK, REF, INK = "#000000", "#8c8c8c", "#c8c8c8", "#4d4d4d", "#e6e6e6", "#1a1a1a"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#a6a6a6", "text.color": INK, "axes.labelcolor": INK})
sources: list[str] = []


def metric(project: str, system: str, key: str):
    """A system's test metric: from final_test.json, or from the B3 test run folders."""
    systems = FINAL["projects"][project]["systems"]
    if system in systems:
        sources.append(f"- {project} {system}: `{systems[system]['run_id']}`")
        return systems[system][key]
    if system == "B4-random":
        return FINAL["projects"][project]["b4_random"]["mean_intent_macro_f1"] if key == "intent_macro_f1" else None
    runs = sorted((ROOT / "runs").glob(f"*_{project}_{system}-final_0"))
    if not runs:
        return None
    sources.append(f"- {project} {system}: `{runs[-1].name}`")
    return json.loads((runs[-1] / "metrics.json").read_text(encoding="utf-8"))["primary"][key]


def save(fig, name, caption):
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=300, bbox_inches="tight")
    plt.close(fig)
    sources.append(f"\n**{name}**: {caption}\n")
    print(f"wrote reports/figures/final/{name}")


SYSTEMS = [("B0", "B0 word matching", OTHER), ("B1", "B1 generic prompt", "#a6a6a6"),
           ("B2", "B2 manual", "#e6e6e6"), ("B3-k", "B3-k XLM-R (matched)", DARK),
           ("B4-random", "B4 random search (mean)", "#ffffff"), ("A1", "A1 agent", A1_COL), ("A2", "A2 agent", AGENT)]


def grouped(key, title, ylabel, name, caption, ylim, skip=()):
    fig, ax = plt.subplots(figsize=(11, 4.4))
    systems = [s for s in SYSTEMS if s[0] not in skip]
    width = 0.8 / len(systems)
    for i, (sid, label, colour) in enumerate(systems):
        for j, p in enumerate(PROJECTS):
            v = metric(p, sid, key)
            if v is None:
                continue
            x = j + (i - (len(systems) - 1) / 2) * width
            # Greyscale only, so the busiest series also get a pattern to stay distinguishable.
            hatch = {"B4-random": "//", "A1": "xx"}.get(sid)
            ax.bar(x, v, width * 0.95, color=colour, label=label if j == 0 else None, hatch=hatch,
                   edgecolor="#333333", linewidth=0.5)
            ax.text(x, v + 0.008, f"{v:.2f}", ha="center", fontsize=6.8, rotation=90)
    ax.set_xticks(range(len(PROJECTS)), [NAMES[p] for p in PROJECTS])
    ax.set_ylim(*ylim)
    ax.set_ylabel(ylabel)
    ax.legend(ncol=len(systems), fontsize=7.6, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.09))
    ax.set_title(title, fontsize=11, fontweight="bold")
    save(fig, name, caption)


def forest():
    pairs = [("A2 vs B1", AGENT), ("A1 vs B1", A1_COL), ("A2 vs B2", DARK), ("A2 vs A1", "#a6a6a6")]
    fig, ax = plt.subplots(figsize=(8.5, 4.6))
    y, labels = 0, []
    for p in PROJECTS:
        boot = FINAL["projects"][p]["bootstrap"]
        for pair, colour in pairs:
            if pair not in boot:
                continue
            ci = boot[pair]["intent_macro_f1"]
            ax.errorbar(ci["difference"], y, xerr=[[ci["difference"] - ci["ci_low"]], [ci["ci_high"] - ci["difference"]]],
                        fmt="o", color=colour, ecolor=colour, capsize=3, lw=1.5)
            ax.text(ci["ci_high"] + 0.004, y, f"{ci['difference']:+.3f} [{ci['ci_low']:+.3f}, {ci['ci_high']:+.3f}]",
                    va="center", fontsize=7.5)
            labels.append((y, f"{p}  {pair}"))
            y -= 1
        y -= 0.6
    ax.axvline(0, color=INK, lw=1, ls="--")
    ax.set_yticks([l[0] for l in labels], [l[1] for l in labels], fontsize=8.5)
    ax.set_xlabel("Difference in intent macro-F1 on test (95% paired bootstrap interval)")
    ax.set_title("Where the interval clears 0, the difference is unlikely to be chance", fontsize=11, fontweight="bold")
    ax.set_xlim(-0.08, 0.17)
    save(fig, "final3_differences_ci.png", "Paired bootstrap intervals, 1,000 resamples, from reports/final_test.json.")


def ablations():
    variants = [("A1", "A1 full"), ("A1-noAnalyzer", "no Analyzer"), ("A1-noReasoning", "no reasoning"),
                ("A1-noSelection", "no scored selection"), ("A1-noRepair", "no repair")]
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.8), sharey=True)
    for ax, p in zip(axes, PROJECTS):
        vals = [metric(p, v, "intent_macro_f1") for v, _ in variants]
        bars = ax.bar(range(len(variants)), vals, color=[A1_COL] + [OTHER] * (len(variants) - 1), width=0.65)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, v + 0.004, f"{v:.3f}", ha="center", fontsize=7.5)
        ax.set_xticks(range(len(variants)), [l for _, l in variants], rotation=30, ha="right", fontsize=8)
        ax.set_ylim(0.78, 0.94)
        ax.set_title(NAMES[p], fontsize=9.5)
    axes[0].set_ylabel("Intent macro-F1 (test)")
    fig.suptitle("Ablations on test: scored selection helps on P1 and P2, but not on the held-out P3", fontsize=11, fontweight="bold")
    save(fig, "final4_ablations.png", "Each bar removes one component of A1; choices made on development data.")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    grouped("intent_macro_f1", "Intent macro-F1 on the locked test data", "Intent macro-F1 (test)",
            "final1_intent.png", "300 test requests (P1, P2), 200 (P3). B2 not run on P3.", (0.6, 1.0))
    grouped("entity_span_f1", "Entity span F1 on the locked test data", "Entity span F1 (test)",
            "final2_entity.png", "B0 extracts no entities; B4-random reports intent only.", (0.0, 0.85),
            skip=("B0", "B4-random"))
    forest()
    ablations()
    (OUT / "SOURCES.md").write_text("# Final figure sources\n\nGenerated by `python scripts/make_final_figures.py` "
                                   "from the locked test runs.\n\n" + "\n".join(dict.fromkeys(sources)) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
