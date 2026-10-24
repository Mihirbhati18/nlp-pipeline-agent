# Interim findings (development data only)

**Nothing in this file is a reportable result.** Every number here comes from
development data, and in several cases the system being measured selected its
configuration *on that same data*, which makes the figure optimistic. The
reportable numbers come from the frozen test runs after the G10 freeze.

This file exists so findings are recorded when they are discovered, with their
caveats attached, rather than reconstructed later.

---

## F1. Plain random search matches or beats the agent at equal budget (13 Oct, P1 and P2)

**Superseded an earlier version of this finding.** The first run gave B4 the
*bare* specification while A1 used the Analyzer-enriched one, which was a bug:
plan section 3 requires B4 to get the "same catalogue, same Analyzer output,
same scorer". Fixed, and both projects re-run. The corrected numbers are below;
the earlier ones understated B4.

| System | P1 intent macro-F1 | P2 intent macro-F1 |
|---|---|---|
| B0 TF-IDF, no LLM | 0.780 | 0.730 |
| B1 generic prompt, no search | 0.927 | 0.804 |
| **A1 agent** | **0.958** | **0.841** |
| **B4-random, 5 seeds** | **0.959** mean, sd 0.009, range 0.951-0.974 | **0.878** mean, sd 0.017, range 0.861-0.898 |
| B4-exhaustive ceiling | 0.974 (`schema-sim-llm`) | 0.898 (`schema-sim-llm`) |

### What the research questions get

- **RQ1, agent vs fixed generic pipeline: positive.** A1 beats B1 by +3.1
  points on P1 and +3.7 on P2, both above the provisional `delta_I` of +2.0.
- **RQ5, agent vs plain search at equal budget: negative.** A1 ties B4-random
  on P1 (-0.1) and **loses by 3.7 points on P2**, where it was beaten by all
  five random seeds. The agent's candidate choice is not better than drawing
  four configurations at random, and on one project it is measurably worse.

Plan section 13 applies: *"If A1 does not beat B4 at equal budget, say the
agent's choice adds no measurable search benefit and report the contribution as
automation."* On this evidence the paper cannot claim search quality at all.

### The mechanism, which is the useful part

The best configuration on **both** projects is `schema-sim-llm`:
schema-guided extraction, similarity-selected examples, LLM out-of-scope label.
**A1 never tried it on either project.**

What A1 tried instead:

| Project | A1's four candidates | How many used similarity selection |
|---|---|---|
| P1 | twostage-sim-llm, joint-fixed-llm, schema-fixed-llm, joint-sim-tfidf | 2 of 4 |
| P2 | joint-fixed-llm, twostage-fixed-llm, schema-fixed-llm, joint-sim-tfidf | 1 of 4 |

On P2 the mean intent macro-F1 is **0.827 for similarity** selection against
**0.778 for fixed**, yet A1 chose fixed in three of its four candidates. Its
stated reasoning favoured schema-guided prompts and call efficiency, and it
systematically under-weighted example selection, which is the factor that
actually mattered. Random sampling has no such bias: it draws similarity
variants about half the time and so lands in the better region reliably.

So the failure is not randomness beating reasoning by luck. It is a
**systematic bias in the reasoning**, visible in the recorded rationales, which
costs A1 real points on P2.

### A positive finding in the same data: the Analyzer's enrichment helps

Fixing the bug above made the comparison fair, and it also produced a clean
before-and-after for enrichment, because without descriptions the
schema-guided configurations are identical to the joint ones:

| Project | Ceiling on the bare specification | Ceiling with Analyzer enrichment |
|---|---|---|
| P1 | 0.958 (`twostage-sim-llm`) | **0.974** (`schema-sim-llm`) |
| P2 | 0.886 (`joint-sim-llm`) | **0.898** (`schema-sim-llm`) |

Enrichment raised the attainable ceiling on both projects, by +1.6 and +1.2
points, and in both cases the new best configuration is a schema-guided one
that only becomes distinct once descriptions exist. That is direct evidence for
the Analyzer component, independent of the Architect's failure.

