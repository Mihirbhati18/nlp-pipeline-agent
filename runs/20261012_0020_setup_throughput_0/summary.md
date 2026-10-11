# G0 throughput and determinism test (20261012_0020_setup_throughput_0)

Ollama 0.40.2. 50 full-size requests per pass, cache disabled.

| model | median s | p95 s | JSON valid | identical repeat | est. h for 21k calls | eligible |
|---|---|---|---|---|---|---|
| qwen2.5:3b | 0.42 | 0.59 | 1.00 | 1.00 | 2.4 | yes |

**Chosen runtime model: qwen2.5:3b**

qwen2.5:3b is the largest candidate meeting both rules: JSON validity 1.00 and an estimated 2.4 h for the expected 21,000-call budget.
