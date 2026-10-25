# B3-full on P3 (test)

xlm-roberta-base fine-tuned on 828 cases for 5 epochs, seed 0, on cpu in 566 s.

**Role in the comparison:** UPPER REFERENCE ONLY, trained on the full split; never a matched comparison

| Metric | Value |
|---|---|
| Intent macro-F1 | 0.913 |
| Entity span F1 | 0.721 |
| Out-of-scope P / R / F1 | 0.472 / 0.758 / 0.581 |
| In-scope false rejection | 0.168 |
| Unsupported extraction rate | 0.0 |

Out-of-scope threshold 0.9306, chosen by macro-F1 over intents plus the out-of-scope class, dev only.

the out-of-scope threshold was tuned on this same development split, so these development numbers are optimistic.

Scored with the shared scorer and span rule, so these numbers are directly comparable with every other system's.
