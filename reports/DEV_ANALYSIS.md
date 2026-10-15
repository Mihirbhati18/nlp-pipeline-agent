# Development-stage analysis: ablations, timing, uncertainty and errors

Run 16 Oct 2026 by `python scripts/run_dev_analysis.py`; raw numbers in
`reports/dev_analysis.json`, full log in `logs/dev_analysis_20261016.log`.
Development data only (100 cases per project; the test split stays locked).
These numbers inform the G10 freeze. The reportable versions come from the
frozen test runs, where every analysis here is repeated.

## 1. Ablations: what each part of the agent contributes

Each row removes one component and keeps everything else. Intent macro-F1 /
entity span F1. Every row is its own run folder (`runs/20261016_*_A1-*`).

| Variant | What is removed | P1 intent | P1 entity | P2 intent | P2 entity |
|---|---|---|---|---|---|
| **A1 full system** | nothing | **0.958** | 0.597 | **0.841** | 0.365 |
| A1-noAnalyzer | Analyzer descriptions (bare spec) | 0.958 | 0.597 | 0.812 | 0.443 |
| A1-noReasoning | Architect reasoning (fixed fallback order) | 0.958 | 0.597 | **0.886** | **0.493** |
| A1-noSelection | scoring candidates (take the Architect's first choice) | 0.927 | 0.610 | 0.804 | 0.451 |
| A1-oneCandidate | candidate search (one predeclared design) | 0.927 | 0.610 | 0.804 | 0.451 |
| A1-noRepair | repair retry on a malformed reply | 0.958 | 0.592 | 0.841 | 0.362 |

What it shows:

- **Evaluation-driven selection is the component that earns its place:** +3.1
  (P1) and +3.7 (P2) intent points over taking a design without scoring it.
- **The Architect's reasoning does not help, and on P2 it hurts.** Its
  documented fallback order, with no planning calls at all, reaches the same
  design on P1 and a better one on P2 (+4.5 intent, +12.8 entity). This is the
  same bias as finding F1: the reasoning avoided similarity-selected examples.
- **The Analyzer helps intent on P2** (+2.9) and is neutral on P1, where the
  chosen two-stage design never reads the descriptions. On P2 the no-Analyzer
  search landed on a design with better entity F1, so its effect on entities is
  mixed, not positive.
- **Repair barely matters for this model:** raw replies were already valid
  99% (P1) and 98% (P2) of the time; repair lifts both to 100% and moves
  entity F1 by under 0.01.
- `A1-noSelection` and `A1-oneCandidate` coincide because the Architect's
  first choice on both projects was `joint-fixed-llm`, the same design as the
  predeclared one.

## 2. Uncertainty: paired bootstrap 95% intervals

A1 minus the other system, resampling the same 100 development cases for
both, 1,000 resamples, fixed seed.

| Comparison | P1 intent difference [95% CI] | P2 intent difference [95% CI] |
|---|---|---|
| A1 vs B1 generic prompt | +0.032 [-0.040, +0.121] | +0.038 [-0.019, +0.104] |
| A1 vs B3-k published baseline | +0.049 [-0.018, +0.137] | +0.008 [-0.104, +0.123] |
| A1 vs development ceiling (`schema-sim-llm`) | -0.016 [-0.065, +0.014] | -0.056 [-0.138, +0.006] |

**Every interval includes zero.** With 100 development cases per project, none
of these differences is statistically reliable yet; the positive point
estimates are suggestive, not established. The larger test sets (300 cases per
project) will narrow the intervals. Until then the paper must not call A1
"significantly better" than anything.

## 3. Real speed (uncached timing)

5 warm-up requests, then 50 development requests with the prediction cache
disabled. Out-of-scope rejections that cost no model call are excluded.

| Project | System | Design | Median | p95 |
|---|---|---|---|---|
| P1 | A1 | twostage-sim-llm (2 calls) | 0.77 s | 0.95 s |
| P1 | B1 | joint-fixed-llm (1 call) | 0.44 s | 0.59 s |
| P2 | A1 | schema-fixed-llm (1 call) | 0.43 s | 0.77 s |
| P2 | B1 | joint-fixed-llm (1 call) | 0.41 s | 0.79 s |

Every pipeline answers in under 1 second at p95. On P1 the agent's two-stage
design costs about 0.3 s more per request than B1 for its +3.1 intent points:
a trade-off, not a free improvement.

## 4. Error analysis of A1

Counted over the 100 development cases per project.

| Error category | P1 | P2 |
|---|---|---|
| Spurious entity (extracted something that is not a field) | 22 | 22 |
| Missed entity | 15 | 19 |
| Incorrect out-of-scope rejection (refused a valid request) | 4 | 11 |
| Wrong entity type (right words, wrong field) | 1 | 10 |
| Wrong entity boundary (too much or too little text) | 1 | 8 |
| Unsupported value (text not in the request) | 7 | 6 |
| Confused intent | 1 | 5 |
| Missed out-of-scope (answered an off-topic request) | 0 | 2 |
| Invalid output or runtime failure | 0 | 0 |

- **Entity over-extraction is the biggest single problem:** 22 spurious
  entities on each project. This explains why A1's entity F1 trails B1 and
  B3-k.
- **Intent errors are rare** (1 and 5), which matches the strong intent F1.
- **P2 is harder:** more wrongly refused requests, and more type and boundary
  errors across its 26 entity types, 5 of which never appear in the examples.
- **No invalid outputs and no failures** on either project.

## What changes for the freeze

1. Report the Architect's reasoning as **not contributing** on development
   data: the fallback order matched it on P1 and beat it on P2.
2. State that development differences are within noise; rely on the test-set
   intervals.
3. The error analysis points to the clearest improvement, which would be
   reducing entity over-extraction. Any such change must happen before the
   freeze and be logged, or be reported as future work.
