# B2 on P2 (development)

Configuration `twostage-sim-llm`, chosen by hand. 10 of 10 intents and 14 of 26 fields described by hand.

**Active human time: 15 minutes** of a 120-minute budget, across 1 development check(s).
AI assistance: Used ChatGPT to recommend an initial configuration and draft and explain the intent and entity descriptions.

| Metric | Value |
|---|---|
| Intent macro-F1 | 0.861 |
| Entity span F1 | 0.394 |
| Out-of-scope F1 | 0.783 |
| Schema validity | 1.000 |

the same person built the automated system and this manual baseline, and already knows the data. This is a single, non-blind measurement of setup effort and must be reported as such.

Notes: Selected twostage-sim-llm because intent classification followed by field extraction may help preserve multiple details in complex productivity requests. Similar examples may improve recognition of varied wording, and LLM-based out-of-scope handling may recognize unsupported requests beyond lexical similarity. Trade-offs include two model calls, additional latency, and possible incorrect classifications. No development checks have been run yet. Active time estimated at 10-20 minutes; 15 recorded as the midpoint.
