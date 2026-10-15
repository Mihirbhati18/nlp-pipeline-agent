"""Draw the paper and presentation figures from the recorded runs.

Every number is read from a run folder or a report JSON, never typed in, so
each figure traces back to its evidence. Writes PNGs (300 dpi) to
``reports/figures/`` plus ``reports/figures/SOURCES.md`` listing the run each
value came from.

Usage:
    python scripts/make_figures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
OUT = ROOT / "reports" / "figures"

AGENT = "#2563eb"   # the system under study
OTHER = "#94a3b8"   # baselines
REF = "#cbd5e1"     # references that are not matched comparisons
INK = "#1e293b"
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#64748b", "axes.labelcolor": INK, "text.color": INK,
                     "xtick.color": INK, "ytick.color": INK})

sources: list[str] = []


def latest(project: str, system: str) -> Path | None:
    found = sorted(RUNS.glob(f"*_{project}_{system}_0"))
    return found[-1] if found else None


def primary(project: str, system: str) -> dict | None:
    run = latest(project, system)
    if run is None or not (run / "metrics.json").is_file():
        return None
    sources.append(f"- {project} {system}: `{run.name}`")
    return json.loads((run / "metrics.json").read_text(encoding="utf-8"))["primary"]


def b4_random(project: str) -> dict:
    run = sorted(RUNS.glob(f"*_{project}_B4-random_seeds"))[-1]
    sources.append(f"- {project} B4-random: `{run.name}`")
    return json.loads((run / "metrics.json").read_text(encoding="utf-8"))["b4_random_summary"]


def ranking(project: str) -> list[dict]:
    run = sorted(RUNS.glob(f"*_{project}_B4-exhaustive_0"))[-1]
    sources.append(f"- {project} all 12 designs: `{run.name}`")
    return json.loads((run / "config.json").read_text(encoding="utf-8"))["selection"]["ranking"]


def a1_attempts(project: str) -> tuple[str, list[str]]:
    run = latest(project, "A1")
    config = json.loads((run / "config.json").read_text(encoding="utf-8"))
    return config["selected_config_id"], [a["config_id"] for a in config["design"]["attempts"]]


def save(fig, name: str, caption: str) -> None:
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=300, bbox_inches="tight")
    plt.close(fig)
    sources.append(f"\n**{name}**: {caption}\n")
    print(f"wrote reports/figures/{name}")


# -- figure 1: the main comparison -----------------------------------------------


def fig_main() -> None:
    systems = [("B0 word matching", "B0", OTHER), ("B1 generic prompt", "B1", OTHER),
               ("B3-k published, matched", "B3-k", OTHER), ("A1 our agent", "A1", AGENT)]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
    for ax, project in zip(axes, ("P1", "P2")):
        names, values, colours = [], [], []
        for label, system, colour in systems:
            p = primary(project, system)
            names.append(label)
            values.append(p["intent_macro_f1"])
            colours.append(colour)
        b4 = b4_random(project)
        names.append("B4 random search\n(mean, min to max)")
        values.append(b4["mean_intent_macro_f1"])
        colours.append(OTHER)
        ceiling = ranking(project)[0]["intent_macro_f1"]
        xs = range(len(names))
        bars = ax.bar(xs, values, color=colours, width=0.65)
        ax.errorbar(len(names) - 1, b4["mean_intent_macro_f1"],
                    yerr=[[b4["mean_intent_macro_f1"] - b4["min_intent_macro_f1"]],
                          [b4["max_intent_macro_f1"] - b4["mean_intent_macro_f1"]]],
                    fmt="none", ecolor=INK, capsize=4, lw=1)
        ax.axhline(ceiling, color=INK, ls="--", lw=1)
        ax.text(len(names) - 0.6, ceiling + 0.006, f"best of 12 designs {ceiling:.3f}",
                ha="right", fontsize=8.5)
        for bar, v in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, v - 0.035, f"{v:.3f}", ha="center",
                    color="white", fontsize=8.5, fontweight="bold")
        ax.set_xticks(list(xs), names, rotation=30, ha="right", fontsize=8.5)
        ax.set_ylim(0.6, 1.0)
        ax.set_title(f"{project}: {'Home assistant' if project == 'P1' else 'Productivity assistant'}")
    axes[0].set_ylabel("Intent macro-F1 (development)")
    fig.suptitle("The agent beats a generic prompt and the matched published baseline, "
                 "but not random search", fontsize=11, fontweight="bold")
    save(fig, "fig1_main_comparison.png",
         "Intent macro-F1 on 100 development cases per project. B4-random is 5 seeds "
         "(bar = mean, whisker = min to max). Dashed line = best of all 12 designs.")


# -- figure 2: intent vs entity -------------------------------------------------------


def fig_entity() -> None:
    systems = [("B1", OTHER), ("A1", AGENT), ("B3-k", "#475569"), ("B3-full", REF)]
    labels = {"B1": "B1 generic prompt", "A1": "A1 our agent", "B3-k": "B3-k published, matched",
              "B3-full": "B3-full, all data\n(reference only)"}
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    width = 0.2
    for ax, metric, title in zip(axes, ("intent_macro_f1", "entity_span_f1"),
                                 ("Intent macro-F1", "Entity span F1")):
        for i, (system, colour) in enumerate(systems):
            values = [primary(p, system)[metric] for p in ("P1", "P2")]
            xs = [x + (i - 1.5) * width for x in range(2)]
            ax.bar(xs, values, width, color=colour, label=labels[system],
                   hatch="//" if system == "B3-full" else None, edgecolor="white")
            for x, v in zip(xs, values):
                ax.text(x, v + 0.012, f"{v:.2f}", ha="center", fontsize=7.5)
        ax.set_xticks([0, 1], ["P1", "P2"])
        ax.set_ylim(0, 1.05)
        ax.set_title(title)
    axes[0].set_ylabel("Score (development)")
    handles, names = axes[0].get_legend_handles_labels()
    fig.legend(handles, names, loc="lower center", ncol=4, frameon=False, fontsize=8.5,
               bbox_to_anchor=(0.5, -0.08))
    fig.suptitle("The agent is strong on intent but weakest on entity extraction",
                 fontsize=11, fontweight="bold")
    save(fig, "fig2_intent_vs_entity.png",
         "B3-full trains on 10 to 30 times more data and is an upper reference, not a matched comparison.")


# -- figure 3: the 12-design landscape --------------------------------------------------


def fig_catalogue() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6), sharex=True)
    for ax, project in zip(axes, ("P1", "P2")):
        rows = sorted(ranking(project), key=lambda r: r["intent_macro_f1"])
        selected, tried = a1_attempts(project)
        colours = [AGENT if r["config_id"] == selected else ("#93c5fd" if r["config_id"] in tried else OTHER)
                   for r in rows]
        ax.barh([r["config_id"] for r in rows], [r["intent_macro_f1"] for r in rows], color=colours)
        for y, r in enumerate(rows):
            ax.text(r["intent_macro_f1"] + 0.004, y, f"{r['intent_macro_f1']:.3f}", va="center", fontsize=7.5)
        ax.set_xlim(0.6, 1.02)
        ax.set_title(project)
        ax.tick_params(axis="y", labelsize=8)
    axes[0].set_xlabel("Intent macro-F1 (development)")
    axes[1].set_xlabel("Intent macro-F1 (development)")
    from matplotlib.patches import Patch
    fig.legend(handles=[Patch(color=AGENT, label="A1 selected"), Patch(color="#93c5fd", label="A1 tried"),
                        Patch(color=OTHER, label="not tried")], loc="lower center", ncol=3,
               frameon=False, fontsize=8.5, bbox_to_anchor=(0.5, -0.04))
    fig.suptitle("The agent never tried the best design (schema-sim-llm) on either project",
                 fontsize=11, fontweight="bold")
    save(fig, "fig3_design_landscape.png",
         "All 12 catalogue designs scored on development data (B4-exhaustive). Colour shows A1's 4 choices.")


# -- figures 4 and 5: ablations and errors ----------------------------------------------


def fig_ablations() -> None:
    path = ROOT / "reports" / "dev_analysis.json"
    if not path.is_file():
        return
    data = json.loads(path.read_text(encoding="utf-8"))["projects"]
    variants = [("full", "A1 full system"), ("A1-noAnalyzer", "no Analyzer"),
                ("A1-noReasoning", "no Architect reasoning"), ("A1-noSelection", "no scored selection"),
                ("A1-noRepair", "no repair")]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    for ax, project in zip(axes, ("P1", "P2")):
        d = data[project]
        values = [d["a1"]["primary"]["intent_macro_f1"] if key == "full"
                  else d["ablations"][key]["primary"]["intent_macro_f1"] for key, _ in variants]
        colours = [AGENT] + [OTHER] * (len(variants) - 1)
        bars = ax.bar(range(len(variants)), values, color=colours, width=0.65)
        ax.axhline(values[0], color=AGENT, ls=":", lw=1)
        for bar, v in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, v + 0.005, f"{v:.3f}", ha="center", fontsize=8)
        ax.set_xticks(range(len(variants)), [label for _, label in variants], rotation=25,
                      ha="right", fontsize=8.5)
        ax.set_ylim(0.7, 1.0)
        ax.set_title(project)
        sources.extend(f"- {project} {k}: `{d['ablations'][k]['run_id']}`" for k, _ in variants[1:])
    axes[0].set_ylabel("Intent macro-F1 (development)")
    fig.suptitle("Scored selection helps; the Architect's reasoning does not (P2 is better without it)",
                 fontsize=11, fontweight="bold")
    save(fig, "fig4_ablations.png", "Each bar removes one component of A1. Source: reports/dev_analysis.json.")


def fig_errors() -> None:
    path = ROOT / "reports" / "dev_analysis.json"
    if not path.is_file():
        return
    data = json.loads(path.read_text(encoding="utf-8"))["projects"]
    cats = sorted({c for p in data.values() for c in p["errors"]["counts"]},
                  key=lambda c: sum(p["errors"]["counts"].get(c, 0) for p in data.values()))
    fig, ax = plt.subplots(figsize=(9, 4))
    height = 0.38
    for i, (project, colour) in enumerate((("P1", "#93c5fd"), ("P2", AGENT))):
        values = [data[project]["errors"]["counts"].get(c, 0) for c in cats]
        ys = [y + (i - 0.5) * height for y in range(len(cats))]
        ax.barh(ys, values, height, color=colour, label=project)
        for y, v in zip(ys, values):
            ax.text(v + 0.3, y, str(v), va="center", fontsize=7.5)
    ax.set_yticks(range(len(cats)), [c.split(" (")[0] for c in cats], fontsize=8.5)
    ax.set_xlabel("Errors in 100 development cases")
    ax.legend(frameon=False)
    fig.suptitle("Most of the agent's errors are entity errors, led by over-extraction",
                 fontsize=11, fontweight="bold")
    save(fig, "fig5_error_analysis.png", "A1's errors by the plan's categories. Source: reports/dev_analysis.json.")


# -- figure 6: robustness -------------------------------------------------------------


def fig_robustness() -> None:
    path = ROOT / "reports" / "robustness.json"
    if not path.is_file():
        return
    data = json.loads(path.read_text(encoding="utf-8"))["projects"]
    variants = ["clean", "typo", "caps", "filler"]
    systems = [("B0", OTHER, "B0 word matching"), ("B1", "#64748b", "B1 generic prompt"),
               ("A1", AGENT, "A1 our agent")]
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    width = 0.26
    for ax, project in zip(axes, ("P1", "P2")):
        for i, (system, colour, label) in enumerate(systems):
            values = [data[project]["systems"][system][v]["intent_macro_f1"] for v in variants]
            xs = [x + (i - 1) * width for x in range(len(variants))]
            ax.bar(xs, values, width, color=colour, label=label)
            for x, v in zip(xs, values):
                ax.text(x, v + 0.008, f"{v:.2f}", ha="center", fontsize=7)
        ax.set_xticks(range(len(variants)), ["clean", "typos", "CAPITALS", "filler words"])
        ax.set_ylim(0.3, 1.02)
        ax.set_title(project)
    axes[0].set_ylabel("Intent macro-F1 (development)")
    handles, names = axes[0].get_legend_handles_labels()
    fig.legend(handles, names, loc="lower center", ncol=3, frameon=False, fontsize=8.5,
               bbox_to_anchor=(0.5, -0.06))
    fig.suptitle("The AI-based systems cope with messy requests; word matching breaks down",
                 fontsize=11, fontweight="bold")
    save(fig, "fig6_robustness.png", "The same 100 development requests rewritten three ways. "
         "Source: reports/robustness.json and the *-robust-* run folders.")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for draw in (fig_main, fig_entity, fig_catalogue, fig_ablations, fig_errors, fig_robustness):
        draw()
    (OUT / "SOURCES.md").write_text(
        "# Figure sources\n\nGenerated by `python scripts/make_figures.py`. Every value is read "
        "from the run folders or reports below; none is typed in.\n\n" + "\n".join(dict.fromkeys(sources)) + "\n",
        encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
