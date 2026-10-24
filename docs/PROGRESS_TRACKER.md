# Progress tracker

Read this file before each work session. Gate and screenshot numbers follow
**PROJECT_PLAN.md v1.2**. This tracker was created new at v1.2 numbering, so no
renumbering from v1.0 was needed (recorded in `decisions.md`).

Last updated: 11 October 2026.

## Current position

**G0-G4 and G6-G9 complete. G5: B4 and B3 done, B2 waiting on you. 14 October.**

### Start here next session

1. `cd D:/MyClaudeProject/nlp` then `python -m pytest tests -q` - expect 336 passed. For a full evidence check: `python scripts/show_evidence.py`.
2. B3 is done; nothing needs downloading.
3. B2 is done for P1 and P2 (finding F7).
4. Next: G10, the freeze.
4. Nothing is lost by stopping. All work is committed, and the prediction cache in `cache/` means model answers already computed are never recomputed.

State confirmed on 13 October: `qwen2.5:3b`, `torch` 2.14.1+cpu and
`transformers` 4.46.3 are all installed, so B3 and every LLM system can run
with no further download. `llama3.1:8b` is **not** installed and its partial
blobs did not survive the restart, so measuring it means a fresh 4.9 GB pull.

## Blocking inputs needed from the user

| # | Question | Why it blocks | Status |
|---|---|---|---|
| 1 | Were DA1 and DA2 submitted and accepted? | An owed DA2 would have reprioritised everything | **Answered 11 Oct: both submitted and accepted.** The plan's schedule stands |
| 2 | Confirmed DA3 cutoff date and time | Decides whether the 18 Oct buffer day exists | **Answered 15 Oct: 19 Oct 2026.** No buffer day; schedule compressed (decision 40). Exact time on the 19th still unconfirmed |
| 3 | Team size and member names | Needed for `contributions.md` and the contribution matrix | **Answered 15 Oct:** Mihir Bhati (24BCE5341), Ahana Sharan (24BCE5334). Equal contribution on all parts |
| 4 | Do the DA1 artifacts exist (15-paper table, 5 gaps, diagrams)? | Decides whether related work is written fresh or reused | **Answered 12 Oct: not reused.** Related work is written fresh against Prompt2Model, DSPy and MASSIVE |
| 5 | B2: configure a pipeline by hand, timed, 2 h per project | The RQ2 comparison, part of the minimum submittable result, and now the strongest remaining claim given finding F1. Only you can do it, because it measures human effort | **Ready for you**: `configs/b2/P1_worksheet.md` is created. Fill in sections 2-5, then `python scripts/run_b2.py check --project P1` and `finish` |

## Gate status

