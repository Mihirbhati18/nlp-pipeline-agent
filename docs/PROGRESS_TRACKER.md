# Progress tracker

Read this file before each work session. Gate and screenshot numbers follow
**PROJECT_PLAN.md v1.2**. This tracker was created new at v1.2 numbering, so no
renumbering from v1.0 was needed (recorded in `decisions.md`).

Last updated: 11 October 2026.

## Current position

**G0-G4 and G6 complete. G5 has B3 and B4 built; only B2 remains. `qwen2.5:3b` installed and measured. 12 October, with the 13 and 14 Oct targets done and part of 15 Oct.**

Next task: install Ollama, pull two candidate models, run
`python scripts/throughput_test.py --models qwen2.5:3b llama3.1:8b`, and record
the chosen runtime model in `protocol.md`. Then G3, the evaluator.

## Blocking inputs needed from the user

| # | Question | Why it blocks | Status |
|---|---|---|---|
| 1 | Were DA1 and DA2 submitted and accepted? | An owed DA2 would have reprioritised everything | **Answered 11 Oct: both submitted and accepted.** The plan's schedule stands |
| 2 | Confirmed DA3 cutoff date and time | Decides whether the 18 Oct buffer day exists | Open |
| 3 | Team size and member names | Needed for `contributions.md` and the contribution matrix | Open |
| 4 | Do the DA1 artifacts exist (15-paper table, 5 gaps, diagrams)? | Decides whether related work is written fresh or reused | **Answered 12 Oct: not reused.** Related work is written fresh against Prompt2Model, DSPy and MASSIVE |
| 5 | Launch B3 on Kaggle | B3 is the published-baseline comparison and part of the minimum submittable result | Open - your action. Notebook and split export are ready |

## Gate status

| Gate | Deliverable | Test condition | Status | Evidence |
|---|---|---|---|---|
| G0 | DA status check; Ollama installed; 50-request throughput + determinism test; runtime model chosen; Overleaf IEEE skeleton | Every unresolved decision listed; model chosen by the section 2A rule | **Done except the model-size comparison and Overleaf** — `qwen2.5:3b` measured: median 0.42 s, p95 0.59 s, JSON validity 1.00, determinism 1.00, budget about 2.4 h. `llama3.1:8b` downloading so the "largest eligible" rule can be applied honestly | S00 ready |
| G1 | Repository structure, dependency lock, LLM client with cache and call counter, run-folder helper | Fresh environment runs a small test; cache hit/miss counted correctly; no secrets in logs | **Done** — 25 automated checks pass, committed | S01 pending |
| G2 | MASSIVE en-US; P1–P3 and OOS pool; k-shot pools and dev/test IDs; frozen project descriptions committed | Label/schema integrity, span conversion and leakage checks pass; descriptions committed before any LLM run | **Done** — 16,521/16,521 spans convert with 0 mismatches; 43 data checks pass; descriptions committed before any model call; see `DATA_REPORT.md` | S02 ready to capture |
| G3 | Scoring, span-location rule, latency and failure handling | Hand-computed fixtures and all span-rule cases match | **Done** - 46 checks pass; every expected metric value computed by hand | S03 ready to capture |
| G4 | 12-configuration catalogue; B0 TF-IDF; B1 fixed; start B3 Kaggle training | All 12 configurations run on 10 P1/P2 dev cases | **Done** - all 12 ran on P1 and P2; two real bugs found and fixed; B0 scored. Remaining: start B3 on Kaggle (your action) | S04 ready |
| G5 | B2 manual (timed); B3-k and B3-full; B4 search code | B3 reproduces a sensible official-split score; B4 deterministic per seed | **Mostly done** - B3 notebook and local scorer written and validated end to end (synthetic runs deleted), awaiting a real Kaggle run; B4-random and B4-exhaustive built and tested with the shared selection rule. Remaining: B2 manual configuration (timed, needs a model) | S05 |
| G6 | Analyzer producing a validated ProjectSpec | Matches gold specification fixtures; conflicts flagged | **Done** - validation blocks on real contradictions and reports gaps without blocking; enrichment described 12/12 P1 and 10/10 P2 intents and every entity type in 2 calls per project; test and held-out data withheld by a guard that raises | S06 ready |
| G7 | Architect candidate choice within the 4-evaluation budget | Valid catalogue entries; budget cap respected; rationale logged | **Next** | S07 |
| G8 | Candidate evaluation and selection; fill P1/P2 dev cache | Synthetic score tables select the correct candidate; no-eligible handled | Not started | S08 |
| G9 | Export/reload pipeline; request interface and demo | Fresh process loads artifact; normal/OOS/invalid requests work | Not started | S09 |
| G10 | Freeze: thresholds, budgets, exact test call count, minimum-result check | Test answers unopened; P3 untouched; one freeze commit | Not started | S10 |
| G11 | Final evaluation on P1/P2, then P3; uncached timing runs | Matching manifests, complete predictions, scored failures | Not started | S11 |
| G12 | Reproduction, paper, figures, submission | Metrics recompute from saved predictions; every claim traces to a run | Not started | S12 |

