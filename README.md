# An agentic framework for project-specific NLP pipeline design

Research implementation for the NLP digital assignment (DA3, 20 Oct 2026).
The agreed plan is `docs/PROJECT_PLAN.md` (v1.2) — read it before changing
anything about the experiment protocol.

Status: **G0/G1 — setup.** No experimental result exists yet.

## Setup

```bash
python -m pip install -e ".[dev]"
python -m pytest tests -q          # 25 checks, needs no model
```

Runtime model, required by every LLM-based system:

```bash
# install Ollama from https://ollama.com, then:
ollama pull qwen2.5:3b
ollama pull llama3.1:8b
python scripts/throughput_test.py --models qwen2.5:3b llama3.1:8b
```

That last command is the G0 day-1 measurement. It reports median and p95
latency, JSON-validity and the identical-output rate for each candidate, then
applies the plan's model-choice rule. Output lands in `runs/<run_id>/`.

## Layout

| Path | Contents |
|---|---|
| `src/llm/` | One client wrapper, prediction cache, call counters |
| `src/evaluation/` | `new_run()` run-folder helper; scorer and span rule (G3) |
| `src/pipelines/` | The fixed 12-configuration execution catalogue (G4) |
| `src/baselines/` | B0 TF-IDF, B3 encoder, B4 search (G4-G5) |
| `src/analyzer/`, `src/architect/`, `src/runtime/` | G6, G7, G9 |
| `docs/` | Plan, progress tracker, evidence log, protocol, decisions |
| `runs/<run_id>/` | Immutable experiment output |
| `configs/` | Project definitions and frozen descriptions |

## Rules this code enforces, rather than only documenting

- A cache entry is keyed by the full rendered prompt, model name, model digest
  and every generation setting.
- A cache hit returns no latency value, so cached output can never become a
  latency figure. Latency comes only from uncached timing runs.
- Logical calls (what a method would have made on its own) are counted
  separately from physical calls, so cache hits are never reported as free
  design cost.
- A failed call is recorded with its error and never cached as a prediction.
- A prompt over the cap is rejected before a call is spent on it.
- Every run folder is created by one helper that stamps the git commit,
  environment, model digest and data hashes.
