# Progress tracker

Read this file before each work session. Gate and screenshot numbers follow
**PROJECT_PLAN.md v1.2**. This tracker was created new at v1.2 numbering, so no
renumbering from v1.0 was needed (recorded in `decisions.md`).

Last updated: 11 October 2026.

## Current position

**Gate: G0 (requirements) and G1 (setup) — in progress, day 1 of the 11–20 Oct schedule.**

Next task: install Ollama, pull two candidate models, run
`python scripts/throughput_test.py --models <small> <larger>`, and record the
chosen runtime model in `protocol.md`.

## Blocking inputs needed from the user

| # | Question | Why it blocks | Status |
|---|---|---|---|
| 1 | Were DA1 and DA2 submitted and accepted? | If DA2 is still owed, the schedule in plan section 11 must be rewritten before coding continues | Open |
| 2 | Confirmed DA3 cutoff date and time | Decides whether the 18 Oct buffer day exists | Open |
| 3 | DA2 rubric — is there a handout beyond `AI DIGITAL ASSIGNMENT_1.docx`? | `D:/study/nlp/assignment 2.pdf` was checked on 11 Oct and is a CAT-2 skip-gram problem set, not the DA2 rubric | Open |
| 4 | Team size and member names | Needed for `contributions.md` and the contribution matrix | Open |
| 5 | Do the DA1 artifacts exist (15-paper table, 5 gaps, diagrams)? | Decides whether related work is written fresh or reused | Open |

## Gate status

| Gate | Deliverable | Test condition | Status | Evidence |
|---|---|---|---|---|
| G0 | DA status check; Ollama installed; 50-request throughput + determinism test; runtime model chosen; Overleaf IEEE skeleton | Every unresolved decision listed; model chosen by the section 2A rule | **Partly done** — toolchain verified (Python 3.10.11, git 2.55); harness written; Ollama not installed; DA questions open | S00 pending |
| G1 | Repository structure, dependency lock, LLM client with cache and call counter, run-folder helper | Fresh environment runs a small test; cache hit/miss counted correctly; no secrets in logs | **Done pending commit** — 25 automated checks pass | S01 pending |
| G2 | MASSIVE en-US; P1–P3 and OOS pool; k-shot pools and dev/test IDs; frozen project descriptions committed | Label/schema integrity, span conversion and leakage checks pass; descriptions committed before any LLM run | Not started | S02 |
| G3 | Scoring, span-location rule, latency and failure handling | Hand-computed fixtures and all span-rule cases match | Not started | S03 |
| G4 | 12-configuration catalogue; B0 TF-IDF; B1 fixed; start B3 Kaggle training | All 12 configurations run on 10 P1/P2 dev cases | Not started | S04 |
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
| 11 Oct 2026 | Repository created at `D:/MyClaudeProject/nlp`; plan moved to `docs/PROJECT_PLAN.md`; LLM client with prediction cache, logical/physical call counters and prompt cap; `new_run()` run-folder helper; 25 automated checks passing; G0 throughput harness written; `assignment 2.pdf` checked and ruled out as the DA2 rubric | None | Install Ollama, pull two models, run the throughput test; answer the five blocking questions above |
