# Decisions

Every protocol-relevant decision, with its date and reason. A decision that
changes after a run is logged as a new row; earlier rows are never edited away.

| # | Date | Decision | Reason |
|---|---|---|---|
| 1 | 11 Oct 2026 | Implementation repository is `D:/MyClaudeProject/nlp`, initialised with git on 11 Oct. `docs/PROJECT_PLAN.md` (moved from `PROJECT_PLAN_v1.2.md`) is the authoritative plan copy; `docs/Project_Plan_v1.2.pdf` is a frozen rendering and is not edited. | Plan section 2 requires one authoritative copy and forbids two independently edited trackers. |
| 2 | 11 Oct 2026 | `PROGRESS_TRACKER.md` and `EVIDENCE_LOG.md` were created new, directly at v1.2 gate and screenshot numbers. | No v1.0-numbered tracker existed, so the section 9 renumbering map had nothing to migrate. Noted here because section 9 asks for the change to be recorded. |
| 3 | 11 Oct 2026 | `D:/study/nlp/assignment 2.pdf` is **not** the DA2 rubric: page 1 is a CAT-2 skip-gram negative-sampling problem set. The DA2 rubric remains unavailable and must come from the teacher. | Plan section 12 asks whether another handout exists. Checked, answered: no. |
| 4 | 11 Oct 2026 | `torch` and `transformers` are excluded from the laptop dependency list; B3 fine-tuning runs only in the Kaggle notebook. | Keeps the laptop environment small; plan section 2 already assigns B3 training to Kaggle's free GPU. |
| 5 | 11 Oct 2026 | Failed model calls are recorded with their error but **never written to the prediction cache**. | A cached failure would silently become a prediction on a later run. Failures still stay in every metric denominator (plan section 5). |
| 6 | 11 Oct 2026 | Cache hits return `latency_s = None` rather than a stored duration. | Enforces the section 2A rule (cached output scores, never times) in code rather than by convention. |
| 7 | 11 Oct 2026 | The G0 throughput prompts are hand-written MASSIVE-style stand-ins. At the 16-example cap they reach about 920 estimated input tokens, not the full 2,000. | The example cap binds before the token cap for a 12-intent project. Real P2 (calendar, email, lists) has a longer schema, so its prompts will be larger and slower. The G0 time estimate is therefore optimistic and must be re-checked at G4 with real prompts. |
| 8 | 11 Oct 2026 | DA1 and DA2 are confirmed submitted and accepted, so the plan's 11-20 Oct schedule stands unchanged and only DA3 is outstanding. | Plan section 11 makes this the first action, because an owed DA2 would have reprioritised everything. |
| 9 | 11 Oct 2026 | MASSIVE 1.1 en-US is the data source, licence CC BY 4.0, archive SHA-256 `4cba5faa...1577`. Project groupings P1 (alarm, iot), P2 (calendar, email, lists), P3 (takeaway, transport) confirmed from domain semantics and split counts. | Plan section 4 requires the grouping be confirmed at G2 before any score. |
| 10 | 11 Oct 2026 | **P3's test set is 200 cases (167 in-scope + 33 OOS), not 300.** Its official test split holds only 181 in-scope cases for takeaway and transport. | Plan section 4 names 200 as the documented fallback. Decided from split counts alone, before any prediction and without inspecting P3 content. P1 and P2 keep 300. |
| 11 | 11 Oct 2026 | Entity schemas are derived from each project's **train** split only, not from all its data. | A developer declares a schema without having seen the evaluation cases. Consequence: 3 gold entities in P1 and 1 in P3 fall outside the declared schema and count as recall errors for every system equally. |
| 12 | 11 Oct 2026 | The two near-duplicate k-shot/evaluation overlaps were **declared by case ID, not resampled away**. | Resampling training examples to avoid matching test inputs would use knowledge of the test set. Both are recorded in `DATA_REPORT.md` so a sensitivity check can exclude them. |
| 13 | 11 Oct 2026 | Out-of-scope cases are sampled disjointly across the three projects. | The plan forbids drawing out-of-scope cases from another project's domains; disjoint sampling additionally stops one utterance serving as evidence for two projects. |
| 14 | 11 Oct 2026 | The catalogue's TF-IDF out-of-scope policy rejects a request **before** any model call, so a rejected case costs zero calls. | It is the honest reading of a similarity-threshold policy, and it makes the efficiency difference between the two out-of-scope policies measurable. Threshold rejections are excluded from latency figures and flagged in `timing.jsonl`, so they cannot flatter a configuration's latency. |
| 15 | 11 Oct 2026 | Two threshold-tuning rules, both development-only: B0 and B3 maximise macro-F1 over intents plus the out-of-scope class; the catalogue's TF-IDF policy maximises F1 on the binary in-scope/out-of-scope decision. | The catalogue policy decides before the model call, so no intent prediction exists at tuning time and the macro-F1 rule cannot be applied. Both rules break ties toward the lower threshold, which rejects fewer in-scope requests. |
| 16 | 11 Oct 2026 | Intent and entity *descriptions* are absent from the bare `ProjectSpec` and are added only by the Analyzer (G6) or by hand for B2. Names come from the manifest and the Analyzer may never change them. | Authoritative supplied fields take precedence over inferred ones (plan section 6), and it makes the no-Analyzer ablation a real comparison: the ablation runs on the bare specification, A1 on the enriched one. |
| 17 | 11 Oct 2026 | B0 is trained on the same k = 10 per intent pool as every LLM system, and extracts no entities. | Matches the data regime so the comparison is fair; B0 is an intent classifier, so its entity F1 is 0 by design rather than by failure. Reported plainly. |

## Open decisions

| # | Question | Decide by |
|---|---|---|
| A | Runtime model (3B vs 7-8B class) | End of G0, by the section 2A rule, from measured numbers only |
| B | Confirm or adjust `delta_I`, `epsilon_E`, `S_min`, `L_max` in `protocol.md` | 16 Oct, before any test access |
| C | Free-API provider for the Architect's planning calls (Gemini or Groq) | Before G7 |
| D | Whether the 18 Oct buffer day exists | Depends on the confirmed DA3 cutoff |
