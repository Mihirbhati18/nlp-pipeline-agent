# Experiment protocol

This file becomes the frozen protocol at G10. Until the freeze commit, every
value marked provisional may still change, and each change is logged in
`decisions.md`. After the freeze, nothing here changes.

Status: **FROZEN on 25 October 2026 (G10).** Created 11 October 2026. The freeze commit's hash is recorded in section 7 and in `decisions.md` (decision 46). Nothing in this file changes after the freeze.

## 1. Runtime model

Measured at G0 on 12 October 2026, run `20261012_0020_setup_throughput_0`.

| Field | Value |
|---|---|
| Model name and tag | `qwen2.5:3b` (**confirmed 13 Oct**; see the candidate note below) |
| Model digest | `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b` |
| Weights blob SHA-256 | `5ee4f07cdb9beadbbb293e85803c569b01bd37ed059d2715faa7bb405f31caa6` |
| Parameter size | 3.1B |
| Quantization | Q4_K_M |
| Ollama version | 0.40.2 |
| Temperature | 0.0 |
| Seed | 0 |
| Output format | JSON |
| Max output tokens | 512 |
| **Identical-output rate on repeat** | **1.00 (50 of 50)** - fully deterministic, so no determinism limitation needs reporting |

### G0 measured throughput

| Measure | Value |
|---|---|
| Requests | 50 full-size prompts (mean 1,028 input tokens, 16 examples), cache disabled |
| Median latency | 0.42 s |
| p95 latency | 0.59 s |
| JSON validity | 1.00 |
| Runtime failures | 0 |
| Estimated time for the expected 21,000-call budget | **2.4 h** |

The plan's section 2A worried the expected budget might take 17-35 h and not fit
two overnight batches. Measured, it is about 2.4 h, so compute is not a
constraint on this project. Cold start is separate and was about 69 s for the
first request after the model is loaded from disk.

### Candidate set, and why only one size was measured

Section 2A asks for a roughly 3B and a roughly 7-8B candidate, with the largest
eligible one chosen. Only `qwen2.5:3b` was measured. `llama3.1:8b` was attempted
twice over two days and abandoned on 13 October: the connection averaged
25-60 KB/s for long stretches, one `ollama pull` failed with
`max retries exceeded: unexpected EOF`, a resumable direct download produced a
corrupt file, and the partial data did not survive a restart.

The paper must therefore say: *one model size was evaluated; a larger candidate
was not evaluated because of bandwidth limits, so the plan's largest-eligible
rule was applied over a single candidate.* This is a stated limitation, not a
claim that the 3B is the best choice.

What is unaffected: every LLM-based system (B1, B2, B4, A1 and all ablations)
uses this one model, the same quantization and the same settings, so the
central comparison stays fair. A larger model would likely raise every
system's absolute scores together; it is the differences between systems that
the research questions turn on.

Hardware context for the limitation: the laptop has 4 GB of VRAM, and an 8B
model at Q4_K_M needs about 4.7 GB, so it could not have run fully on the GPU
and would likely have been several times slower than the measured 0.42 s.

One runtime model serves B1, B2, B4, A1 and all ablations. The Architect's
planning calls may use a free API model; that provider, model ID and date are
recorded per call, and such models are never used for runtime predictions in
reported results.

## 2. Prompt cap

At most 16 examples and at most 2,000 input tokens per request, whichever is
reached first. Examples are dropped first; intent and entity definitions are
never truncated. Actual token counts are logged per request.

## 3. Budgets

| Budget | Value |
|---|---|
| Candidate evaluations per project (A1) | 4 (3 initial + 1 revision) |
| B4-random configurations | 4 per seed, 5 seeds |
| B4-exhaustive | all 12 configurations |
| Architect design repeats per project | 1 (deviation from the plan; decision 44) |
| Expected total model calls | about 21,000 |
| Hard upper bound | about 36,700 |
| Exact test call count | **at most 7,800 first-attempt calls** (3,900 per project for P1 and P2: 15 frozen choices, 9 and 10 distinct pipelines, 300 test cases each; repairs add at most one per failed reply; TF-IDF rejections make fewer). Computed with `python scripts/run_final.py --count` from the manifests, before any test access. B3 makes no LLM calls. P3 is counted when it is released. |

## 4. Success thresholds (frozen 25 Oct)

| Symbol | Meaning | Frozen value |
|---|---|---|
| delta_I | Minimum intent macro-F1 improvement of A1 over B1 | +2.0 points |
| epsilon_E | Largest acceptable entity F1 drop of A1 vs B1 | 2.0 points |
| S_min | Minimum schema validity after repair | 0.98 |
| L_max | Maximum p95 latency for an agent (A1, A2) | **2 x B1's p95 measured in the same interleaved timing session**: 1.22 s on P1 and 1.67 s on P2 (`reports/timing_interleaved.json`, 25 Oct). The 16 Oct B1 timing gave 1.18 s and 1.58 s; both agents are within either limit. |

