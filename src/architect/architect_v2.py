"""The improved NLP Architect used by A2 (decision 42).

A1's Architect asks the planning model to pick 3 of 12 configuration ids at
once. The development analysis (FINDINGS F1, F5) showed where that fails: the
model reasons about extraction style and call cost and never tries the other
example-selection option, so the best region of the catalogue goes unexplored,
and its documented fallback order beat it on P2.

A2 changes *how* the model is asked, not what the catalogue holds:

1. **Factor-wise reasoning.** One planning call ranks the options of each of
   the three factors separately (extraction, example selection, out-of-scope
   policy), each ranking with its own reason.
2. **Structured initial candidates.** From those rankings, three candidates
   are built so that every factor's top choice is tried and each of the first
   two factors is varied once from it:
   ``(e1, s1, o1)``, ``(e1, s2, o1)``, ``(e2, s1, o1)``.
   This is a one-factor-at-a-time design: whatever the model prefers, the
   alternative example selection and the runner-up extraction are both
   measured. No configuration is hard-coded from development results.
3. **A one-step revision.** After the first three are scored, the model sees
   the error report and chooses one factor to change from the best candidate
   so far; only untried configurations one factor away are allowed.

Everything else is A1's contract: catalogue-only choices, a hard budget of
3 + 1 enforced here, reasoned and fallback choices counted separately, and
selection by the same shared rule B4 uses. A1's module is not modified.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from ..analyzer.spec import ProjectSpec
from ..evaluation.selection import Candidate, select
from ..llm.client import LLMClient
from ..pipelines.catalogue import CATALOGUE, CATALOGUE_BY_ID, Config
from .architect import (
    FACTOR_GUIDE,
    INITIAL_BUDGET,
    REVISION_BUDGET,
    TOTAL_BUDGET,
    Attempt,
    DesignResult,
    coverage_note,
    error_report,
)

FACTORS = ("extraction", "example_selection", "oos_policy")
OPTIONS = {
    "extraction": ("joint", "two_stage", "schema_guided"),
    "example_selection": ("fixed", "similarity"),
    "oos_policy": ("llm_label", "tfidf_threshold"),
}
# Used for a factor whose ranking is missing or malformed: the options in
# their declared order, so the fallback is neutral rather than a tuned guess.
DEFAULT_RANKING = {name: list(options) for name, options in OPTIONS.items()}

FACTOR_PROMPT = """You are designing a language-understanding pipeline for one
project. Decide each design choice separately, for this project.

Project: {name}
{description}

It must recognise {n_intents} request types and extract {n_entities} kinds of
information. {coverage_note}

{guide}

For EACH of the three choices, rank ALL of its options from most to least
suitable for this project, and give one sentence of reasoning per choice.
Reply with JSON only, using exactly these option names:
{{"extraction": {{"ranking": ["joint", "two_stage", "schema_guided"], "why": "<one sentence>"}},
 "example_selection": {{"ranking": ["fixed", "similarity"], "why": "<one sentence>"}},
 "oos_policy": {{"ranking": ["llm_label", "tfidf_threshold"], "why": "<one sentence>"}}}}"""

REVISION_PROMPT_V2 = """You have tried these pipeline configurations on
development data for one project:

Project: {name}
It must recognise {n_intents} request types and extract {n_entities} kinds of
information. {coverage_note}

{guide}

Results so far:
{report}

The best so far is {best} ({best_factors}).
You may try ONE more configuration, and it must change exactly ONE choice from
the best. These are the untried options:
{moves}

