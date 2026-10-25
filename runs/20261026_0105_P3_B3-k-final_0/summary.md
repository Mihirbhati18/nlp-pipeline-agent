# B3-k on P3 (test)

xlm-roberta-base fine-tuned on 60 cases for 30 epochs, seed 0, on cpu in 291 s.

**Role in the comparison:** matched comparison at k=10 per intent

| Metric | Value |
|---|---|
| Intent macro-F1 | 0.770 |
| Entity span F1 | 0.515 |
| Out-of-scope P / R / F1 | 0.371 / 0.788 / 0.505 |
| In-scope false rejection | 0.263 |
| Unsupported extraction rate | 0.005235602094240838 |

Out-of-scope threshold 0.8816, chosen by macro-F1 over intents plus the out-of-scope class, dev only.

the out-of-scope threshold was tuned on this same development split, so these development numbers are optimistic.

Scored with the shared scorer and span rule, so these numbers are directly comparable with every other system's.
