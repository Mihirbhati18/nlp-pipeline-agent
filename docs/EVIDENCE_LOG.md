# Evidence log

Index of tests, screenshots, runs and decisions. Screenshots are supplementary;
the saved inputs, outputs, metrics and code version are the reproducible
evidence. Screenshot IDs follow PROJECT_PLAN.md v1.2.

Filename convention: `S06_20261014_analyzer-check_RUN-ID.png`, stored in
`evidence/screenshots/`.

## Automated test results

| Date | Gate | What was checked | Result | Where |
|---|---|---|---|---|
| 11 Oct 2026 | G1 | Cache key covers prompt, model, digest and every generation setting; hit/miss counted; corrupt entry treated as a miss, not a prediction | 8 checks pass | `tests/test_cache.py` |
| 11 Oct 2026 | G1 | Logical vs physical call counting; cache hit carries no latency; prompt cap rejects before spending a call; repair retry is a new counted call; failures recorded and not cached | 10 checks pass | `tests/test_llm_client.py` |
| 11 Oct 2026 | G1 | Run folder writes config and manifest; run IDs never reused; failed runs stay visible; data hashes recorded | 7 checks pass | `tests/test_runs.py` |
| 11 Oct 2026 | G2 | MASSIVE `annot_utt` to character-span conversion: slot at position 0, slot at end, repeated value, adjacent slots, inconsistent annotation rejected, and all 16,521 en-US records converted | 9 checks pass, 16,521/16,521 records, 0 mismatches | `tests/test_massive.py` |
| 11 Oct 2026 | G2 | Split sizes, official-split provenance, in-scope domain membership, out-of-scope pool rule, no shared case ID within or across projects, gold span indexing, file hashes, declared overlaps, frozen descriptions present | 34 checks pass | `tests/test_data_splits.py` |
| 11 Oct 2026 | G3 | Span-location rule: repeated substring takes the next unclaimed occurrence, missing substring is unsupported and never fuzzy-matched, case difference matches case-insensitively, overlapping entities cannot claim the same characters, quotes stripped but nothing else normalised | 15 checks pass | `tests/test_span_rule.py` |
| 11 Oct 2026 | G3 | Scorer against hand-computed fixtures: perfect, wrong, empty and malformed output; empty output scores 0 entity F1 with unsupported rate N/A rather than 0; failures and missing responses stay in every denominator; latency only from supplied timing runs | 14 checks pass | `tests/test_scorer.py` |
| 11 Oct 2026 | G3 | Output contract: valid shapes, code fences, undeclared intent and entity types, malformed items kept rather than dropped, extra fields, repair instruction | 17 checks pass | `tests/test_output_schema.py` |
| 11 Oct 2026 | G4 | Catalogue has exactly 12 unique configurations covering every factor combination, 4 of them two-stage; B1's configuration is in it; prompts stay inside the cap for all 12; definitions never dropped; two-stage makes 2 calls and stops at 1 on rejection; TF-IDF rejection costs no call; one counted repair retry; runtime failures recorded | 24 checks pass | `tests/test_catalogue.py` |
| 11 Oct 2026 | G4 | Threshold tuning: separable case, ties break toward the lower threshold, reject-nothing reachable, criterion recorded; B0 makes no model calls, extracts no entities, entity F1 0 with unsupported rate N/A, refuses to predict before tuning, deterministic | 16 checks pass | `tests/test_thresholds_b0.py` |
| 12 Oct 2026 | G4 | Repair parity across extraction strategies: a broken two-stage stage one gets exactly one repair, the repair asks only for an intent and offers exactly the labels its prompt offered, a failed repair still ends invalid, the retry is counted, disabling repair disables it everywhere, and all three strategies make exactly one call plus one repair | 10 checks pass | `tests/test_catalogue_repair_parity.py` |
| 12 Oct 2026 | G6 | Data access guard: train and dev available, the test split locked before the freeze with no back door, every split of the held-out project locked, release requires the freeze commit and returns a new handle leaving the original locked, refused accesses not recorded as accesses | 15 checks pass | `tests/test_access.py` |
| 12 Oct 2026 | G6 | Analyzer: clean spec passes; duplicate intents, duplicate entity types, the reserved OOS label, an empty inventory or description, impossible constraints, and pool labels outside the inventory are all rejected; missing examples reported without blocking; constraints preserved; enrichment cannot add, rename or remove a declared name, and an undescribed name keeps no description; unparseable or failed enrichment reported without blocking | 25 checks pass | `tests/test_analyzer.py` |
| 12 Oct 2026 | G7 | Architect: exactly 3 initial + 1 revision evaluated, over-proposals cut and logged, duplicates refused, hallucinated configuration ids discarded and replaced by a recorded fallback, every attempt carries a rationale and its source, reasoned and fallback choices counted separately, planning calls separated from runtime calls, a crashed candidate still consumes its slot and is excluded from selection, no-eligible-candidate reported explicitly, and the revision prompt provably contains the development error report | 23 checks pass | `tests/test_architect.py` |
| 12 Oct 2026 | G5 | B3 BIO decoding: adjacent same-type entities not merged, a type change mid-entity is a boundary, orphan I- tags still produce an entity, tags on special tokens ignored, decoded text always a substring of the utterance, whitespace-only spans dropped | 14 checks pass, 1 skipped pending torch | `tests/test_b3_encoder.py` |
| 13 Oct 2026 | G8 | Full design run: A1 and B4 are handed the same evaluator closure, evaluation never produces a latency figure, design cost includes Analyzer and planning calls, a known score table selects the known winner, a contradictory specification stops the design before any candidate, an impossible constraint yields an explicit no-eligible outcome, the no-Analyzer ablation skips enrichment, and a design run provably never touches the test split | 15 checks pass | `tests/test_design_run.py` |
| 11 Oct 2026 | G5 | Selection rule: highest intent macro-F1 wins, ties break by entity F1 then lower p95 then config id, order-independent; a hard constraint beats a better headline score; no-eligible-candidate is explicit; a missing score is rejected not treated as zero; an unknown latency is recorded as unchecked | 13 checks pass | `tests/test_selection_b4.py` |
| 11 Oct 2026 | G5 | B4 search: a seed always draws the same configurations, different seeds differ, budget respected with no duplicates, draws only from the catalogue, exhaustive finds the catalogue best, random sometimes misses it, logical calls reported separately from physical, five-seed summary reports a spread and counts no-eligible seeds | 17 checks pass | `tests/test_selection_b4.py` |
| 11 Oct 2026 | G5 | B3 Kaggle assets: the uploaded split file carries no test IDs and no P3; its case IDs and hashes match the frozen manifests exactly; the notebook is valid JSON with compiling cells, never mentions P3 or test splits, verifies the G2 dataset hash, refuses to train on out-of-scope examples, exports predictions rather than metrics, and marks B3-full as an upper reference | 11 checks pass | `tests/test_b3_assets.py` |