Pick the change the results above suggest is most promising, and say why.
Reply with JSON only:
{{"change": "<one of: {move_names}>", "why": "<one sentence>"}}"""


def find_config(extraction: str, example_selection: str, oos_policy: str) -> Config:
    for config in CATALOGUE:
        if (config.extraction, config.example_selection, config.oos_policy) == (
            extraction, example_selection, oos_policy
        ):
            return config
    raise KeyError((extraction, example_selection, oos_policy))


def factors_of(config: Config) -> dict[str, str]:
    return {"extraction": config.extraction, "example_selection": config.example_selection,
            "oos_policy": config.oos_policy}


def neighbours(config: Config, exclude: set[str]) -> dict[str, Config]:
    """Untried configurations that differ from ``config`` in exactly one factor."""
    base = factors_of(config)
    out: dict[str, Config] = {}
    for factor in FACTORS:
        for option in OPTIONS[factor]:
            if option == base[factor]:
                continue
            candidate = find_config(**{**base, factor: option})
            if candidate.config_id not in exclude:
                out[f"{factor}={option}"] = candidate
    return out


def _parse_json(text: str) -> Any:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[4:] if text.lower().startswith("json") else text
    return json.loads(text)


@dataclass
class ArchitectV2:
    """Factor-wise reasoning plus a one-factor revision, within a hard budget."""

    client: LLMClient | None = None

    def _call(self, prompt: str) -> tuple[Any, str | None, int]:
        """One planning call: (payload or None, problem or None, physical calls)."""
        if self.client is None:
            return None, "no planning model available; neutral factor order used", 0
        record = self.client.generate(prompt)
        physical = 0 if record.cache_hit else 1
        if record.error:
            return None, f"planning call failed: {record.error}", physical
        try:
            return _parse_json(record.text), None, physical
        except json.JSONDecodeError as exc:
            return None, f"planning reply was not JSON: {exc.msg}", physical

    def rank_factors(self, payload: Any) -> tuple[dict[str, list[str]], dict[str, str], list[str], set[str]]:
        """Validate the model's rankings. Returns rankings, reasons, findings, reasoned factors."""
        rankings, reasons, findings, reasoned = {}, {}, [], set()
        for factor in FACTORS:
            entry = payload.get(factor) if isinstance(payload, dict) else None
            ranking = entry.get("ranking") if isinstance(entry, dict) else None
            if (isinstance(ranking, list) and sorted(map(str, ranking)) == sorted(OPTIONS[factor])):
                rankings[factor] = [str(r) for r in ranking]
                reasons[factor] = " ".join(str(entry.get("why", "")).split()) or "no reason given"
                reasoned.add(factor)
            else:
                rankings[factor] = list(DEFAULT_RANKING[factor])
                reasons[factor] = "neutral order: no usable ranking"
                if payload is not None:
                    findings.append(f"ranking for {factor} was missing or malformed; neutral order used")
        return rankings, reasons, findings, reasoned

    def design(
        self,
        spec: ProjectSpec,
        pool: Sequence[dict],
        evaluate_config: Callable[[Config], tuple[dict[str, Any], int, int]],
        *,
        min_entity_f1: float | None = None,
        max_p95_latency_s: float | None = None,
        min_schema_validity: float | None = None,
        estimate_p95: Callable[[Config], float | None] | None = None,
    ) -> DesignResult:
        note = coverage_note(spec, pool)
        attempts: list[Attempt] = []
        findings: list[str] = []
        events: list[dict] = []
        logical = physical = planning = 0

        def run(config: Config, rationale: str, source: str, stage: str) -> None:
            nonlocal logical, physical
            attempt = Attempt(config_id=config.config_id, rationale=rationale, source=source, stage=stage)
            try:
                metrics, lc, pc = evaluate_config(config)
                attempt.metrics = metrics
                logical += lc
                physical += pc
            except Exception as exc:  # noqa: BLE001
                attempt.error = f"{type(exc).__name__}: {exc}"
            attempts.append(attempt)
            events.append({"kind": "candidate_attempt", **attempt.as_dict()})

        # -- stage one: factor-wise rankings -> three structured candidates --
        payload, problem, used = self._call(FACTOR_PROMPT.format(
            name=spec.name, description=spec.description_text.strip()[:1200],
            n_intents=len(spec.intents), n_entities=len(spec.entity_types),
            coverage_note=note, guide=FACTOR_GUIDE,
        ))
        if problem:
            findings.append(problem)
        planning += 1 if self.client else 0
        physical += used
        rankings, reasons, rank_findings, reasoned = self.rank_factors(payload)
        findings.extend(rank_findings)
        events.append({"kind": "factor_rankings", "rankings": rankings, "reasons": reasons,
                       "reasoned_factors": sorted(reasoned)})

        e, s, o = rankings["extraction"], rankings["example_selection"], rankings["oos_policy"]
        plan = [
            ((e[0], s[0], o[0]), "top choice on every factor", {"extraction", "example_selection", "oos_policy"}),
            ((e[0], s[1], o[0]), "top choices, other example selection", {"example_selection"}),
            ((e[1], s[0], o[0]), "top choices, runner-up extraction", {"extraction"}),
        ]
        for (ext, sel, oos), what, depends in plan[:INITIAL_BUDGET]:
            config = find_config(ext, sel, oos)
            # Every candidate uses all three rankings (its other factors sit on
            # their top choice), so it counts as reasoned only if the model
            # ranked all three. Reasoning is never credited on a neutral fallback.
            source = "reasoned" if reasoned == set(FACTORS) else "fallback"
            why = f"{what}: " + " | ".join(f"{f}: {reasons[f]}" for f in sorted(depends))
            run(config, why, source, "initial")

        # -- stage two: change exactly one factor from the best so far -------
        scored = [a for a in attempts if a.error is None and a.metrics]
        tried = {a.config_id for a in attempts}
        if scored:
            best = select([Candidate(config_id=a.config_id, metrics=a.metrics or {}) for a in scored]).selected
            best_config = CATALOGUE_BY_ID[best.config_id] if best else CATALOGUE_BY_ID[scored[0].config_id]
            moves = neighbours(best_config, tried)
            if moves:
                move_names = list(moves)
                reply, problem, used = self._call(REVISION_PROMPT_V2.format(
                    name=spec.name, n_intents=len(spec.intents), n_entities=len(spec.entity_types),
                    coverage_note=note, guide=FACTOR_GUIDE, report=error_report(attempts),
                    best=best_config.config_id,
                    best_factors=", ".join(f"{k}={v}" for k, v in factors_of(best_config).items()),
                    moves="\n".join(f"- {name} -> {cfg.config_id}" for name, cfg in moves.items()),
                    move_names=", ".join(move_names),
                ))
                if problem:
                    findings.append(problem)
                planning += 1 if self.client else 0
                physical += used
                change = reply.get("change") if isinstance(reply, dict) else None
                if isinstance(change, str) and change in moves:
                    why = " ".join(str(reply.get("why", "")).split()) or "no reason given"
                    run(moves[change], f"changed {change} from {best_config.config_id}: {why}",
                        "reasoned", "revision")
                else:
                    if reply is not None:
                        findings.append(f"revision proposed {change!r}, not an allowed one-factor change; "
                                        "the first untried factor in the fixed order was changed instead")
                    # Deterministic fallback: the first allowed move in factor order.
                    name = move_names[0]
                    run(moves[name], f"fallback: changed {name} from {best_config.config_id}",
                        "fallback", "revision")
            else:
                findings.append("no untried one-factor change remained for the revision step")
        else:
            findings.append("no initial candidate produced scores; revision skipped")

        if len(attempts) > TOTAL_BUDGET:
            raise AssertionError(f"budget violated: {len(attempts)} evaluations against a cap of {TOTAL_BUDGET}")
        assert REVISION_BUDGET == 1  # the revision above evaluates exactly one configuration

        candidates = [
            Candidate(
                config_id=a.config_id, metrics=a.metrics or {}, rationale=a.rationale,
                estimated_p95_s=(estimate_p95(CATALOGUE_BY_ID[a.config_id]) if estimate_p95 else None),
            )
            for a in attempts if a.error is None
        ]
        selection = select(candidates, min_entity_f1=min_entity_f1,
                           max_p95_latency_s=max_p95_latency_s, min_schema_validity=min_schema_validity)
        events.append({"kind": "selection_decision", **selection.as_dict()})
        if selection.no_eligible_candidate:
            findings.append("no candidate met the declared hard constraints within the budget; "
                            "reported as an explicit no-eligible-candidate outcome")

        return DesignResult(
            project_id=spec.project_id, attempts=attempts, selection=selection, findings=findings,
            logical_calls=logical, physical_calls=physical, planning_calls=planning, events=events,
        )
