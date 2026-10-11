# G2 data report

Date: 11 October 2026. Produced by `python scripts/prepare_data.py`, verified by
`python -m pytest tests -q`.

## Source audit

| Field | Value |
|---|---|
| Dataset | MASSIVE, version 1.1 (released 2022-11-16) |
| Language used | en-US only |
| Licence | CC BY 4.0 (Attribution 4.0 International); derived from SLURP, also CC BY 4.0 |
| Attribution | Required. Cite FitzGerald et al., ACL 2023, and the SLURP paper |
| Archive SHA-256 | `4cba5faa11c71437928e17cb1b9b3d8b8e727e7ea363a3a9a8045e19c0491577` |
| Records (en-US) | 16,521 |
| Official partitions | train 11,514 / dev 2,033 / test 2,974 |
| Scenarios (domains) | 18 |
| Intents | 60 |
| Slot types | 55 |
| Annotation format | Inline `[slot_type : value]` spans in `annot_utt` |

The 18/60/55 counts match the published paper, so the local copy is the
expected release.

## Span conversion integrity

Every one of the 16,521 en-US records was converted from `annot_utt` into
character spans over `utt`. **16,521 succeeded, 0 mismatched.** The converter
raises rather than guessing if the annotation's plain text does not reconstruct
the utterance exactly, and it re-checks every offset against the utterance
after conversion, so a misaligned span cannot enter gold data.

Covered by `tests/test_massive.py`, including the awkward cases: a slot at
position 0, a slot at the end of the string, the same value appearing twice in
one utterance, adjacent slots, and a deliberately inconsistent annotation.

## Projects

Groupings were confirmed from domain semantics and split counts before any
score was computed, as plan section 4 requires.

| Project | Role | Domains | Intents | Entity types | k-shot | Dev | Test |
|---|---|---|---|---|---|---|---|
| P1 Home assistant | development | alarm, iot | 12 | 18 | 120 | 100 (80 + 20 OOS) | 300 (250 + 50 OOS) |
| P2 Productivity assistant | development | calendar, email, lists | 10 | 26 | 100 | 100 (80 + 20 OOS) | 300 (250 + 50 OOS) |
| P3 Ordering and travel | **held out** | takeaway, transport | 6 | 19 | 60 | 100 (80 + 20 OOS) | **200 (167 + 33 OOS)** |

Out-of-scope pool (used by no project): audio, cooking, datetime, general,
music, news, play, qa, recommendation, social, weather. Out-of-scope cases are
sampled disjointly across projects, so no utterance serves as out-of-scope
evidence for more than one project.

Every intent has exactly k = 10 training examples; no project was short.
Entity schemas are derived from each project's **train** split only, so the
declared schema never depends on an evaluation case.

Sampling is seeded per project (`20261011|<project>`) and verified
reproducible: a rerun produces byte-identical files and hashes.

## Deviations from the plan, and why

**P3's test set is 200 cases, not 300.** The official en-US test split holds
only 181 in-scope cases for takeaway and transport, short of the 250 the
standard size requires. Plan section 4 already names 200 as the test fallback,
so P3 uses it: 167 in-scope + 33 out-of-scope. The decision came from split
counts alone, before any prediction and without inspecting P3 content, and
P1/P2 keep the full 300. Consequence: P3's confidence intervals will be wider
than P1's and P2's, and the comparison is per-project anyway.

## Known data limitations to report in the paper

1. **Thin per-intent support.** `iot_hue_lighton` has only 3 cases in P1's
   test set, and five intents across P1 and P2 have 5 development cases. Intent
   macro-F1 weights every intent equally, so these classes add real variance to
   P1's headline number. Per-intent support is recorded in each manifest and
   must be shown alongside macro-F1, not hidden behind it.
2. **Two declared near-duplicate overlaps.** The k-shot pool shares an
   utterance with an evaluation case in two places, both recorded by case ID:
   - P2: k-shot `massive-17118` and test `massive-16002`, both "check for new email" (1 of 250 in-scope test cases)
   - P3: k-shot `massive-57` and dev `massive-58`, both "find my thai takeaways around grassmarket" (1 of 80 in-scope dev cases)
   No case ID is shared across splits, and nothing was resampled to hide these:
   removing them would have required choosing training examples using knowledge
   of the test inputs. They are named here so a sensitivity check can exclude
   them if either result turns out to be close.
3. **A few gold entities fall outside the declared schema**, because the schema
   comes from the train split: P1 has 2 `person` and 1 `media_type`, and P3 has
   1 `ingredient`. These are unextractable by design and count as recall errors.
   This is realistic — a developer's declared schema is rarely exhaustive — but
   it puts a small ceiling on entity recall that applies equally to every system.
4. **Pretraining familiarity.** MASSIVE is public and predates the runtime
   model, so the model may have seen it. A locally hidden test file does not
   remove that. This is a limitation for every LLM system here, including the
   baselines.

## Entity types the k-shot pool never demonstrates (found at G6)

Each project's entity schema is derived from its **full** train split, but the
prompt pool holds only k = 10 examples per intent. So a declared entity type can
be absent from every example the model ever sees.

| Project | Schema types | Shown in the k-shot pool | Needed in dev gold but never shown | Share of dev gold entities affected |
|---|---|---|---|---|
| P1 | 18 | 11 | 0 | 0% |
| **P2** | 26 | 10 | **5** (`email_folder`, `meal_type`, `media_type`, `place_name`, `timeofday`) | **10.7%** (8 of 75) |
| P3 | 19 | 11 | 0 | 0% |

**Why this matters.** For about 11% of P2's development entities, no system has
an in-prompt example to copy: the entity must be recognised from the declared
schema and the project description alone. P1 and P3 are unaffected, so this is a
property of P2's larger schema (26 types against P1's 18) meeting the same
10-examples-per-intent budget.

**A prediction this makes, which the experiment can falsify.** The
schema-guided catalogue configurations carry field descriptions into the
prompt, and the Analyzer's enrichment supplies those descriptions. If
description-based enrichment helps anywhere, it should help P2's entity recall
more than P1's. If P2 shows no such advantage, that is evidence against the
enrichment contributing, and should be reported as such.

This also puts a floor under how well any few-shot system can do on P2 entity
recall, and it applies equally to every LLM system, so it does not favour one.

## Access rule in force

| Path | Who may use it, and for what |
|---|---|
| `data/processed/<P>/kshot.jsonl` | Model fitting and few-shot example selection |
| `data/processed/<P>/dev.jsonl` | Prompts, candidates, thresholds, hyperparameters |
| `data/processed/<P>/holdout/test.jsonl` | Opened only after the G10 freeze |
| Anything under `data/processed/P3/` | Not touched before the freeze at all; only `configs/descriptions/P3.md` was written |
