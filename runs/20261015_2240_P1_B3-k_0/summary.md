# B3-k on P1 (development)

xlm-roberta-base fine-tuned on 120 cases for 30 epochs, seed 0, on cpu in 664 s.

**Role in the comparison:** matched comparison at k=10 per intent

| Metric | Value |
|---|---|
| Intent macro-F1 | 0.909 |
| Entity span F1 | 0.650 |
| Out-of-scope P / R / F1 | 0.654 / 0.850 / 0.739 |
| In-scope false rejection | 0.113 |
| Unsupported extraction rate | 0.0 |

Out-of-scope threshold 0.9335, chosen by macro-F1 over intents plus the out-of-scope class, dev only.

the out-of-scope threshold was tuned on this same development split, so these development numbers are optimistic.

Scored with the shared scorer and span rule, so these numbers are directly comparable with every other system's.
