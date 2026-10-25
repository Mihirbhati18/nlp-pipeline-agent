"""Draw the diagrams and terminal images used in the verification guide.

Terminal images are rendered from the real command outputs saved in
``captures/`` (each produced by running the command shown in its title bar),
so they show exactly what the commands print.

Usage (from the project root):
    python reports/guide/make_guide_images.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "images"
INK, QUIET, EDGE = "#1e293b", "#475569", "#64748b"
AI_FILL, AI_EDGE = "#dbeafe", "#2563eb"
PLAIN_FILL = "#f8fafc"
GOOD = "#16a34a"


def box(ax, x, y, w, h, title, lines=(), ai=False, fill=None):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=fill or (AI_FILL if ai else PLAIN_FILL),
                                ec=AI_EDGE if ai else EDGE, lw=2 if ai else 1.2))
    ax.text(x + w / 2, y + h - 0.28, title, ha="center", va="center", fontsize=10.5,
            fontweight="bold", color=INK)
    for i, line in enumerate(lines):
        ax.text(x + w / 2, y + h - 0.62 - i * 0.27, line, ha="center", va="center", fontsize=8.6, color=QUIET)


def arrow(ax, x1, y1, x2, y2, label=None, curve=0.0, dx=0.0, dy=0.12):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=14,
                                 color=EDGE, lw=1.3, connectionstyle=f"arc3,rad={curve}"))
    if label:
        ax.text((x1 + x2) / 2 + dx, (y1 + y2) / 2 + dy, label, ha="center", fontsize=8.3, color=QUIET)


def canvas(w, h, title):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    ax.text(0.2, h - 0.35, title, fontsize=12.5, fontweight="bold", color=INK)
    return fig, ax


def save(fig, name):
    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / name, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"wrote {name}")


def how_it_works():
    fig, ax = canvas(11, 5.2, "How the framework designs a pipeline (blue = steps where the AI decides)")
    y = 2.7
    box(ax, 0.2, y, 1.9, 1.4, "1. Input", ["project description", "request types", "fields + examples"])
    box(ax, 2.4, y, 1.9, 1.4, "2. Analyzer", ["AI writes a short", "description of every", "request type and field"], ai=True)
    box(ax, 4.6, y, 1.9, 1.4, "3. Architect", ["AI picks which of the", "12 pipeline designs", "to test (3, then 1)"], ai=True)
    box(ax, 6.8, y, 1.9, 1.4, "4. Test + select", ["each design scored on", "100 development cases;", "best score is kept"])
    box(ax, 9.0, y, 1.8, 1.4, "5. Export", ["saved package that", "any program can", "load and use"])
    for x in (2.1, 4.3, 6.5, 8.7):
        arrow(ax, x, y + 0.7, x + 0.3, y + 0.7)
    arrow(ax, 7.75, y, 5.55, y, curve=-0.45, label="scores go back: Architect picks a 4th design", dy=-0.72)
    box(ax, 9.0, 0.35, 1.8, 1.25, "6. Live use", ["\"turn the lights off\"", "-> iot_hue_lightoff,", "house_place=..."])
    arrow(ax, 9.9, y, 9.9, 1.6)
    ax.text(0.2, 0.9, "The 12 designs = 3 ways to extract x 2 ways to pick examples x 2 ways to reject off-topic requests.",
            fontsize=9, color=INK)
    ax.text(0.2, 0.55, "No human configures anything: the same steps run for any new project description.",
            fontsize=9, color=INK)
    save(fig, "how_it_works.png")


def fair_comparison():
    fig, ax = canvas(11, 4.6, "Why the comparison is fair: everything except the design method is shared")
    systems = [("B0", "word matching"), ("B1", "generic prompt"), ("B2", "human, by hand"),
               ("B3", "published XLM-R"), ("B4", "random search"), ("A1 / A2", "our agent")]
    for i, (name, what) in enumerate(systems):
        box(ax, 0.2 + i * 1.8, 2.6, 1.6, 1.0, name, [what], ai=name.startswith("A"))
        arrow(ax, 1.0 + i * 1.8, 2.6, 5.5, 1.75)
    box(ax, 2.3, 0.35, 6.4, 1.4, "Shared by every system", [
        "same MASSIVE data and the same fixed splits (seeded)",
        "same AI model (qwen2.5:3b) for every AI-based system",
        "same scorer, same rules: failures stay in every score"], fill="#f0fdf4")
    save(fig, "fair_comparison.png")


def verification():
    fig, ax = canvas(11, 5.0, "How each result is verified")
    box(ax, 0.1, 2.2, 2.4, 1.5, "Saved predictions", ["every answer, request", "by request, in", "runs/<run>/predictions.jsonl"])
    box(ax, 3.2, 3.3, 3.0, 1.15, "Our scorer", ["recorded the score in", "runs/<run>/metrics.json"])
    box(ax, 3.2, 1.85, 3.0, 1.15, "Re-scored from scratch", ["scripts/reproduce_metrics.py"])
    box(ax, 3.2, 0.4, 3.0, 1.15, "scikit-learn (independent)", ["scripts/verify_with_sklearn.py"])
    for y in (3.85, 2.4, 0.95):
        arrow(ax, 2.5, 2.95, 3.2, y)
    box(ax, 7.0, 1.85, 1.9, 1.15, "Compare", ["to 9 decimal places"])
    for y in (3.85, 2.4, 0.95):
        arrow(ax, 6.2, y, 7.0, 2.4)
    box(ax, 9.3, 1.85, 1.6, 1.15, "44 / 44 agree", ["no number was", "edited by hand"], fill="#dcfce7")
    arrow(ax, 8.9, 2.4, 9.3, 2.4)
    ax.text(7.0, 4.2, "Also: 371 automated tests, a dated git history of 40+ commits,", fontsize=8.8, color=INK)
    ax.text(7.0, 3.92, "and every run folder records its code version and data hashes.", fontsize=8.8, color=INK)
    save(fig, "verification.png")


def terminal(capture: str, command: str, name: str, highlight: tuple[str, ...] = ()):
    lines = (HERE / "captures" / capture).read_text(encoding="utf-8").rstrip("\n").splitlines()
    lines = [l if len(l) <= 132 else l[:129] + "..." for l in lines]
    height = 0.75 + 0.2 * len(lines)
    fig, ax = plt.subplots(figsize=(11, height))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, height)
    ax.axis("off")
    ax.add_patch(FancyBboxPatch((0, 0), 1, height, boxstyle="round,pad=0,rounding_size=0.02",
                                fc="#0f172a", ec="#0f172a", transform=ax.transData))
    ax.add_patch(FancyBboxPatch((0, height - 0.38), 1, 0.38, boxstyle="square,pad=0",
                                fc="#1e293b", ec="#1e293b"))
    ax.text(0.015, height - 0.19, f"> {command}", va="center", fontsize=9.2, color="#e2e8f0",
            family="monospace", fontweight="bold")
    for i, line in enumerate(lines):
        colour = "#86efac" if any(h in line for h in highlight) else "#cbd5e1"
        ax.text(0.015, height - 0.6 - i * 0.2, line, va="center", fontsize=7.0, color=colour, family="monospace")
    save(fig, name)


def main():
    how_it_works()
    fair_comparison()
    verification()
    terminal("01_pytest.txt", "python -m pytest tests", "screen_tests.png", ("passed",))
    terminal("02_reproduce.txt", "python scripts/reproduce_metrics.py", "screen_reproduce.png", ("{",))
    terminal("03_sklearn.txt", "python scripts/verify_with_sklearn.py", "screen_sklearn.png", ("{",))
    terminal("04_demo.txt", "python scripts/demo.py --project P1", "screen_demo.png", ("-> ok", "-> out_of_scope", "invalid_request"))
    terminal("05_gitlog.txt", "git log --reverse (dates and messages)", "screen_gitlog.png")
    terminal("06_summary.txt", "python scripts/show_evidence.py   (summary lines)", "screen_summary.png", ("Overall",))
    # for the "how we did every test" guide
    evaluation_flow()
    terminal("07a_walk_request.txt", "python scripts/walkthrough.py   (request 2 of 3 shown)", "screen_walk_request.png",
             ("intent RIGHT", "intent =", "Model's raw reply"))
    terminal("07b_walk_scores.txt", "python scripts/walkthrough.py   (end of the output)", "screen_walk_scores.png", ("our scorer", "scikit-learn"))
    terminal("08_my_first_test.txt", "python -m pytest tests/test_my_first.py -vv", "screen_my_first_test.png", ("passed", "PASSED"))
    terminal("09_run_a2.txt", "python scripts/run_a2.py", "screen_run_a2.png", ("selected", "GOES"))
    terminal("11_data_check.txt", "python scripts/prepare_data.py --check", "screen_data_check.png", ("pass",))
    terminal("12a_explain_table.txt", "python scripts/explain_f1.py   (steps 1 to 3)", "screen_explain_table.png", ("NO", "Saved"))
    terminal("12b_explain_counts.txt", "python scripts/explain_f1.py   (steps 4 to 6)", "screen_explain_counts.png", ("= 0.9744", "same", "F1 ="))
    terminal("13_bootstrap.txt", "python scripts/explain_stats.py bootstrap", "screen_bootstrap.png", ("interval =", "-> same", "STEP 1."))
    terminal("14_timing.txt", "python scripts/explain_stats.py timing", "screen_timing.png", ("Median =", "p95 =", "-> same"))
    terminal("15a_errors.txt", "python scripts/explain_stats.py errors   (first part)", "screen_errors.png", (": 22", ": 15", ": 7", ": 4"))
    terminal("10_scorer_tests.txt", "python -m pytest tests/test_scorer.py -vv   (first 8 of 14)", "screen_scorer_tests.png", ("PASSED",))


def evaluation_flow():
    fig, ax = canvas(11, 4.4, "What one evaluation run does, for every one of the 100 development requests")
    steps = [("Request", ["from the locked-split", "development file"]),
             ("Prompt", ["labels + examples", "+ the request"]),
             ("AI model", ["qwen2.5:3b replies", "in JSON"]),
             ("Read reply", ["check format, locate", "entities in the text"]),
             ("Compare", ["with the correct", "answer from data"]),
             ("Save", ["prediction written to", "predictions.jsonl"])]
    for i, (title, lines) in enumerate(steps):
        box(ax, 0.15 + i * 1.82, 2.2, 1.62, 1.2, title, lines, ai=(title == "AI model"))
        if i:
            arrow(ax, 0.15 + i * 1.82 - 0.2, 2.8, 0.15 + i * 1.82, 2.8)
    box(ax, 3.3, 0.3, 4.4, 1.15, "After all 100 requests", ["scorer computes F1, accuracy, ...", "-> metrics.json in a dated run folder"],
        fill="#f0fdf4")
    arrow(ax, 10.1, 2.2, 7.7, 0.9, curve=-0.2)
    save(fig, "evaluation_flow.png")


if __name__ == "__main__":
    main()
