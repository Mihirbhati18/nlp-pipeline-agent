"""The NLP Architect (PROJECT_PLAN.md section 6).

    The Architect reads the ProjectSpec and chooses which catalogue
    configurations to evaluate. It does not need unrestricted generated Python
    code.

    Search budget: 4 candidate evaluations per project (3 initial + 1 revision
    chosen after reading the development error report). Save every attempted
    configuration, its rationale and its failures. If the budget is exhausted
    or no candidate meets hard constraints, return that outcome explicitly.

This is the component B4 exists to beat. B4 draws its 4 configurations at
random; the Architect reasons about which to try. Both then evaluate on the
same development cases and select with the **same** shared rule, so a
difference between them is attributable to the choice of candidates and
nothing else.

What the Architect may and may not do:

- It may choose only configurations that exist in the fixed catalogue. A
  proposal naming anything else is rejected, recorded, and replaced by a
  deterministic fallback, so a hallucinated configuration can never be run.
- It may not exceed the budget. The cap is enforced by this module, not by the
  model's cooperation.
- It may not see test data: it receives a ``DataAccess`` handle, which refuses.
- Its revision step sees a development **error report**, not raw gold labels
  beyond the development split it is already allowed.

Honesty about what the model contributes: if the model is unavailable or its
proposals are unusable, the Architect falls back to a fixed, documented
ordering of the catalogue. Every run records whether the choice was reasoned
or fallback, so a result cannot silently be attributed to reasoning that did
not happen.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from ..analyzer.spec import ProjectSpec
from ..evaluation.selection import Candidate, SelectionResult, select
from ..llm.client import LLMClient
from ..pipelines.catalogue import CATALOGUE, CATALOGUE_BY_ID, Config

INITIAL_BUDGET = 3
REVISION_BUDGET = 1
TOTAL_BUDGET = INITIAL_BUDGET + REVISION_BUDGET

# Used when the model is absent or its proposal is unusable. Chosen to span the
# three extraction strategies rather than to be good, so the fallback is a
# neutral spread and not a tuned guess.
FALLBACK_ORDER = (
    "joint-fixed-llm",
    "twostage-sim-llm",
    "schema-sim-tfidf",
    "joint-sim-llm",
    "schema-fixed-llm",
    "twostage-fixed-tfidf",
)

FACTOR_GUIDE = """Each configuration combines three choices:

extraction:
- joint: one call returns the intent and the information together. Fewest calls.
- two_stage: one call for the intent, then one for that intent's fields only.
  Twice the calls, but the second prompt is narrower.
- schema_guided: one call, and the prompt includes a written description of
  every intent and every field. Helps when a field has no example to copy.

example_selection:
- fixed: the same one example per intent every time. Covers every intent, but
  ignores the request.
- similarity: the examples most similar to the request. Closer examples, but
  some intents may get none.

oos_policy:
- llm_label: the model may answer none_of_the_above.
- tfidf_threshold: a similarity threshold rejects a request before any model
  call. Cheaper, but the model is then never offered a way to reject."""


@dataclass
class Attempt:
    """One candidate the Architect tried."""

    config_id: str
    rationale: str
    source: str  # "reasoned" or "fallback"
    stage: str  # "initial" or "revision"
    metrics: dict[str, Any] | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        primary = (self.metrics or {}).get("primary", {})
        return {
            "config_id": self.config_id,
            "rationale": self.rationale,
            "source": self.source,
            "stage": self.stage,
            "intent_macro_f1": primary.get("intent_macro_f1"),
            "entity_span_f1": primary.get("entity_span_f1"),
            "schema_validity": primary.get("schema_validity_after_repair"),
            "runtime_failure_rate": primary.get("runtime_failure_rate"),
            "error": self.error,
        }


@dataclass
class DesignResult:
    project_id: str
    attempts: list[Attempt]
    selection: SelectionResult
    findings: list[str] = field(default_factory=list)
    logical_calls: int = 0
    physical_calls: int = 0
    planning_calls: int = 0
    events: list[dict] = field(default_factory=list)

    @property
    def budget_used(self) -> int:
        return len(self.attempts)

    @property
    def reasoned_choices(self) -> int:
        return sum(1 for a in self.attempts if a.source == "reasoned")

    def as_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "budget": TOTAL_BUDGET,
            "budget_used": self.budget_used,
            "reasoned_choices": self.reasoned_choices,
            "fallback_choices": self.budget_used - self.reasoned_choices,
            "attempts": [a.as_dict() for a in self.attempts],
            "selection": self.selection.as_dict(),
            "findings": self.findings,
            "design_cost": {
                "logical_calls": self.logical_calls,
                "physical_calls": self.physical_calls,
                "planning_calls": self.planning_calls,
            },
        }


# -- prompts -----------------------------------------------------------

INITIAL_PROMPT = """You are choosing which pipeline configurations to try for a
language-understanding project. You have a budget of {n} to try first.

Project: {name}
{description}

