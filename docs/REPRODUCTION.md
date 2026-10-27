# Reproduction log (G12)

How every reported number can be reproduced, and what has been reproduced. Last checked 28 Oct 2026 on the
project laptop (RTX 3050 4 GB, Ollama 0.40.2, `qwen2.5:3b` digest `357c53fb659c`).

Freeze commit: `0ee6b22b86894aebbe253fae3b00eb97c542c575` (G10, 25 Oct 2026). Test data and the held-out
project P3 are released only by naming this commit.

## 1. What was reproduced, and the result

| Check | Command | Result |
|---|---|---|
| Automated tests | `python -m pytest tests` | 371 passed |
| Every metric recomputed from saved predictions (dev and test) | `python scripts/reproduce_metrics.py` | 99 of 99 runs match exactly; 30 runs have no predictions to check (timing, throughput, design runs) |
| Independent recomputation with scikit-learn | `python scripts/verify_with_sklearn.py` | 99 agree to 9 decimal places, 1 skipped (not a scored run) |
| B0 retrained from nothing on P1 test | `python scripts/reproduce_live.py --freeze-commit 0ee6b22b...` | identical on all 15 metrics (intent macro-F1 0.6991) |
| A2 asked live, prediction cache off, 50 P1 test requests | same command | 50 of 50 answers identical to the recorded test predictions, 50 real model calls |
| Model repeatability | `python scripts/throughput_test.py` (G0) | 50 of 50 identical outputs on repeat |
| Exported pipeline runs end to end | `python scripts/demo.py --project P1` | A2 package `b7847545a937` loads, verifies hashes and model digest, answers correctly |
| All of the above in one command | `python scripts/show_evidence.py` | "all checks passed" (`reports/EVIDENCE_SUMMARY.md`) |

The live A2 check matters because cached predictions alone cannot show that the model still produces the recorded
answers; with the cache disabled it did, for every request checked. An earlier attempt on 26 Oct failed only
because a failed Ollama auto-update had removed its server binary; after reinstalling the same version (0.40.2)
the model digest was unchanged and the check passed.

## 2. Reproducing from scratch

```bash
python -m pip install -e ".[dev]"
ollama pull qwen2.5:3b                      # digest must start 357c53fb659c
python scripts/prepare_data.py --check      # verifies the frozen splits against data/manifests (SHA-256)
```

Development stage (P1, P2 only):

```bash
python scripts/run_b0.py
python scripts/run_design.py                # A1 design runs and ablations
python scripts/run_a2.py                    # A2 design runs
python scripts/run_b3_local.py              # XLM-R baselines, dev
```

Test stage (only after the freeze; each command needs the freeze commit):

```bash
python scripts/run_final.py --count                                   # exact planned calls, no test access
python scripts/run_final.py --split test --freeze-commit 0ee6b22b86894aebbe253fae3b00eb97c542c575 --projects P1 P2
python scripts/run_final.py --split test --freeze-commit 0ee6b22b86894aebbe253fae3b00eb97c542c575 --projects P3
python scripts/run_b3_local.py --split test --freeze-commit 0ee6b22b86894aebbe253fae3b00eb97c542c575
python scripts/run_timing.py --projects P1 P2                          # close games and other GPU programs first
```

Figures and paper:

```bash
python scripts/make_final_figures.py        # reports/figures/final/
python scripts/make_paper_figures.py        # paper/figures/*.pdf
```

Because model replies are cached by the full prompt, model digest and settings (`cache/`), re-running a stage
replays the same answers in seconds. Delete `cache/` to force every call to be made again; with temperature 0 and
seed 0 the answers are the same (section 1).

## 3. Where each reported number lives

| Number | Source |
|---|---|
| Test scores, all systems and projects | `reports/final_test.json`; B3 in `runs/*_B3-k-final_0`, `runs/*_B3-full-final_0` |
| Bootstrap intervals | `reports/final_test.json` -> `bootstrap` (1,000 resamples, seed 20261016) |
| Latency | `reports/timing_interleaved.json` |
| Development scores and the 12-design landscape | `runs/*_B4-exhaustive_0`, `reports/DEV_ANALYSIS.md` |
| A2 development trace | `runs/20261025_1514_P1_A2_0/events.jsonl`, `runs/20261025_1514_P2_A2_0/events.jsonl` |
| Data counts and hashes | `data/manifests/P1.json`, `P2.json`, `P3.json`, `docs/DATA_REPORT.md` |
| Live reproduction | `reports/reproduction_live.json` |

Each run folder holds `config.json`, `manifest.json` (git commit, model digest, data hashes), `metrics.json` and,
for scored runs, `predictions.jsonl`.

## 4. Known differences from the plan

Recorded in `docs/decisions.md`: one model size was evaluated (decision on bandwidth, protocol section 1); the
Architect's design run was not repeated three times because the local model is deterministic (decision 44); the
latency limit is measured in an interleaved session (decision 46). None of these changes a reported number.
