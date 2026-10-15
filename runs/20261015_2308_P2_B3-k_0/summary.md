# B3-k on P2 (development)

xlm-roberta-base fine-tuned on 100 cases for 30 epochs, seed 0, on cpu in 646 s.

**Role in the comparison:** matched comparison at k=10 per intent

| Metric | Value |
|---|---|
| Intent macro-F1 | 0.833 |
| Entity span F1 | 0.448 |
| Out-of-scope P / R / F1 | 0.565 / 0.650 / 0.605 |
| In-scope false rejection | 0.125 |
| Unsupported extraction rate | 0.0 |

Out-of-scope threshold 0.7708, chosen by macro-F1 over intents plus the out-of-scope class, dev only.

the out-of-scope threshold was tuned on this same development split, so these development numbers are optimistic.

Scored with the shared scorer and span rule, so these numbers are directly comparable with every other system's.
