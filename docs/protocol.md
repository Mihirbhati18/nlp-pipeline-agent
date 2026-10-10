# Experiment protocol

This file becomes the frozen protocol at G10. Until the freeze commit, every
value marked provisional may still change, and each change is logged in
`decisions.md`. After the freeze, nothing here changes.

Status: **draft, not frozen.** Created 11 October 2026.

## 1. Runtime model

| Field | Value |
|---|---|
| Model name and tag | _decided at G0 by measurement_ |
| Model digest | _recorded automatically in every run manifest_ |
| Quantization | _as pulled; recorded at G0_ |
| Ollama version | _recorded at G0_ |
| Temperature | 0.0 |
| Seed | 0 |
| Output format | JSON |
| Max output tokens | 512 |
| Identical-output rate on repeat | _measured at G0; reported as a limitation if below 100%_ |

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
| Project descriptions P1, P2, P3 | _at G2_ | |
| Split IDs and k-shot pools | _at G2_ | |
| Protocol, thresholds, configurations, code | _at G10_ | |