It also means that on the bare specification **four of the twelve
configurations are behavioural duplicates** of four others, so the catalogue
really offers eight distinct behaviours until enrichment separates them. This
partly explains the clustering noted below.

### Why the catalogue is a weak instrument for search quality

All 12 configurations, P1 then P2, on the enriched specification. The
out-of-scope policy dominates: every `llm_label` configuration beats every
`tfidf_threshold` one on both projects, a gap of roughly 9 points, far larger
than anything the search contributes. Six of twelve sit within a few points of
the best, so four random draws usually land near the top.

A search baseline can only discriminate when the space has spread. This one has
one dominant factor and a cluster of near-equivalent good options. If a future
version wanted to test search quality properly, the catalogue would need
configurations that genuinely fail.

### Caveats that must travel with these numbers

- Development scores. A1 and B4 both selected on this same split, so both are
  optimistically biased; the bias applies to both, so the comparison between
  them is sounder than either absolute figure.
- No confidence intervals yet. The P1 gap (-0.1) is noise. The P2 gap (-3.7,
  with A1 below all five seeds) is large enough to take seriously, but needs a
  paired bootstrap on test data before being stated as a result.
- Two projects. P3 stays untouched until after the freeze.
- The selection rule ranks on intent macro-F1 first and so trades entity
  quality away: on P1 it picked `twostage-sim-llm` (entity 0.597) over
  `joint-sim-llm` (entity 0.678). That is a property of the declared rule, and
  belongs in the paper rather than being quietly omitted.

### What this means for the claim

The honest framing left is: the framework **automates** pipeline design,
reaches a better configuration than a fixed generic pipeline (RQ1), and its
Analyzer enrichment raises the attainable ceiling. Its candidate *selection*
does not beat random search at the same budget, and on P2 it is worse. If B2
shows comparable quality to a human at much lower human effort, that becomes
the strongest supported claim.

---

## F1b. A fairness bug found and fixed (13 Oct)

For the first P1 and P2 runs, `scripts/run_design.py` passed the bare
specification to B4 while A1 used the enriched one. The same configuration
therefore scored differently for the two systems: `schema-fixed-llm` scored
0.841 for A1 and 0.804 for B4 on P2.

It was caught by noticing that discrepancy in the two run folders. Plan
section 3 requires B4 to receive the same Analyzer output, so B4 now runs the
Analyzer too. The faulty runs are superseded, not deleted, and the corrected
runs are the ones to cite.

Note the direction: the bug **flattered A1**, and A1 still lost on P2 once it
was fixed.

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

**Prediction outcome (13 Oct): partly supported.** The prediction was that
schema-guided configurations and enrichment should help P2's entity recall
more than P1's. Enrichment did raise the ceiling on both projects and made a
schema-guided configuration the best on both (F1), so the direction holds. But
the gain was larger on P1 (+1.6 points) than on P2 (+1.2), which is the
opposite of the ordering predicted. On the bare specification the
schema-guided and joint configurations scored identically on entity F1 on both
projects, confirming they are duplicates without descriptions. The prediction
should be retested on the frozen test split before any claim is made.

---

## F4. The runtime model is fully deterministic (12 Oct)

50 of 50 repeated requests produced identical output, so the determinism
limitation the plan anticipated does not need reporting. The expected
21,000-call budget measured at about 2.4 h against a feared 17-35 h.
Recorded in `protocol.md`.

---

## F4. The published baseline (B3, XLM-R) against the agent (15 Oct, P1 and P2)

B3 fine-tunes XLM-R base, the reference baseline of the MASSIVE paper, for
joint intent and slot tagging, trained locally on CPU. B3-k uses the same
k = 10 per intent pool every other system gets and is the matched comparison.
B3-full uses the full official train split and is an upper reference only.
Development data, same shared scorer and span rule as every other system.

