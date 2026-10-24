# B2 on P1 (development)

Configuration `twostage-sim-tfidf`, chosen by hand. 12 of 12 intents and 9 of 18 fields described by hand.

**Active human time: 38 minutes** of a 120-minute budget, across 1 development check(s).
AI assistance: used the internet and Claude's explanation of the configuration options and terms (plus the scripts/b2_examples.py example viewer) to understand them; chose the configuration and wrote all descriptions myself

| Metric | Value |
|---|---|
| Intent macro-F1 | 0.858 |
| Entity span F1 | 0.586 |
| Out-of-scope F1 | 0.588 |
| Schema validity | 1.000 |

the same person built the automated system and this manual baseline, and already knows the data. This is a single, non-blind measurement of setup effort and must be reported as such.

Notes: I selected twostage-sim-tfidf because the two-stage approach first identifies the user's intent and then extracts the required information. Similarity-based examples help the model understand different ways of expressing commands. TF-IDF helps reject requests outside the supported tasks. A possible disadvantage is that the two-stage approach requires two model calls, which may increase response time. TF-IDF may also reject some valid requests with unusual wording.
