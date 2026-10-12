"""G8: a full design run, from project description to a selected pipeline.

This is where the pieces built separately become the A1 system:

    frozen description + manifest
        -> Analyzer (validate, then enrich)            [G6]
        -> Architect (3 candidates, then 1 revision)   [G7]
        -> each candidate executed on development data [G4 catalogue]
        -> selection under the declared constraints    [shared rule]
        -> an exportable decision                      [G9 consumes this]

The same ``evaluate_config`` closure is handed to B4, so A1 and B4 evaluate
candidates by identical code on identical data and differ only in which
candidates they try. That is what makes the RQ5 comparison interpretable.

Two things this module is careful about:

- **Latency is never produced here.** Candidate evaluation uses the prediction
  cache, so it reports no latency at all. A declared latency constraint is
  filtered on a cheap a-priori estimate, and the selected pipeline's real p95
  is measured separately by an uncached timing run (plan section 2A).
- **Design cost is honest.** Logical calls (what the method would have made on
  its own) are summed separately from physical calls, so a candidate already
  evaluated for another system is not reported as free.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from ..analyzer.access import DataAccess
from ..analyzer.analyzer import AnalysisResult, Analyzer
from ..analyzer.spec import ProjectSpec
from ..evaluation.scorer import score
from ..evaluation.selection import select
from ..evaluation.thresholds import ThresholdChoice, tune_binary_threshold
from ..llm.client import LLMClient
from ..pipelines.catalogue import Config, ConfigRunner
from ..pipelines.examples import ExampleSelector
from .architect import Architect, DesignResult

# A two-stage configuration makes two calls per request, so its latency is
# roughly twice a single-call configuration's. Used only to filter a declared
# latency constraint before anything is timed; the real figure comes later.
def estimate_p95(config: Config, single_call_p95_s: float) -> float:
    return single_call_p95_s * config.calls_per_request


@dataclass
class CandidateEvaluation:
    config_id: str
    metrics: dict[str, Any]
    logical_calls: int
    physical_calls: int
    cache_hits: int
    seconds: float


@dataclass
class FullDesign:
    """Everything one design run produced, ready for a run folder and export."""

    project_id: str
    analysis: AnalysisResult
    design: DesignResult
    evaluations: list[CandidateEvaluation]
    oos_threshold: ThresholdChoice
    seconds: float
    data_access: dict[str, Any]

    @property
    def selected_config_id(self) -> str | None:
        selected = self.design.selection.selected
        return selected.config_id if selected else None

    @property
    def total_logical_calls(self) -> int:
        return self.analysis.logical_calls + self.design.logical_calls

    @property
    def total_physical_calls(self) -> int:
        return self.analysis.physical_calls + self.design.physical_calls

    def as_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "selected_config_id": self.selected_config_id,
            "no_eligible_candidate": self.design.selection.no_eligible_candidate,
            "analysis": self.analysis.as_dict(),
            "design": self.design.as_dict(),
            "oos_threshold": self.oos_threshold.as_dict(),
            "design_cost": {
                # Analyzer enrichment and Architect planning are design cost
                # too, not free overhead, so they are included here.
                "logical_calls": self.total_logical_calls,
                "physical_calls": self.total_physical_calls,
                "planning_calls": self.design.planning_calls,
                "analyzer_calls": self.analysis.logical_calls,
                "candidate_calls": self.design.logical_calls,
                "wall_time_s": round(self.seconds, 1),
            },
            "data_access": self.data_access,
            "evaluations": [
                {
                    "config_id": e.config_id,
                    "logical_calls": e.logical_calls,
                    "physical_calls": e.physical_calls,
                    "cache_hits": e.cache_hits,
                    "seconds": round(e.seconds, 1),
                }
                for e in self.evaluations
            ],
        }


def make_config_evaluator(
    spec: ProjectSpec,
    client: LLMClient,
    pool: Sequence[dict],
    dev_cases: Sequence[dict],
    oos_threshold: float,
    *,
    collect: list[CandidateEvaluation] | None = None,
    allow_repair: bool = True,
) -> Callable[[Config], tuple[dict[str, Any], int, int]]:
    """Build the closure that evaluates one configuration on development data.

    The *same* closure is given to the Architect and to B4, so neither can be
    evaluating under friendlier conditions than the other.
    """
    selector = ExampleSelector(list(pool))

    def evaluate(config: Config) -> tuple[dict[str, Any], int, int]:
        runner = ConfigRunner(
            config=config,
            spec=spec,
            client=client,
            selector=selector,
            oos_threshold=oos_threshold,
            allow_repair=allow_repair,
        )
        started = time.perf_counter()
        predictions = []
        logical = physical = hits = 0
        for case in dev_cases:
            outcome = runner.run_case(case)
            predictions.append(outcome.prediction)
            logical += outcome.logical_calls
            physical += outcome.physical_calls
            hits += outcome.cache_hits

        # No latency is passed: a cached evaluation cannot produce one.
        metrics = score(dev_cases, predictions, labels=spec.intent_names)
        elapsed = time.perf_counter() - started
        if collect is not None:
            collect.append(
                CandidateEvaluation(
                    config_id=config.config_id,
                    metrics=metrics,
                    logical_calls=logical,
                    physical_calls=physical,
                    cache_hits=hits,
                    seconds=elapsed,
                )
            )
        return metrics, logical, physical

    return evaluate


def run_design(
    spec: ProjectSpec,
    access: DataAccess,
    *,
    runtime_client: LLMClient,
    planning_client: LLMClient | None = None,
    load_cases: Callable[[str], list[dict]],
    min_entity_f1: float | None = None,
    max_p95_latency_s: float | None = None,
    min_schema_validity: float | None = None,
    single_call_p95_s: float | None = None,
    allow_repair: bool = True,
    enrich: bool = True,
) -> FullDesign:
    """Run the full A1 design for one project.

    ``enrich=False`` is the no-Analyzer ablation: the bare specification is
    used and no enrichment call is made.

    ``planning_client=None`` is the no-reasoning path: the Architect falls back
    to its documented ordering, and the record shows ``reasoned_choices: 0``.
    """
    started = time.perf_counter()

    # Only train and development paths are reachable; the guard refuses test.
    pool = load_cases(access.train_path)
    dev_cases = load_cases(access.dev_path)

    analysis = Analyzer(client=runtime_client if enrich else None).analyze(spec, pool)
    if not analysis.ok:
        # A contradiction in the inputs stops the design, by design.
        return FullDesign(
            project_id=spec.project_id,
            analysis=analysis,
            design=DesignResult(
                project_id=spec.project_id,
                attempts=[],
                selection=select([]),
                findings=["design not attempted: the project specification is contradictory"],
            ),
            evaluations=[],
            oos_threshold=ThresholdChoice(0.0, 0.0, 0, "not tuned: design not attempted"),
            seconds=time.perf_counter() - started,
            data_access=access.as_dict(),
        )

    selector = ExampleSelector(list(pool))
    threshold = tune_binary_threshold(
        [selector.max_similarity(c["utt"]) for c in dev_cases],
        [c["in_scope"] for c in dev_cases],
    )

    collected: list[CandidateEvaluation] = []
    evaluate = make_config_evaluator(
        analysis.spec, runtime_client, pool, dev_cases, threshold.threshold,
        collect=collected, allow_repair=allow_repair,
    )

    design = Architect(client=planning_client).design(
        analysis.spec,
        pool,
        evaluate,
        min_entity_f1=min_entity_f1,
        max_p95_latency_s=max_p95_latency_s,
        min_schema_validity=min_schema_validity,
        estimate_p95=(
            (lambda c: estimate_p95(c, single_call_p95_s))
            if single_call_p95_s is not None
            else None
        ),
    )

    return FullDesign(
        project_id=spec.project_id,
        analysis=analysis,
        design=design,
        evaluations=collected,
        oos_threshold=threshold,
        seconds=time.perf_counter() - started,
        data_access=access.as_dict(),
    )