| System | P1 intent | P1 entity | P1 OOS | P2 intent | P2 entity | P2 OOS |
|---|---|---|---|---|---|---|
| B1 generic prompt | 0.927 | 0.610 | 0.870 | 0.804 | 0.451 | 0.691 |
| **A1 agent** | **0.958** | 0.597 | **0.909** | **0.841** | 0.365 | **0.735** |
| **B3-k (matched, 10 per intent)** | 0.909 | **0.650** | 0.739 | 0.833 | **0.448** | 0.605 |
| B3-full (upper reference: 1,159 / 3,180 cases) | 0.936 | 0.768 | 0.579 | 0.923 | 0.797 | 0.432 |

- **At matched data, the agent beats the published baseline on intent** (+4.9
  on P1, +0.8 on P2) **and on out-of-scope detection** (+17.0, +13.0), and
  **loses on entity extraction** (-5.3, -8.3). Entity extraction is the
  agent's consistent weak point, as in F1.
- **B3-full wins on entities by a wide margin** (0.768 and 0.797) with 10-30x
  more training data, as the plan expected. It is reported as an upper
  reference, never a matched comparison.
- **B3-full's out-of-scope detection is the worst of any system** (0.579 and
  0.432): a classifier trained only on in-scope examples, with a confidence
  threshold, rejects poorly. More training data made it more confident on
  out-of-scope requests, not less.
- The P2 intent gap between A1 and B3-k (+0.8) is small enough to sit inside
  development-set noise; the frozen test run decides it.

Runs: `20261015_2240_P1_B3-k_0`, `20261015_2257_P1_B3-full_0`,
`20261015_2308_P2_B3-k_0`, `20261015_2354_P2_B3-full_0`.

---

## F5. Ablations, intervals, timing and errors (16 Oct, P1 and P2)

Full write-up: `reports/DEV_ANALYSIS.md`. Headlines:

- **The Architect's reasoning adds nothing on development data and hurts on
  P2.** With no planning calls, its fallback order reaches the same design on
  P1 and a better one on P2 (0.886 against 0.841 intent, 0.493 against 0.365
  entity). Evaluation-driven selection is the component that helps (+3.1, +3.7
  over the unscored first choice).
- **No development difference is statistically reliable.** Every paired
  bootstrap 95% interval (A1 against B1, B3-k and the ceiling) includes zero
  at 100 cases per project.
- **All pipelines answer within 1 s at p95**; A1's two-stage design on P1 costs
  about 0.3 s more than B1.
- **A1's main error is entity over-extraction** (22 spurious entities per
  project); intent errors are rare and there are no invalid outputs.

---

## F6. Robustness to typos, capitals and filler words (16 Oct, P1 and P2)

The LLM systems (A1, B1) lose at most 7.1 intent points when requests are
rewritten with typos, capitals or filler words; B0's word matching loses up to
26.9. A1 keeps its lead over B1 in every condition except P2 capitals (a tie),
but on P2 it degrades more than B1 under typos and capitals. Details:
`reports/DEV_ANALYSIS.md` section 5.

---

## F7. Manual configuration (B2) against the agent (24 Oct, P1)

One team member configured P1 by hand through `configs/b2/P1_worksheet.md`,
timed, with assistance declared. Run `20261024_1622_P1_B2_0`.

| System | Human configuration time | Design | Intent | Entity | OOS |
|---|---|---|---|---|---|
| **B2 manual** | **38 min** (1 development check) | twostage-sim-tfidf | 0.858 | 0.586 | 0.588 |
| B1 generic prompt | 0 (predeclared) | joint-fixed-llm | 0.927 | 0.610 | 0.870 |
| **A1 agent** | **0** (automatic) | twostage-sim-llm | **0.958** | 0.597 | **0.909** |

- **RQ2: the agent beats the manual configuration** by +10.0 intent points
  and +32.1 OOS points, with no human configuration time against 38 minutes.
  Entity F1 is close (+1.1 for A1).
- The gap comes mostly from the out-of-scope policy: B2 chose the TF-IDF
  threshold, which every development run has shown to be the weaker policy
  (F1). B2's written descriptions did not enter its prompts, because only
  schema-guided designs use them.
- **Caveats, recorded with the number:** a single, non-blind measurement by a
  self-described NLP beginner on the team that built A1; assistance declared
  (internet and Claude's explanation of the options); P1 only. The result
  shows the agent beats a quick novice configuration, not an expert one.
