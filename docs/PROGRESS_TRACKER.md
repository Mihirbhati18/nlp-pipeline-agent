# Progress tracker

Read this file before each work session. Gate and screenshot numbers follow
**PROJECT_PLAN.md v1.2**. This tracker was created new at v1.2 numbering, so no
renumbering from v1.0 was needed (recorded in `decisions.md`).

Last updated: 11 October 2026.

## Current position

**G1, G2 and G3 complete. G0 is complete except the throughput test (Ollama installed 11 Oct, models downloading) and the Overleaf skeleton. Day 1 of the 11–20 Oct schedule; G2 and G3 were the 12 Oct targets, so we are a day ahead.**

Next task: install Ollama, pull two candidate models, run
`python scripts/throughput_test.py --models qwen2.5:3b llama3.1:8b`, and record
the chosen runtime model in `protocol.md`. Then G3, the evaluator.

## Blocking inputs needed from the user

| # | Question | Why it blocks | Status |
|---|---|---|---|
| 1 | Were DA1 and DA2 submitted and accepted? | An owed DA2 would have reprioritised everything | **Answered 11 Oct: both submitted and accepted.** The plan's schedule stands |
| 2 | Confirmed DA3 cutoff date and time | Decides whether the 18 Oct buffer day exists | Open |
| 3 | Team size and member names | Needed for `contributions.md` and the contribution matrix | Open |
| 4 | Do the DA1 artifacts exist (15-paper table, 5 gaps, diagrams)? | Decides whether related work is written fresh or reused for the paper | Open |
| 5 | Install Ollama and pull two candidate models | Blocks the G0 throughput test, which chooses the runtime model, which every LLM system needs | Ollama 0.40.2 installed 11 Oct; `qwen2.5:3b` and `llama3.1:8b` downloading |

## Gate status

| Gate | Deliverable | Test condition | Status | Evidence |
|---|---|---|---|---|
| G0 | DA status check; Ollama installed; 50-request throughput + determinism test; runtime model chosen; Overleaf IEEE skeleton | Every unresolved decision listed; model chosen by the section 2A rule | **Partly done** — DA status answered; toolchain verified (Python 3.10.11, git 2.55, 16 GB RAM, RTX 3050 4 GB); harness written and its prompt builder checked; Ollama not installed; Overleaf not started | S00 pending |
| G1 | Repository structure, dependency lock, LLM client with cache and call counter, run-folder helper | Fresh environment runs a small test; cache hit/miss counted correctly; no secrets in logs | **Done** — 25 automated checks pass, committed | S01 pending |
| G2 | MASSIVE en-US; P1–P3 and OOS pool; k-shot pools and dev/test IDs; frozen project descriptions committed | Label/schema integrity, span conversion and leakage checks pass; descriptions committed before any LLM run | **Done** — 16,521/16,521 spans convert with 0 mismatches; 43 data checks pass; descriptions committed before any model call; see `DATA_REPORT.md` | S02 ready to capture |
| G3 | Scoring, span-location rule, latency and failure handling | Hand-computed fixtures and all span-rule cases match | **Done** - 46 checks pass; every expected metric value computed by hand | S03 ready to capture |
| G4 | 12-configuration catalogue; B0 TF-IDF; B1 fixed; start B3 Kaggle training | All 12 configurations run on 10 P1/P2 dev cases | **Next** - needs the chosen runtime model from G0 | S04 |
| G5 | B2 manual (timed); B3-k and B3-full; B4 search code | B3 reproduces a sensible official-split score; B4 deterministic per seed | Not started | S05 |
| G6 | Analyzer producing a validated ProjectSpec | Matches gold specification fixtures; conflicts flagged | Not started | S06 |
| G7 | Architect candidate choice within the 4-evaluation budget | Valid catalogue entries; budget cap respected; rationale logged | Not started | S07 |
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