Rule (applies to A1 and A2): an agent succeeds against B1 if intent improvement is at least delta_I, the
entity difference is no worse than -epsilon_E, schema validity is at least
S_min, and p95 latency is at most L_max.

## 4a. Data as frozen at G2

| Project | Domains | Intents | Entity types | k-shot | Dev | Test |
|---|---|---|---|---|---|---|
| P1 Home assistant | alarm, iot | 12 | 18 | 120 | 100 (80 + 20 OOS) | 300 (250 + 50 OOS) |
| P2 Productivity assistant | calendar, email, lists | 10 | 26 | 100 | 100 (80 + 20 OOS) | 300 (250 + 50 OOS) |
| P3 Ordering and travel (held out) | takeaway, transport | 6 | 19 | 60 | 100 (80 + 20 OOS) | 200 (167 + 33 OOS) |

Sampling seed 20261011, per-project stream `20261011|<project>`. Verified
reproducible. Full counts, limitations and the two declared near-duplicate
overlaps are in `DATA_REPORT.md`.

## 5. Data access rules

- Train: model fitting and few-shot example selection.
- Development: prompts, candidates, thresholds, hyperparameters.
- Test: only after this protocol, the configurations, metrics and budgets are frozen.
- P3 is excluded from every pre-freeze step except writing and committing its
  description at G2. Gates G4-G10 use only P1 and P2.
- OOS examples are never used for training in any system.
- OOS thresholds (B0 TF-IDF, B3 max-softmax) are tuned on development data only.

## 6. Latency measurement

Latency figures come only from uncached timing runs: 50 fixed development cases
per system and project, after a 5-request warm-up, with the cache disabled.
From 25 Oct the systems are timed **interleaved** (`scripts/run_timing.py`): each request goes to B1, A1 and A2 in
turn, so a slowdown of the machine affects all of them equally. Timings taken while other programs use the GPU are
discarded (decision 46).
Cold start is measured separately. Cache hits never contribute a latency number.

## 7. Frozen artifacts

| Artifact | Commit hash | Date |
|---|---|---|
| Project descriptions P1, P2, P3 (`configs/descriptions/`) | `dd4e25ab240f18438888404dc8a8d06e1f59a3ac` | 11 Oct 2026 |
| Split IDs, k-shot pools and entity schemas (`data/manifests/`) | `dd4e25ab240f18438888404dc8a8d06e1f59a3ac` | 11 Oct 2026 |
| Protocol, thresholds, configurations, code | the G10 freeze commit (see decision 46) | 25 Oct 2026 |

## 8. Frozen choices (G10)

Every system's choice was made on development data before the freeze and is replayed, not re-made, at test time
(`scripts/run_final.py`). P1 / P2:

| System | P1 | P2 |
|---|---|---|
| B0 | TF-IDF + logistic regression, dev-tuned threshold | same |
| B1 | joint-fixed-llm, bare specification | same |
| B2 | twostage-sim-tfidf (worksheet) | twostage-sim-llm (worksheet, ChatGPT-assisted) |
| B3-k / B3-full | XLM-R, seed 0, 30 / 5 epochs, threshold tuned on dev | same |
| B4-random seeds 0-4 | twostage-sim-llm, joint-sim-llm, schema-sim-llm, joint-sim-llm, twostage-sim-llm | same designs |
| B4-best (all 12) | schema-sim-llm | schema-sim-llm |
| A1 | twostage-sim-llm | schema-fixed-llm |
| A2 | schema-sim-llm | schema-sim-llm |
| A1 ablations | noAnalyzer twostage-sim-llm; noReasoning twostage-sim-llm; noSelection and oneCandidate joint-fixed-llm; noRepair twostage-sim-llm | noAnalyzer twostage-fixed-llm; noReasoning joint-sim-llm; noSelection and oneCandidate joint-fixed-llm; noRepair schema-fixed-llm |

Exported packages: A1 `artifacts/P1/twostage-sim-llm-ff3d548a0af2`, `artifacts/P2/schema-fixed-llm-d754b7d4ad80`;
A2 `artifacts/P1/schema-sim-llm-b7847545a937`, `artifacts/P2/schema-sim-llm-630708f9b329`.

Primary comparisons, reported per project with paired bootstrap 95% intervals: A2 and A1 against B1 (the success
rule), against B4-random (RQ5), against B2 (RQ2) and against B3-k. A1 and A2 are both reported whichever does better
(decision 42). A3 is future work (decision 47). P3 follows the same procedure once released: design on its
development data, then test; it has no B2.
