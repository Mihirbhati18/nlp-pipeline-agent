# Interim findings (development data only)

**Nothing in this file is a reportable result.** Every number here comes from
development data, and in several cases the system being measured selected its
configuration *on that same data*, which makes the figure optimistic. The
reportable numbers come from the frozen test runs after the G10 freeze.

This file exists so findings are recorded when they are discovered, with their
caveats attached, rather than reconstructed later.

---

## F1. The agent reaches the catalogue optimum, but plain search nearly matches it (13 Oct, P1)

Run IDs: `20261013_0049_P1_A1_0`, `20261013_0056_P1_B4-random_seeds`,
`20261013_0056_P1_B4-exhaustive_0`, `20261013_0043_P1_B1_0`.

| System | P1 intent macro-F1 | Notes |
|---|---|---|
| B0 TF-IDF | 0.780 | no LLM, no entity extraction |
| B1 generic prompt | 0.927 | one predeclared configuration, no search |
| **A1 agent** | **0.958** | selected `twostage-sim-llm`, 4/4 choices reasoned |
| **B4-random, 5 seeds** | **0.954 mean**, sd 0.004, range 0.951-0.958 | same 4-candidate budget |
| B4-exhaustive | 0.958 | all 12; the development ceiling |

**What this says about the research questions.**

- **RQ1 (agent vs fixed generic pipeline):** A1 beats B1 by **+3.1 points**,
  above the provisional `delta_I` of +2.0. Promising, pending the test run.
- **RQ5 (agent vs plain search at equal budget):** A1 beats B4-random by
  **+0.4 points**, far below `delta_I`, and B4-random reached the same ceiling
  in 2 of its 5 seeds. On this project and this data, **the agent's choice of
  candidates shows no measurable search benefit over random selection.**

Plan section 13 prescribes the response: *"If A1 does not beat B4 at equal
budget, say the agent's choice adds no measurable search benefit and report the
contribution as automation."* The honest framing is therefore automation,
reliability of reaching the optimum, and setup effort, not search quality.

**Why, and this is the more interesting part.** All 12 configurations on P1:

| Configuration | Intent F1 | Entity F1 |
|---|---|---|
| twostage-sim-llm | 0.958 | 0.597 |
| joint-sim-llm | 0.951 | 0.678 |
| schema-sim-llm | 0.951 | 0.678 |
| joint-fixed-llm | 0.927 | 0.610 |
| schema-fixed-llm | 0.927 | 0.610 |
| twostage-fixed-llm | 0.901 | 0.587 |
| joint-sim-tfidf | 0.862 | 0.620 |
| schema-sim-tfidf | 0.862 | 0.620 |
| twostage-sim-tfidf | 0.858 | 0.586 |
| joint-fixed-tfidf | 0.849 | 0.520 |
| schema-fixed-tfidf | 0.849 | 0.520 |
| twostage-fixed-tfidf | 0.839 | 0.544 |

Two structural facts follow:

1. **One factor dominates.** Every `llm_label` configuration scores 0.901 or
   above; every `tfidf_threshold` configuration scores 0.862 or below. That is
   a gap of roughly 9 points, far larger than anything the search contributes.
   The out-of-scope policy, not the extraction strategy or the example
   selection, is the decision that matters on P1.
2. **The good options are clustered.** Six of twelve configurations lie within
   6 points of the best. Drawing 4 of 12 at random therefore lands near the top
   most of the time. The catalogue is a **weak instrument for detecting search
   quality**: it cannot separate a good chooser from a lucky one, because
   almost any choice is nearly as good.

Point 2 is itself a finding worth reporting. A search baseline only
discriminates when the search space has meaningful spread, and this one does
not. It also suggests that if a future version wanted to test search quality
properly, the catalogue would need configurations that genuinely fail.

**Caveats attached to the numbers above.**

- Development scores, and A1 and B4 both selected on this same split, so both
  are optimistically biased. The bias applies equally, so the *comparison*
  between them is fairer than either absolute number.
- One project only. P2 is not yet run, and P3 is held out until after the
  freeze.
- No confidence intervals yet. The +0.4-point gap is well inside the kind of
  variation a paired bootstrap would show on 100 cases, so it should not be
  described as a difference at all until tested.
- Entity F1 does **not** follow intent F1: the best intent configuration
  (`twostage-sim-llm`, 0.597) is *worse* at entities than `joint-sim-llm`
  (0.678). The selection rule ranks on intent macro-F1 first, so it knowingly
  trades entity quality away here. That trade-off is in the ranking rule and
  must be stated, not hidden.

---

## F2. B0's out-of-scope detection is weak (11 Oct, P1 and P2)

A TF-IDF confidence threshold at k = 10 gives out-of-scope recall 0.65 and
precision 0.42 on both development projects. It sets a low bar, and any LLM
system should clear it. Recorded in the B0 run summaries.

---

## F3. P2 has entity types with no example anywhere in its prompt pool (12 Oct)

5 of P2's 26 declared entity types never appear in its k-shot pool, covering
10.7% of its development gold entities. P1 and P3 are unaffected. Details and
the falsifiable prediction this generates are in `DATA_REPORT.md`.

---

## F4. The runtime model is fully deterministic (12 Oct)

50 of 50 repeated requests produced identical output, so the determinism
limitation the plan anticipated does not need reporting. The expected
21,000-call budget measured at about 2.4 h against a feared 17-35 h.
Recorded in `protocol.md`.
