# Experiment protocol

This file becomes the frozen protocol at G10. Until the freeze commit, every
value marked provisional may still change, and each change is logged in
`decisions.md`. After the freeze, nothing here changes.

Status: **draft, not frozen.** Created 11 October 2026.

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
| Architect design repeats per project | 3 |
| Expected total model calls | about 21,000 |
| Hard upper bound | about 36,700 |
| Exact test call count | _computed at G10 before any test call_ |

## 4. Success thresholds (provisional until 16 Oct)

| Symbol | Meaning | Provisional value |
|---|---|---|
| delta_I | Minimum intent macro-F1 improvement of A1 over B1 | +2.0 points |
| epsilon_E | Largest acceptable entity F1 drop of A1 vs B1 | 2.0 points |
| S_min | Minimum schema validity after repair | 0.98 |
| L_max | Maximum p95 latency for A1 | 2x B1's development p95, to be fixed here as a number |

Rule: A1 succeeds against B1 if intent improvement is at least delta_I, the
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
Cold start is measured separately. Cache hits never contribute a latency number.

## 7. Frozen artifacts

| Artifact | Commit hash | Date |
|---|---|---|
| Project descriptions P1, P2, P3 (`configs/descriptions/`) | `dd4e25ab240f18438888404dc8a8d06e1f59a3ac` | 11 Oct 2026 |
| Split IDs, k-shot pools and entity schemas (`data/manifests/`) | `dd4e25ab240f18438888404dc8a8d06e1f59a3ac` | 11 Oct 2026 |
| Protocol, thresholds, configurations, code | _at G10_ | |