It must recognise {n_intents} request types and extract {n_entities} kinds of
information. {coverage_note}

{guide}

Available configuration ids:
{catalogue}

Choose exactly {n} different ids that are worth trying first, and say briefly
why each suits this project. Reply with JSON only:
{{"choices": [{{"config_id": "<id>", "why": "<one sentence>"}}]}}"""

REVISION_PROMPT = """You are choosing one more pipeline configuration to try,
after seeing how the first ones scored.

Project: {name}
It must recognise {n_intents} request types and extract {n_entities} kinds of
information. {coverage_note}

{guide}

What you already tried, and how it went on development data:
{report}

Available configuration ids you have NOT tried:
{remaining}

Choose exactly one id that the results above suggest is worth trying, and say
why. Reply with JSON only:
{{"choices": [{{"config_id": "<id>", "why": "<one sentence>"}}]}}"""


def coverage_note(spec: ProjectSpec, pool: Sequence[dict]) -> str:
    """One factual sentence about field coverage in the example pool.

    This is the kind of project-specific fact the Analyzer's specification
    makes available, and it is exactly what a plain random search cannot use.
    Derived from the k-shot pool only.
    """
    shown = {e["type"] for case in pool for e in case["entities"]}
    declared = set(spec.entity_type_names)
    missing = sorted(declared - shown)
    if not missing:
        return "Every kind of information has at least one example in the pool."
    return (
        f"{len(missing)} of {len(declared)} kinds of information have no example "
        f"in the pool at all ({', '.join(missing[:6])}"
        f"{', ...' if len(missing) > 6 else ''}), so for those the model has only "
        "the written description to go on."
    )


def error_report(attempts: Sequence[Attempt]) -> str:
    """A compact development error report for the revision step."""
    lines: list[str] = []
    for attempt in attempts:
        if attempt.error:
            lines.append(f"- {attempt.config_id}: failed to run ({attempt.error})")
            continue
        primary = (attempt.metrics or {}).get("primary", {})

        def show(value, digits=3):
            return "n/a" if value is None else f"{value:.{digits}f}"

        lines.append(
            f"- {attempt.config_id}: intent macro-F1 {show(primary.get('intent_macro_f1'))}, "
            f"information F1 {show(primary.get('entity_span_f1'))}, "
            f"valid replies {show(primary.get('schema_validity_after_repair'))}, "
            f"wrongly rejected {show(primary.get('false_rejection_rate_in_scope'))}, "
            f"invented values {primary.get('unsupported_extraction_rate')}"
        )
    return "\n".join(lines) or "- nothing ran"


# -- the Architect -----------------------------------------------------


@dataclass
class Architect:
    """Chooses catalogue configurations within a hard budget."""

    client: LLMClient | None = None
    catalogue: Sequence[Config] = field(default_factory=lambda: list(CATALOGUE))

    # -- proposing -----------------------------------------------------

    def _ask(self, prompt: str, allowed: Sequence[str], n: int) -> tuple[list[tuple[str, str]], list[str], int]:
        """One planning call. Returns (choices, findings, physical_calls).

        Proposals are filtered to ``allowed``; anything else is discarded and
        reported, so a hallucinated configuration can never be run.
        """
        findings: list[str] = []
        if self.client is None:
            return [], ["no planning model available; fallback ordering used"], 0

        record = self.client.generate(prompt)
        physical = 0 if record.cache_hit else 1
        if record.error:
            return [], [f"planning call failed: {record.error}"], physical

        text = record.text.strip()
        if text.startswith("```"):
            text = text.strip("`")
            text = text[4:] if text.lower().startswith("json") else text
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            return [], [f"planning reply was not JSON: {exc.msg}"], physical

        raw = payload.get("choices") if isinstance(payload, dict) else None
        if not isinstance(raw, list):
            return [], ["planning reply had no choices list"], physical

        allowed_set = set(allowed)
        chosen: list[tuple[str, str]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            config_id = item.get("config_id")
            why = item.get("why", "")
            if not isinstance(config_id, str):
                continue
            if config_id not in allowed_set:
                findings.append(
                    f"proposed {config_id!r}, which is not an available configuration; discarded"
                )
                continue
            if any(config_id == existing for existing, _ in chosen):
                findings.append(f"proposed {config_id!r} twice; the duplicate was discarded")
                continue
            chosen.append((config_id, " ".join(str(why).split()) or "no reason given"))

        if len(chosen) > n:
            findings.append(f"proposed {len(chosen)} configurations for a budget of {n}; extras discarded")
            chosen = chosen[:n]

        return chosen, findings, 1 if self.client else 0

    def _fill_from_fallback(
        self, chosen: list[tuple[str, str]], n: int, exclude: set[str]
    ) -> list[tuple[str, str, str]]:
        """Top up to ``n`` with the documented fallback order."""
        out = [(cid, why, "reasoned") for cid, why in chosen]
        taken = {cid for cid, _, _ in out} | exclude
        for config_id in FALLBACK_ORDER:
            if len(out) >= n:
                break
            if config_id in taken or config_id not in CATALOGUE_BY_ID:
                continue
            out.append((config_id, "fallback ordering: no usable proposal", "fallback"))
            taken.add(config_id)
        # Still short? Take any remaining catalogue entry, in catalogue order.
        for config in self.catalogue:
            if len(out) >= n:
                break
            if config.config_id in taken:
                continue
            out.append((config.config_id, "fallback ordering: catalogue order", "fallback"))
            taken.add(config.config_id)
        return out[:n]

    # -- the design run ------------------------------------------------

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
        """Run one design: propose, evaluate, revise, select.

        ``evaluate_config`` returns ``(metrics, logical_calls, physical_calls)``
        for one configuration on development data. Injecting it keeps the
        Architect free of I/O and makes it testable without a model.
        """
        note = coverage_note(spec, pool)
        catalogue_ids = [c.config_id for c in self.catalogue]
        attempts: list[Attempt] = []
        findings: list[str] = []
        events: list[dict] = []
        logical = physical = planning = 0

        # -- stage one: three initial candidates ------------------------
        proposed, ask_findings, used = self._ask(
            INITIAL_PROMPT.format(
                n=INITIAL_BUDGET,
                name=spec.name,
                description=spec.description_text.strip()[:1200],
                n_intents=len(spec.intents),
                n_entities=len(spec.entity_types),
                coverage_note=note,
                guide=FACTOR_GUIDE,
                catalogue="\n".join(f"- {cid}" for cid in catalogue_ids),
            ),
            catalogue_ids,
            INITIAL_BUDGET,
        )
        findings.extend(ask_findings)
        planning += used
        physical += used

        initial = self._fill_from_fallback(proposed, INITIAL_BUDGET, set())
        for config_id, why, source in initial:
            config = CATALOGUE_BY_ID[config_id]
            attempt = Attempt(config_id=config_id, rationale=why, source=source, stage="initial")
            try:
                metrics, lc, pc = evaluate_config(config)
                attempt.metrics = metrics
                logical += lc
                physical += pc
            except Exception as exc:  # noqa: BLE001
                attempt.error = f"{type(exc).__name__}: {exc}"
            attempts.append(attempt)
            events.append({"kind": "candidate_attempt", **attempt.as_dict()})

        # -- stage two: one revision, after reading the error report ----
        tried = {a.config_id for a in attempts}
        remaining = [cid for cid in catalogue_ids if cid not in tried]
        if remaining:
            revised, revise_findings, used = self._ask(
                REVISION_PROMPT.format(
                    name=spec.name,
                    n_intents=len(spec.intents),
                    n_entities=len(spec.entity_types),
                    coverage_note=note,
                    guide=FACTOR_GUIDE,
                    report=error_report(attempts),
                    remaining="\n".join(f"- {cid}" for cid in remaining),
                ),
                remaining,
                REVISION_BUDGET,
            )
            findings.extend(revise_findings)
            planning += used
            physical += used

            revision = self._fill_from_fallback(revised, REVISION_BUDGET, tried)
            for config_id, why, source in revision:
                config = CATALOGUE_BY_ID[config_id]
                attempt = Attempt(
                    config_id=config_id, rationale=why, source=source, stage="revision"
                )
                try:
                    metrics, lc, pc = evaluate_config(config)
                    attempt.metrics = metrics
                    logical += lc
                    physical += pc
                except Exception as exc:  # noqa: BLE001
                    attempt.error = f"{type(exc).__name__}: {exc}"
                attempts.append(attempt)
                events.append({"kind": "candidate_attempt", **attempt.as_dict()})
        else:
            findings.append("no untried configuration remained for the revision step")

        # The budget is enforced here, not by the model's cooperation.
        if len(attempts) > TOTAL_BUDGET:
            raise AssertionError(
                f"budget violated: {len(attempts)} evaluations against a cap of {TOTAL_BUDGET}"
            )

        # -- selection, by the same rule B4 uses ------------------------
        candidates = [
            Candidate(
                config_id=a.config_id,
                metrics=a.metrics or {},
                rationale=a.rationale,
                estimated_p95_s=(
                    estimate_p95(CATALOGUE_BY_ID[a.config_id]) if estimate_p95 else None
                ),
            )
            for a in attempts
            if a.error is None
        ]
        selection = select(
            candidates,
            min_entity_f1=min_entity_f1,
            max_p95_latency_s=max_p95_latency_s,
            min_schema_validity=min_schema_validity,
        )
        events.append({"kind": "selection_decision", **selection.as_dict()})

        if selection.no_eligible_candidate:
            findings.append(
                "no candidate met the declared hard constraints within the budget; "
                "reported as an explicit no-eligible-candidate outcome"
            )

        return DesignResult(
            project_id=spec.project_id,
            attempts=attempts,
            selection=selection,
            findings=findings,
            logical_calls=logical,
            physical_calls=physical,
            planning_calls=planning,
            events=events,
        )
