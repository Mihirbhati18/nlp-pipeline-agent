# An agentic framework for project-specific NLP pipeline design

Given a description of a new assistant (its intents, entity schema and ten labelled examples per intent), an agent
designs, tests and exports an intent and slot pipeline that runs on a small local language model. Evaluated on three
projects built from MASSIVE en-US, one held out until the protocol was frozen.

Team: Mihir Bhati (24BCE5341) and Ahana Sharan (24BCE5334), equal contribution. Guide: Vijayaprabakaran K.
VIT Chennai, NLP digital assignment DA3.

Status: **complete.** Protocol frozen at commit `0ee6b22b` (25 Oct 2026); all three projects tested; every result
reproduced (`docs/REPRODUCTION.md`). Paper: `paper/main.tex` (IEEE, 8 pages).

## Results on the locked test data

Intent macro-F1 / entity span F1 / out-of-scope F1.

| System | P1 home assistant | P2 productivity | P3 ordering and travel (held out) |
|---|---|---|---|
| B0 TF-IDF + logistic regression | 0.699 / – / 0.426 | 0.669 / – / 0.403 | 0.769 / – / 0.404 |
| B1 generic prompt | 0.876 / 0.626 / 0.875 | 0.823 / 0.477 / 0.662 | 0.895 / 0.529 / 0.771 |
| B2 human designer | 0.837 / 0.648 / 0.471 | 0.851 / 0.491 / 0.748 | not run |
| B3-k XLM-R, same 10 per intent | 0.809 / 0.650 / 0.568 | 0.800 / 0.461 / 0.536 | 0.770 / 0.515 / 0.505 |
| B3-full XLM-R, full training split | 0.883 / 0.802 / 0.604 | 0.904 / 0.775 / 0.560 | 0.913 / 0.721 / 0.581 |
| B4 random search, mean intent (range) | 0.893 (0.881–0.903) | 0.854 (0.848–0.872) | 0.894 (0.882–0.909) |
| A1 agent, direct planner | 0.903 / 0.639 / 0.885 | 0.852 / 0.504 / 0.758 | 0.889 / 0.506 / 0.845 |
| **A2 agent, factor-wise planner** | **0.898 / 0.699 / 0.865** | **0.872 / 0.532 / 0.767** | **0.882 / 0.675 / 0.795** |

- A2 chose the best of the 12 designs on development data on all three projects, testing only 4.
- Against B1, A2 met the preregistered success rule on P1 and P2 (intent +2.2 and +4.9 points, entity +7.3 and
  +5.5). On P3 intent fell 1.3 points (95% CI [−3.8, +1.4], not significant) and entity rose 14.6 points.
- Live check: asked again with the cache off, A2 reproduced 50 of 50 recorded test answers.

Full numbers: `reports/final_test.json`, `reports/EVIDENCE_SUMMARY.md`. Findings with caveats: `docs/FINDINGS.md`.

## Quick start

```bash
python -m pip install -e ".[dev]"
python -m pytest tests                     # 371 checks, no model needed
ollama pull qwen2.5:3b                     # the runtime model (digest 357c53fb659c)
python scripts/show_evidence.py            # runs every check and the live demo
python scripts/demo.py --project P1 --interactive
```

Reproducing the experiments step by step: `docs/REPRODUCTION.md`.

## Where things are

| Path | Contents |
|---|---|
| `paper/` | IEEE paper (`main.tex`, `references.bib`, figures, compiled PDF), `Research_Paper_Explained.pdf` |
| `src/analyzer/` | Specification checks, enrichment, the data-access lock that withholds test data |
| `src/architect/` | A1 (`architect.py`) and A2 (`architect_v2.py`) agents, design runs |
| `src/pipelines/` | The fixed 12-design catalogue and example selection |
| `src/evaluation/` | Scorer, span-location rule, selection rule, threshold tuning, run folders |
| `src/baselines/` | B0 TF-IDF, B3 XLM-R, B4 random search |
| `src/runtime/` | Package export and verified loading |
| `src/llm/` | Model client, prediction cache, call counters |
| `artifacts/` | Exported pipeline packages (A1 and A2 for P1 and P2) |
| `runs/<run_id>/` | One folder per experiment run: config, manifest, metrics, predictions |
| `reports/` | Final results, evidence summary, figures, guides for presenting (`reports/guide/`) |
| `docs/` | Plan, frozen protocol, decisions log, findings, data report, reproduction log, contributions |
| `data/manifests/` | Frozen splits with SHA-256 hashes |

## Rules this code enforces, rather than only documenting

- Test data and the held-out project are released only by naming the freeze commit.
- The agent chooses only from the fixed catalogue; a made-up design is discarded, never run.
- The four-evaluation budget is enforced by code, not by the model.
- The same selection rule is used by the agent and by random search.
- Every LM system uses the same scorer and the same exact-match span rule.
- A cache entry is keyed by the full prompt, model digest and settings; cached replies never give a latency figure.
- Every run folder records the git commit, model digest and data hashes.
- Exported packages are hash-verified on load and refuse a different model.

Data: MASSIVE 1.1 (FitzGerald et al., ACL 2023), CC BY 4.0. AI assistance is recorded in `docs/contributions.md`.
