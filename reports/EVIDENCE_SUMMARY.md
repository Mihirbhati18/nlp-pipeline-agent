# Evidence summary (16 Oct 2026 01:31)

Code version: `ab0c353 Robustness test, figures from run folders, and the analysis report` (22 commits in the history)

## 1. Automated tests
`python -m pytest tests` -> **336 passed in 15.32s**

## 2. Results recomputed from saved predictions
`python scripts/reproduce_metrics.py` -> {'not checkable': 18, 'match': 38}
Every run with saved predictions was re-scored; a 'match' means the recorded number is exactly what the code computes.

## 3. Recorded experiment runs
56 run folders in `runs/`, each with its config, manifest (git commit, model digest, data hashes) and metrics:
- A1: 5
- A1-noAnalyzer: 2
- A1-noReasoning: 2
- A1-noRepair: 2
- A1-noSelection: 2
- A1-oneCandidate: 2
- A1-robust-caps: 2
- A1-robust-filler: 2
- A1-robust-typo: 2
- A1-timing: 2
- B0: 2
- B0-robust-caps: 2
- B0-robust-filler: 2
- B0-robust-typo: 2
- B1: 4
- B1-robust-caps: 2
- B1-robust-filler: 2
- B1-robust-typo: 2
- B1-timing: 2
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
  -> ok  intent=alarm_set  time='six thirty', date='tomorrow'  [2 model calls, 0.95s]
[normal] 'turn the bedroom lights off'
  -> ok  intent=iot_hue_lightoff  house_place='bedroom'  [2 model calls, 0.51s]
[out of scope] 'who won the football match last night'
  -> out_of_scope  [1 model calls, 0.19s]
[invalid] ''
  -> invalid_request  error: request is empty  [0 model calls, 0.00s]
[invalid] 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx...'
  -> invalid_request  error: request is 600 characters; the limit is 500  [0 model calls, 0.00s]
```

**Overall: all checks passed**
