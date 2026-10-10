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

## Open decisions

| # | Question | Decide by |
|---|---|---|
| A | Runtime model (3B vs 7-8B class) | End of G0, by the section 2A rule, from measured numbers only |
| B | Confirm or adjust `delta_I`, `epsilon_E`, `S_min`, `L_max` in `protocol.md` | 16 Oct, before any test access |
| C | Free-API provider for the Architect's planning calls (Gemini or Groq) | Before G7 |
| D | Whether the 18 Oct buffer day exists | Depends on the confirmed DA3 cutoff |
