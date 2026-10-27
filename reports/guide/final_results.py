"""The "final results" section appended to every guide after the test runs.

The guides were written during development; their earlier sections are kept as they were, and this section,
added at the end, gives the locked-test results (reports/final_test.json, 25-26 Oct 2026) and the
reproduction checks (28 Oct 2026). One source, so every guide states the same numbers.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FINAL = json.loads((ROOT / "reports" / "final_test.json").read_text(encoding="utf-8"))
FIGS = ROOT / "reports" / "figures" / "final"


def _metric(project: str, system: str) -> str:
    m = FINAL["projects"][project]["systems"].get(system)
    if m is None:
        runs = sorted((ROOT / "runs").glob(f"*_{project}_{system}-final_0"))
        if not runs:
            return "not run"
        m = json.loads((runs[-1] / "metrics.json").read_text(encoding="utf-8"))["primary"]
    entity = "–" if system == "B0" else f"{m['entity_span_f1']:.3f}"
    return f"{m['intent_macro_f1']:.3f} / {entity} / {m['oos_f1']:.3f}"


def _ci(project: str, pair: str, key: str = "intent_macro_f1") -> str:
    c = FINAL["projects"][project]["bootstrap"][pair][key]
    return f"{100 * c['difference']:+.1f} [{100 * c['ci_low']:+.1f}, {100 * c['ci_high']:+.1f}]"


def add_final_results(b, heading: str = "Final results on the locked test data") -> None:
    """Append the final-results section to a guide built with docx_helpers.Builder."""
    b.page_break()
    b.h(heading)
    b.callout("**Read this section for the final numbers.** Everything above was written during development and "
              "uses development scores (100 practice requests). On 25 October 2026 the protocol, every system's choice "
              "and all code were frozen in one commit (`0ee6b22b`); only then were the test requests and the held-out "
              "project P3 unlocked. These are the results reported in the paper.")
    b.h("What was tested", 2)
    b.bullets([
        "P1 home assistant and P2 productivity: 300 test requests each (250 in scope + 50 off-topic).",
        "P3 ordering and travel, **held out**: never used during development; 200 test requests (167 + 33).",
        "Every system's design was chosen on development data before the freeze and replayed, not re-chosen, on test.",
    ])
    b.h("The results (intent F1 / entity F1 / off-topic F1)", 2)
    systems = [("B0 word matching", "B0"), ("B1 generic prompt", "B1"), ("B2 person", "B2"),
               ("B3-k XLM-R, same examples", "B3-k"), ("B3-full XLM-R, all training data", "B3-full"),
               ("A1 first agent", "A1"), ("A2 improved agent", "A2")]
    rows = [[label] + [_metric(p, s) for p in ("P1", "P2", "P3")] for label, s in systems]
    b4 = FINAL["projects"]
    rows.insert(5, ["B4 random search (mean intent, range)"] + [
        f"{b4[p]['b4_random']['mean_intent_macro_f1']:.3f} ({b4[p]['b4_random']['min']:.3f}–{b4[p]['b4_random']['max']:.3f})"
        for p in ("P1", "P2", "P3")])
    b.table(["System", "P1", "P2", "P3 (held out)"], rows, [5.0, 3.9, 3.9, 3.8], font=9, bold_first_col=True)
    if (FIGS / "final1_intent.png").is_file():
        b.image(FIGS / "final1_intent.png", "Intent F1 on the locked test data for every system and project.")
    b.h("What the results mean", 2)
    b.bullets([
        "**A2 found the best design every time.** On all three projects it picked the design that is best of all 12 on "
        "development data, while testing only 4.",
        f"**A2 beat the generic prompt (B1) on P1 and P2 and met the success rule.** Intent difference in points with "
        f"95% interval: P1 {_ci('P1', 'A2 vs B1')}, P2 {_ci('P2', 'A2 vs B1')}. Entity: P1 "
        f"{_ci('P1', 'A2 vs B1', 'entity_span_f1')}, P2 {_ci('P2', 'A2 vs B1', 'entity_span_f1')}. The P2 intent gain "
        "and both entity gains are significant (interval above zero).",
        f"**On the held-out P3 it did not beat B1 on intents:** {_ci('P3', 'A2 vs B1')} points, an interval that "
        f"includes zero, so it could be luck. On entities it was much better: {_ci('P3', 'A2 vs B1', 'entity_span_f1')}. "
        "P3's practice set had only about 13 requests per intent, and the designs were very close on test.",
        f"**Against the person (B2):** A2 was {_ci('P1', 'A2 vs B2')} points higher on P1 (significant) and "
        f"{_ci('P2', 'A2 vs B2')} on P2 (not significant). On P1 the person chose the similarity threshold for "
        "off-topic requests, and off-topic F1 fell to 0.471.",
        "**Against XLM-R with the same 10 examples per intent (B3-k):** A2 was 7 to 11 points higher on intents, higher "
        "on entities and far better at refusing off-topic requests on every project. With 10 to 32 times more labelled "
        "data (B3-full), XLM-R is better at entities but still refuses badly.",
        "**Against random search (B4):** A2 was above the random average on P1, at the top of the random range on P2, "
        "and at the bottom of the range on P3.",
        "**A1** passed the success rule on P1 and P2 too, but none of its differences from B1 is significant, and it "
        "failed on P3.",
    ])
    b.h("Speed and reliability", 2)
    b.bullets([
        "95th-percentile time per request (limit = 2 × B1 in the same session): P1 A2 0.89 s (limit 1.22 s), "
        "P2 A2 1.08 s (limit 1.67 s). Median about 0.65 s.",
        "Valid replies after repair: at least 0.997 for every agent run (needed 0.98).",
        "Designing one project costs A2 about 397 model calls, about 3 minutes, against 38 minutes for the person on P1.",
    ])
    b.h("Proof the numbers are real", 2)
    b.bullets([
        "`python scripts/reproduce_metrics.py`: 99 of 99 runs recomputed from their saved answers match exactly.",
        "`python scripts/verify_with_sklearn.py`: scikit-learn recomputes the same scores to 9 decimal places.",
        "`python scripts/reproduce_live.py --freeze-commit 0ee6b22b86894aebbe253fae3b00eb97c542c575`: B0 retrained "
        "from scratch is identical, and A2 asked live with the cache off gave 50 of 50 answers identical to the "
        "recorded test answers.",
        "`python scripts/show_evidence.py` runs every check and the live demo in one go (`reports/EVIDENCE_SUMMARY.md`).",
    ])
    b.p("Full details: the paper (`paper/main.tex` and its PDF), `paper/Research_Paper_Explained.pdf`, "
        "`docs/REPRODUCTION.md` and `reports/final_test.json`.")
