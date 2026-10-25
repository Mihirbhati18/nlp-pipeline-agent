# B3-full on P1 (test)

xlm-roberta-base fine-tuned on 1159 cases for 5 epochs, seed 0, on cpu in 650 s.

**Role in the comparison:** UPPER REFERENCE ONLY, trained on the full split; never a matched comparison

| Metric | Value |
|---|---|
| Intent macro-F1 | 0.883 |
| Entity span F1 | 0.802 |
| Out-of-scope P / R / F1 | 0.630 / 0.580 / 0.604 |
| In-scope false rejection | 0.068 |
| Unsupported extraction rate | 0.009852216748768473 |

Out-of-scope threshold 0.8208, chosen by macro-F1 over intents plus the out-of-scope class, dev only.

the out-of-scope threshold was tuned on this same development split, so these development numbers are optimistic.

Scored with the shared scorer and span rule, so these numbers are directly comparable with every other system's.