| Gate | Deliverable | Test condition | Status | Evidence |
|---|---|---|---|---|
| G0 | DA status check; Ollama installed; 50-request throughput + determinism test; runtime model chosen; Overleaf IEEE skeleton | Every unresolved decision listed; model chosen by the section 2A rule | **Done except Overleaf** - `qwen2.5:3b` confirmed 13 Oct: median 0.42 s, p95 0.59 s, JSON validity 1.00, determinism 1.00, budget about 2.4 h. The 8B candidate was abandoned on bandwidth grounds and the limitation is recorded in `protocol.md` | S00 ready |
| G1 | Repository structure, dependency lock, LLM client with cache and call counter, run-folder helper | Fresh environment runs a small test; cache hit/miss counted correctly; no secrets in logs | **Done** — 25 automated checks pass, committed | S01 pending |
| G2 | MASSIVE en-US; P1–P3 and OOS pool; k-shot pools and dev/test IDs; frozen project descriptions committed | Label/schema integrity, span conversion and leakage checks pass; descriptions committed before any LLM run | **Done** — 16,521/16,521 spans convert with 0 mismatches; 43 data checks pass; descriptions committed before any model call; see `DATA_REPORT.md` | S02 ready to capture |
| G3 | Scoring, span-location rule, latency and failure handling | Hand-computed fixtures and all span-rule cases match | **Done** - 46 checks pass; every expected metric value computed by hand | S03 ready to capture |
| G4 | 12-configuration catalogue; B0 TF-IDF; B1 fixed; start B3 Kaggle training | All 12 configurations run on 10 P1/P2 dev cases | **Done** - all 12 ran on P1 and P2; two real bugs found and fixed; B0 scored. Remaining: start B3 on Kaggle (your action) | S04 ready |
| G5 | B2 manual (timed); B3-k and B3-full; B4 search code | B3 reproduces a sensible official-split score; B4 deterministic per seed | **B4 done** on P1 and P2 (5 seeds plus exhaustive). **B2 workflow ready** for you: worksheet, timed effort recording, development checks, AI-assistance declaration. **B3 done** 15 Oct: B3-k and B3-full on P1 and P2 (see `FINDINGS.md` F4) | S05 |
| G6 | Analyzer producing a validated ProjectSpec | Matches gold specification fixtures; conflicts flagged | **Done** - validation blocks on real contradictions and reports gaps without blocking; enrichment described 12/12 P1 and 10/10 P2 intents and every entity type in 2 calls per project; test and held-out data withheld by a guard that raises | S06 ready |
| G7 | Architect candidate choice within the 4-evaluation budget | Valid catalogue entries; budget cap respected; rationale logged | **Done** - 3 initial + 1 revision enforced in code; only real catalogue entries run; rationale and reasoned-vs-fallback source recorded per attempt; revision reads the development error report | S07 ready |
| G8 | Candidate evaluation and selection; fill P1/P2 dev cache | Synthetic score tables select the correct candidate; no-eligible handled | **Done for P1** - A1, B1, B4-random (5 seeds) and B4-exhaustive all ran on P1 development data; 15 new checks; see `FINDINGS.md` F1 for the headline comparison. P2 running | S08 ready |
| G9 | Export/reload pipeline; request interface and demo | Fresh process loads artifact; normal/OOS/invalid requests work | **Done** - A1's selections exported as hash-verified packages (`artifacts/P1/twostage-sim-llm-ff3d548a0af2`, `artifacts/P2/schema-fixed-llm-d754b7d4ad80`), each tied to its A1 run folder and refused if the re-run selection differs; a modified file refuses to load; a different installed model refuses to serve; invalid requests rejected before any model call; demo on both projects; 27 new checks (325 total) | S09 ready: `python scripts/demo.py --project P1` |
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
| 12 Oct 2026 (G7) | NLP Architect: 3 initial candidates plus 1 revision that reads the development error report, hard budget enforcement, catalogue-only choices with hallucinated ids discarded, per-attempt rationale and reasoned-vs-fallback accounting, planning calls counted apart from runtime calls, explicit no-eligible outcome; B3 switched from Kaggle to local CPU training with its trainer and runner written; 37 new checks (282 total) | The CUDA PyTorch wheel (2.5 GB) failed on a DNS error at 255 KB/s and was abandoned for the CPU build (200 MB) | Confirm the runtime model against `llama3.1:8b`, run B3 locally, then wire G8 selection to the real catalogue |
| 13 Oct 2026 (G8) | Runtime model confirmed as `qwen2.5:3b` with the 8B limitation recorded; full design run wired end to end (Analyzer, Architect, catalogue, shared selection) and run on real P1 data for A1, B1, B4-random over 5 seeds and B4-exhaustive; `FINDINGS.md` created; B3 switched to a prefetch-then-train flow after repeated download breaks; 16 new checks (298 total) | **A1 beats B1 by +3.1 points but beats B4-random by only +0.4, far below the 2.0-point threshold.** Recorded as finding F1: on P1 the agent's candidate choice shows no measurable search benefit, and the catalogue is a weak instrument for detecting search quality because 6 of 12 configurations lie within 6 points of the best | Finish P2 and B3; then G9 export and demo |
| 14 Oct 2026 (G9) | Session moved from the terminal to the desktop app and resumed from the transcript. Runtime package format with SHA-256 integrity checks, model-digest check before the first call, explicit response statuses (ok, out_of_scope, invalid_output, error, invalid_request); `export_pipeline.py` exports A1's selections from a fully cached re-run (0 uncached calls) and ties each to its A1 run folder; `demo.py` shows normal, out-of-scope and invalid requests on both projects; 27 new checks (325 total) | XLM-R's chunked (xet) download stalled at 0 bytes on a ~140 KB/s connection; replaced with a curl byte-range download verified against the published SHA-256 | Finish B3; B2 by the user; G10 freeze |
| 15 Oct 2026 (B3) | XLM-R weights downloaded and SHA-256 verified on a stable connection; B3-k and B3-full trained on CPU and scored for P1 and P2 (finding F4); B2 example helper added; team and the 19 Oct deadline recorded | None | B2 by the user; G10 freeze |
| 16 Oct 2026 (dev analysis) | Development-stage ablations (no Analyzer, no reasoning, no selection, one candidate, no repair) as run folders; uncached timing for A1 and B1; paired bootstrap 95% intervals; A1 error analysis by the plan's categories; `reports/DEV_ANALYSIS.md`; 8 new checks (333 total) | **The Architect's fallback order beats its reasoning on P2**, and no development difference is statistically reliable at 100 cases (finding F5) | B2 by the user; G10 freeze |
| 16 Oct 2026 (evidence) | Reproduction check (all 38 checkable runs recompute exactly from saved predictions); robustness test with typos, capitals and filler words (18 run folders, finding F6); six figures drawn from run folders with a sources list; `show_evidence.py` runs every check in one command and saves `reports/EVIDENCE_SUMMARY.md`; prediction logs now tracked; 3 new checks (336 total) | The reproduction check found that B0 and B3 never logged raw schema validity; both runners fixed | B2 by the user; G10 freeze |
| 24 Oct 2026 (B2) | B2 manual configuration of P1 completed: 38 active minutes, 1 development check, assistance declared; intent 0.858 against A1's 0.958 (finding F7) | Ollama was not running after a restart and was started; the installed model digest is unchanged (357c53fb659c) | G10 freeze |
| 24 Oct 2026 (B2 P2) | B2 for P2 completed with ChatGPT assistance declared; intent 0.861 against A1's 0.841; measured elapsed time 5.7 min against a 15-minute self-estimate, recorded as the bound (finding F7) | None | G10 freeze |
