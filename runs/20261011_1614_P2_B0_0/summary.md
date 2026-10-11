# B0 on P2 (development)

TF-IDF + logistic regression, 100 training examples (k=10 per intent), 0 model calls.
Out-of-scope threshold 0.2944, chosen by macro-F1 over intents plus the out-of-scope class, dev only.

| Metric | Value |
|---|---|
| Intent macro-F1 | 0.730 |
| Intent accuracy (in-scope) | 0.650 |
| Entity span F1 | 0.000 (no entity extraction by design) |
| Out-of-scope precision / recall / F1 | 0.419 / 0.650 / 0.510 |
| In-scope false rejection | 0.225 |
| Schema validity | 1.000 (output is constructed, not generated) |
| Unsupported extraction rate | None (N/A: nothing predicted) |

These are development numbers with the threshold tuned on this same split, so they are optimistic. B0 is a sanity reference, not a state-of-the-art claim.
