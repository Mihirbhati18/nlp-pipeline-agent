# Evidence summary (25 Oct 2026 15:00)

Code version: `2b6e7a7 Project explanation and verification guide (Word), with diagrams and real command outputs` (35 commits in the history)

## 1. Automated tests
`python -m pytest tests` -> **371 passed in 14.59s**

## 2. Results recomputed from saved predictions
`python scripts/reproduce_metrics.py` -> {'not checkable': 22, 'match': 44}
Every run with saved predictions was re-scored; a 'match' means the recorded number is exactly what the code computes.

## 2b. Metrics recomputed independently with scikit-learn
`python scripts/verify_with_sklearn.py` -> {'agrees': 44, 'skipped': 1}
scikit-learn, the standard machine-learning library, recomputed intent macro-F1, accuracy and out-of-scope precision, recall and F1 from the saved predictions without using our scorer.

## 3. Recorded experiment runs
66 run folders in `runs/`, each with its config, manifest (git commit, model digest, data hashes) and metrics:
- A1: 5
- A1-noAnalyzer: 2
- A1-noReasoning: 2
- A1-noRepair: 2
- A1-noSelection: 2
- A1-oneCandidate: 2
- A1-robust-caps: 2
- A1-robust-filler: 2
- A1-robust-typo: 2
- A1-selected: 2
- A1-timing: 2
- A2: 2
- A2-planner-qwen2.5-3b: 2
- A2-selected: 2
- B0: 2
- B0-robust-caps: 2
- B0-robust-filler: 2
- B0-robust-typo: 2
- B1: 4
- B1-robust-caps: 2
- B1-robust-filler: 2
- B1-robust-typo: 2
- B1-timing: 2
- B2: 2
- B3-full: 2
- B3-k: 2
- B4-exhaustive: 4
- B4-random: 4
- throughput: 1

## 4. Headline results (development data, intent macro-F1 / entity F1)

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

## 6. Live demo of the exported pipeline
```
Loaded P1 (Home assistant) pipeline twostage-sim-llm, package ff3d548a0af2
Model qwen2.5:3b @ 357c53fb659c | 12 intents, 18 entity types

[normal] 'wake me up at six thirty tomorrow'
  -> ok  intent=alarm_set  time='six thirty', date='tomorrow'  [2 model calls, 14.14s]
[normal] 'turn the bedroom lights off'
  -> ok  intent=iot_hue_lightoff  house_place='bedroom'  [2 model calls, 0.70s]
[out of scope] 'who won the football match last night'
  -> out_of_scope  [1 model calls, 0.30s]
[invalid] ''
  -> invalid_request  error: request is empty  [0 model calls, 0.00s]
[invalid] 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx...'
  -> invalid_request  error: request is 600 characters; the limit is 500  [0 model calls, 0.00s]
```

**Overall: all checks passed**