Gates G4–G10 use **only P1 and P2**. P3 is touched before the freeze solely to
write and commit its description in G2.

## Session log

| Date | Work done | Failures | Next action |
|---|---|---|---|
| 11 Oct 2026 (G1) | Repository created at `D:/MyClaudeProject/nlp`; plan moved to `docs/PROJECT_PLAN.md`; LLM client with prediction cache, logical/physical call counters and prompt cap; `new_run()` run-folder helper; 25 checks passing; G0 throughput harness written; `assignment 2.pdf` checked and ruled out as the DA2 rubric | None | — |
| 11 Oct 2026 (G2) | MASSIVE 1.1 en-US downloaded (CC BY 4.0, archive hashed); span conversion verified on all 16,521 records with 0 mismatches; P1/P2/P3 and the OOS pool defined and confirmed against split counts; k-shot pools, dev and test IDs sampled with a per-project seed and verified reproducible; train-derived entity schemas; leakage and cross-project independence checks; three frozen project descriptions committed; `DATA_REPORT.md` written; 68 checks passing | P3's official test split cannot supply 250 in-scope cases (181 available), so the plan's 200-case fallback was applied and logged | Install Ollama and run the throughput test; then build the G3 evaluator |
| 11 Oct 2026 (G3) | Span-location rule implemented once in `src/evaluation/span_rule.py` and used by every system; common scorer with all primary and secondary metrics; shared output contract with explicit statuses and a repair instruction; 46 new checks, all expected values hand-computed | None | Finish the G0 throughput test once the models finish downloading, then G4 |
| 11 Oct 2026 (G4) | 12-configuration catalogue with prompt rendering inside the cap, two-stage extraction, TF-IDF out-of-scope policy that rejects before spending a call, and one counted repair retry; example selection (fixed and similarity); shared threshold tuner; B0 baseline scored on P1 and P2 development data into immutable run folders; experiment runner separating scoring from latency measurement; 40 new checks (154 total) | `qwen2.5:3b` pull failed once with `max retries exceeded: unexpected EOF` and is being retried | Finish the model download, run the G0 throughput test and `scripts/run_catalogue_check.py`, start B3 on Kaggle |
| 11 Oct 2026 (G5 part) | B3 Kaggle notebook (XLM-R joint intent + slot BIO, B3-k and B3-full), the frozen-split export it consumes, and `scripts/score_b3.py` which tunes the threshold and scores with the shared scorer; whole path validated on synthetic predictions, and the split-mismatch guard verified to refuse writing a run folder; 11 new checks (165 total) | None. Synthetic validation runs were deleted so they cannot be mistaken for evidence | Upload the notebook to Kaggle and start B3 training; finish the model download for G0 |
| 11 Oct 2026 (G5 part 2) | Shared candidate selection rule used by both B4 and the agent, with hard-constraint filtering, explicit no-eligible-candidate outcome and recorded unchecked constraints; B4-random (seeded, 5 seeds, reported as a distribution) and B4-exhaustive as the development ceiling; 30 new checks (195 total) | None | Register the model when the download finishes, run the G0 throughput test and the G4 catalogue check |
| 12 Oct 2026 (G0, G4 gate) | `qwen2.5:3b` installed after a corrupt GGUF attempt was discarded; client fixed to read the model digest from `/api/tags` and record quantization; G0 throughput test run (median 0.42 s, p95 0.59 s, JSON validity 1.00, determinism 1.00, budget about 2.4 h); G4 gate met with all 12 configurations running on P1 and P2 | Two real bugs found by the gate on live data: two-stage configurations got no repair retry where single-call ones did, and `schema_valid_raw` ignored the stage-one repair. Both fixed and covered by 10 new checks. A corrupt 3.72 GB GGUF download was detected by size and deleted | Measure `llama3.1:8b` when it finishes, then confirm the runtime model; build G6 Analyzer; start the Overleaf skeleton |
| 12 Oct 2026 (G6) | Data access guard that refuses test and held-out data rather than relying on discipline; Project Analyzer split into model-free validation and two-call enrichment, with authoritative names protected from the model; verified live on P1 and P2 (all intents and entity types described, no blocking findings); 40 new checks (245 total) | None | Build G7 Architect, then G8 selection |
