# Evidence summary (28 Oct 2026 00:41)

Code version: `d4b017d Add plain-language paper explainer; live reproduction 50/50 identical` (57 commits in the history)

## 1. Automated tests
`python -m pytest tests` -> **371 passed in 18.50s**

## 2. Results recomputed from saved predictions
`python scripts/reproduce_metrics.py` -> {'match': 99, 'not checkable': 30}
Every run with saved predictions was re-scored; a 'match' means the recorded number is exactly what the code computes.

## 2b. Metrics recomputed independently with scikit-learn
`python scripts/verify_with_sklearn.py` -> {'agrees': 99, 'skipped': 1}
scikit-learn, the standard machine-learning library, recomputed intent macro-F1, accuracy and out-of-scope precision, recall and F1 from the saved predictions without using our scorer.

## 3. Recorded experiment runs
129 run folders in `runs/`, each with its config, manifest (git commit, model digest, data hashes) and metrics:
- A1: 5
- A1-final: 3
- A1-noAnalyzer: 2
- A1-noAnalyzer-final: 3
- A1-noReasoning: 2
- A1-noReasoning-final: 3
- A1-noRepair: 2
- A1-noRepair-final: 3
- A1-noSelection: 2
- A1-noSelection-final: 3
- A1-oneCandidate: 2
- A1-oneCandidate-final: 3
- A1-robust-caps: 2
- A1-robust-filler: 2
- A1-robust-typo: 2
- A1-selected: 2
- A1-timing: 2
- A1-timing-interleaved: 2
- A2: 4
- A2-final: 3
- A2-planner-qwen2.5-3b: 2
- A2-selected: 2
- A2-timing-interleaved: 2
- B0: 4
- B0-final: 3
- B0-robust-caps: 2
- B0-robust-filler: 2
- B0-robust-typo: 2
- B1: 4
- B1-final: 3
- B1-robust-caps: 2
- B1-robust-filler: 2
- B1-robust-typo: 2
- B1-timing: 2
- B1-timing-interleaved: 2
- B2: 2
- B2-final: 2
- B3-full: 2
- B3-full-final: 3
- B3-k: 2
- B3-k-final: 3
- B4-best-final: 3
- B4-exhaustive: 4
- B4-random: 4
- B4-random-seed0-final: 3
- B4-random-seed1-final: 3
- B4-random-seed2-final: 3
- B4-random-seed3-final: 3
- B4-random-seed4-final: 3
- throughput: 1

## 4. Final results on the locked test data (freeze commit `0ee6b22b86`)
Intent macro-F1 / entity F1 / out-of-scope F1. P3 was held out until the freeze.

| System | P1 | P2 | P3 |
|---|---|---|---|
| B0 word matching | 0.699 / 0.000 / 0.426 | 0.669 / 0.000 / 0.403 | 0.769 / 0.000 / 0.404 |
| B1 generic prompt | 0.876 / 0.626 / 0.875 | 0.823 / 0.477 / 0.662 | 0.895 / 0.529 / 0.771 |
| B2 human | 0.837 / 0.648 / 0.471 | 0.851 / 0.491 / 0.748 | not run |
| B3-k XLM-R, same examples | 0.809 / 0.650 / 0.568 | 0.800 / 0.461 / 0.536 | 0.770 / 0.515 / 0.505 |
| B3-full XLM-R, all data | 0.883 / 0.802 / 0.604 | 0.904 / 0.775 / 0.560 | 0.913 / 0.721 / 0.581 |
| A1 first agent | 0.903 / 0.639 / 0.885 | 0.852 / 0.504 / 0.758 | 0.889 / 0.506 / 0.845 |
| A2 improved agent | 0.898 / 0.699 / 0.865 | 0.872 / 0.532 / 0.767 | 0.882 / 0.675 / 0.795 |
| B4 random search, mean intent (range) | 0.893 (0.881-0.903) | 0.854 (0.848-0.872) | 0.894 (0.882-0.909) |

A2 against B1, intent macro-F1 difference with 95% paired bootstrap interval:
- P1: +0.022 [-0.006, +0.051]
- P2: +0.049 [+0.011, +0.089]
- P3: -0.013 [-0.038, +0.014]
Figures: `reports/figures/final/`; paper version: `paper/figures/`.

## 4b. Live reproduction (`python scripts/reproduce_live.py`)
- B0 retrained from scratch: identical on 15 metrics
- A2 asked live, cache off: 50 of 50 P1 test answers identical to the recorded ones (50 real model calls)

## 4c. Development results (before the freeze, intent macro-F1 / entity F1)

| System | P1 | P2 |
|---|---|---|
| B0 word matching | 0.780 / 0.000 | 0.730 / 0.000 |
| B1 generic prompt | 0.927 / 0.610 | 0.804 / 0.451 |
| B3-k published, matched | 0.909 / 0.650 | 0.833 / 0.448 |
| A1 our agent | 0.958 / 0.597 | 0.841 / 0.365 |
| B3-full, all data (reference) | 0.936 / 0.768 | 0.923 / 0.797 |

Full analysis: `reports/DEV_ANALYSIS.md`; findings with caveats: `docs/FINDINGS.md`.

## 5. Figures
- `reports/figures/fig1_main_comparison.png`
- `reports/figures/fig2_intent_vs_entity.png`
- `reports/figures/fig3_design_landscape.png`
- `reports/figures/fig4_ablations.png`
- `reports/figures/fig5_error_analysis.png`
- `reports/figures/fig6_robustness.png`
- `reports/figures/final/final1_intent.png`
- `reports/figures/final/final2_entity.png`
- `reports/figures/final/final3_differences_ci.png`
- `reports/figures/final/final4_ablations.png`

## 6. Live demo of the exported pipeline
```
Loaded P1 (Home assistant) pipeline schema-sim-llm, package b7847545a937
Model qwen2.5:3b @ 357c53fb659c | 12 intents, 18 entity types

[normal] 'wake me up at six thirty tomorrow'
  -> ok  intent=alarm_set  time='six thirty', date='tomorrow'  [1 model calls, 1.16s]
[normal] 'turn the bedroom lights off'
  -> ok  intent=iot_hue_lightoff  house_place='bedroom'  [1 model calls, 1.74s]
[out of scope] 'who won the football match last night'
  -> out_of_scope  [1 model calls, 0.37s]
[invalid] ''
  -> invalid_request  error: request is empty  [0 model calls, 0.00s]
[invalid] 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx...'
  -> invalid_request  error: request is 600 characters; the limit is 500  [0 model calls, 0.00s]
```

**Overall: all checks passed**
