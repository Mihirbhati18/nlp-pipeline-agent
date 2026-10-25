# B3-k on P1 (test)

xlm-roberta-base fine-tuned on 120 cases for 30 epochs, seed 0, on cpu in 499 s.

**Role in the comparison:** matched comparison at k=10 per intent

| Metric | Value |
|---|---|
| Intent macro-F1 | 0.809 |
| Entity span F1 | 0.650 |
| Out-of-scope P / R / F1 | 0.411 / 0.920 / 0.568 |
| In-scope false rejection | 0.264 |
| Unsupported extraction rate | 0.0058823529411764705 |

Out-of-scope threshold 0.9335, chosen by macro-F1 over intents plus the out-of-scope class, dev only.

the out-of-scope threshold was tuned on this same development split, so these development numbers are optimistic.

Scored with the shared scorer and span rule, so these numbers are directly comparable with every other system's.
