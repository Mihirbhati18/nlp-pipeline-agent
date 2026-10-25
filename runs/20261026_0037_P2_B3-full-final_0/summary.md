# B3-full on P2 (test)

xlm-roberta-base fine-tuned on 3180 cases for 5 epochs, seed 0, on cpu in 2094 s.

**Role in the comparison:** UPPER REFERENCE ONLY, trained on the full split; never a matched comparison

| Metric | Value |
|---|---|
| Intent macro-F1 | 0.904 |
| Entity span F1 | 0.775 |
| Out-of-scope P / R / F1 | 0.560 / 0.560 / 0.560 |
| In-scope false rejection | 0.088 |
| Unsupported extraction rate | 0.0 |

Out-of-scope threshold 0.9204, chosen by macro-F1 over intents plus the out-of-scope class, dev only.

the out-of-scope threshold was tuned on this same development split, so these development numbers are optimistic.

Scored with the shared scorer and span rule, so these numbers are directly comparable with every other system's.