Reproduce with: `python -m pytest tests -q` (298 passed, 1 skipped, 13 Oct 2026).

## Runs

| Run ID | Gate | System / project | Status | Notes |
|---|---|---|---|---|
| `20261011_1614_P1_B0_0` | G4 | B0 / P1 development | complete | Intent macro-F1 0.780, OOS F1 0.510, entity F1 0 (no extraction by design). Threshold 0.3482 tuned on this same split, so optimistic |
| `20261011_1614_P2_B0_0` | G4 | B0 / P2 development | complete | Intent macro-F1 0.730, OOS F1 0.510, entity F1 0. Threshold 0.2944, same bias note |
| `20261012_0020_setup_throughput_0` | G0 | qwen2.5:3b throughput and determinism | complete | 50 full-size requests x 2 passes, cache disabled. Median 0.42 s, p95 0.59 s, JSON validity 1.00, **identical-output rate 1.00**, 0 failures, expected budget about 2.4 h |
| `20261013_0043_P1_B1_0` | G8 | B1 / P1 development | complete | intent 0.927, entity 0.610, OOS 0.870, schema 1.000 |
| `20261013_0049_P1_A1_0` | G8 | A1 / P1 development | complete | selected `twostage-sim-llm`, intent 0.958; 4/4 choices reasoned; 453 logical calls, 2 planning |
| `20261013_0056_P1_B4-random_seeds` | G8 | B4-random / P1 development | complete | 5 seeds: mean 0.954, sd 0.004, range 0.951-0.958 |
| `20261013_0056_P1_B4-exhaustive_0` | G8 | B4-exhaustive / P1 development | complete | all 12 configurations; ceiling 0.958 (`twostage-sim-llm`) |

## Screenshots

| ID | Gate | What it must show | Status | File |
|---|---|---|---|---|
| S00 | G0 | Throughput report title, run ID, date, per-model median/p95/JSON-validity/determinism, chosen model | **Ready to capture** - `runs/20261012_0020_setup_throughput_0/summary.md`; recapture after the 8B is measured | - |
| S01 | G1 | `pytest` output with the passing checks, plus the repository tree | Pending | - |
| S02 | G2 | Data manifest: MASSIVE version, licence, counts, label inventory, split IDs, description commit hash | **Ready to capture** - run `python scripts/prepare_data.py` and show `docs/DATA_REPORT.md` | - |
| S03 | G3 | Evaluator unit-test report including every span-rule case | **Ready to capture** - run `python -m pytest tests/test_span_rule.py tests/test_scorer.py tests/test_output_schema.py -v` | - |
| S04 | G4 | All 12 catalogue configurations running; B0/B1 development outputs | **Ready to capture** - `python scripts/run_catalogue_check.py --model qwen2.5:3b --n 10` | - |
| S05 | G5 | B2 timing record, B3-k score, B4 seed determinism | Pending | - |
| S06 | G6 | Analyzer preserving intents and required entities; conflict flagged | **Ready to capture** - `python -m pytest tests/test_analyzer.py tests/test_access.py -v` plus the live P1/P2 enrichment output | - |
| S07 | G7 | Candidate plans with rationale; budget cap respected | **Ready to capture** - `python -m pytest tests/test_architect.py -v` | - |
| S08 | G8 | Development leaderboard and selection decision log | **Ready to capture** - `runs/20261013_0056_P1_B4-exhaustive_0/events.jsonl` gives the 12-configuration leaderboard, and the A1 run's events give the decision log | - |
| S09 | G9 | Fresh process loading the exported artifact; normal/OOS/invalid requests | Pending | - |
| S10 | G10 | Freeze commit, protocol.md thresholds, exact test call budget | Pending | - |
| S11 | G11 | Final comparison tables with confidence intervals | Pending | - |
| S12 | G12 | Reproduction log showing metrics recomputed from saved predictions | Pending | - |

## Decisions

Recorded in `decisions.md`.
