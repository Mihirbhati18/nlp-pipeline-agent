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

Reproduce with: `python -m pytest tests -q` (114 passed, 11 Oct 2026).

## Runs

| Run ID | Gate | System / project | Status | Notes |
|---|---|---|---|---|
| _none yet_ | - | - | - | No model run exists. G2 data preparation is deterministic and recorded in `data/manifests/`, not as a run folder. The first run folder will be the G0 throughput test |

## Screenshots

| ID | Gate | What it must show | Status | File |
|---|---|---|---|---|
| S00 | G0 | Throughput report title, run ID, date, per-model median/p95/JSON-validity/determinism, chosen model | Pending - needs Ollama | - |
| S01 | G1 | `pytest` output with the passing checks, plus the repository tree | Pending | - |
| S02 | G2 | Data manifest: MASSIVE version, licence, counts, label inventory, split IDs, description commit hash | **Ready to capture** - run `python scripts/prepare_data.py` and show `docs/DATA_REPORT.md` | - |
| S03 | G3 | Evaluator unit-test report including every span-rule case | **Ready to capture** - run `python -m pytest tests/test_span_rule.py tests/test_scorer.py tests/test_output_schema.py -v` | - |
| S04 | G4 | All 12 catalogue configurations running; B0/B1 development outputs | Pending | - |
| S05 | G5 | B2 timing record, B3-k score, B4 seed determinism | Pending | - |
| S06 | G6 | Analyzer preserving intents and required entities; conflict flagged | Pending | - |
| S07 | G7 | Candidate plans with rationale; budget cap respected | Pending | - |
| S08 | G8 | Development leaderboard and selection decision log | Pending | - |
| S09 | G9 | Fresh process loading the exported artifact; normal/OOS/invalid requests | Pending | - |
| S10 | G10 | Freeze commit, protocol.md thresholds, exact test call budget | Pending | - |
| S11 | G11 | Final comparison tables with confidence intervals | Pending | - |
| S12 | G12 | Reproduction log showing metrics recomputed from saved predictions | Pending | - |

## Decisions

Recorded in `decisions.md`.
