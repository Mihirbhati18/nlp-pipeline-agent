"""Checks on A2's Architect (decision 42): factor-wise reasoning, structured
candidates, a one-factor revision, and A1's safety contract kept intact."""

import itertools
import json
from types import SimpleNamespace

import pytest

from src.analyzer.spec import Constraints, EntitySpec, IntentSpec, ProjectSpec
from src.architect.architect_v2 import (
    OPTIONS,
    ArchitectV2,
    factors_of,
    find_config,
    neighbours,
)
from src.pipelines.catalogue import CATALOGUE, CATALOGUE_BY_ID

SPEC = ProjectSpec(
    project_id="PT", name="Test project",
    description_text="An assistant that sets and cancels alarms for people at home.",
    intents=[IntentSpec("alarm_set"), IntentSpec("alarm_remove")],
    entity_types=[EntitySpec("time")],
    slots_by_intent={"alarm_set": ["time"], "alarm_remove": []},
    constraints=Constraints(),
)
POOL = [{"case_id": "k1", "utt": "wake me at six", "true_intent": "alarm_set", "in_scope": True,
         "entities": [{"type": "time", "text": "six", "start": 11, "end": 14}]}]


class FakeClient:
    """Answers planning prompts from two queues and records every prompt."""

    def __init__(self, rankings=None, revision=None):
        self.rankings = rankings
        self.revision = revision
        self.prompts = []

    def generate(self, prompt, **_):
        self.prompts.append(prompt)
        reply = self.rankings if "rank ALL of its options" in prompt else self.revision
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return SimpleNamespace(text=text, cache_hit=False, error=None)


def ranking(e, s, o):
    return {"extraction": {"ranking": list(e), "why": "e-reason"},
            "example_selection": {"ranking": list(s), "why": "s-reason"},
            "oos_policy": {"ranking": list(o), "why": "o-reason"}}


def evaluator(scores=None):
    """Scores each configuration by a fixed table (default: catalogue position)."""
    seen = []

    def evaluate(config):
        seen.append(config.config_id)
        value = (scores or {}).get(config.config_id, 0.5 + 0.01 * CATALOGUE.index(config))
        return {"primary": {"intent_macro_f1": value, "entity_span_f1": 0.5,
                            "schema_validity_after_repair": 1.0}}, 100, 100
    evaluate.seen = seen
    return evaluate


E = ("schema_guided", "joint", "two_stage")
S = ("similarity", "fixed")
O = ("llm_label", "tfidf_threshold")


def test_the_initial_candidates_follow_the_one_factor_design():
    client = FakeClient(ranking(E, S, O), {"change": "oos_policy=tfidf_threshold", "why": "cheaper"})
    result = ArchitectV2(client=client).design(SPEC, POOL, evaluator())
    first_three = [a.config_id for a in result.attempts[:3]]
    assert first_three == [
        find_config("schema_guided", "similarity", "llm_label").config_id,
        find_config("schema_guided", "fixed", "llm_label").config_id,
        find_config("joint", "similarity", "llm_label").config_id,
    ]
    assert all(a.source == "reasoned" for a in result.attempts)


@pytest.mark.parametrize("e,s,o", list(itertools.product(
    itertools.permutations(OPTIONS["extraction"]),
    itertools.permutations(OPTIONS["example_selection"]),
    itertools.permutations(OPTIONS["oos_policy"]),
)))
def test_both_example_selections_are_always_tried(e, s, o):
    client = FakeClient(ranking(e, s, o), {"change": "nonsense"})
    result = ArchitectV2(client=client).design(SPEC, POOL, evaluator())
    tried = {CATALOGUE_BY_ID[a.config_id].example_selection for a in result.attempts}
    assert tried == {"fixed", "similarity"}
    assert len(result.attempts) == 4
    assert len({a.config_id for a in result.attempts}) == 4  # no duplicates


def test_a_malformed_ranking_falls_back_to_the_neutral_order_and_is_reported():
    bad = ranking(E, S, O)
    bad["extraction"]["ranking"] = ["schema_guided", "magic_strategy"]
    result = ArchitectV2(client=FakeClient(bad, None)).design(SPEC, POOL, evaluator())
    assert any("extraction" in f and "neutral" in f for f in result.findings)
    # The neutral extraction order starts with joint; the first candidate depends on it.
    assert result.attempts[0].config_id.startswith("joint-")
    # Every initial candidate sits on the unranked extraction choice, so none
    # is credited as reasoning, even though the other two factors were ranked.
    assert [a.source for a in result.attempts[:3]] == ["fallback"] * 3


def test_without_a_model_every_choice_is_a_counted_fallback():
    result = ArchitectV2(client=None).design(SPEC, POOL, evaluator())
    assert result.reasoned_choices == 0
    assert result.budget_used == 4
    assert result.planning_calls == 0


def test_an_unparseable_reply_is_reported_not_trusted():
    result = ArchitectV2(client=FakeClient("this is not json", "neither is this")).design(
        SPEC, POOL, evaluator())
    assert any("not JSON" in f for f in result.findings)
    assert result.reasoned_choices == 0


def test_the_revision_changes_exactly_one_factor_from_the_best():
    scores = {find_config("joint", "similarity", "llm_label").config_id: 0.99}
    client = FakeClient(ranking(E, S, O), {"change": "example_selection=fixed", "why": "check"})
    result = ArchitectV2(client=client).design(SPEC, POOL, evaluator(scores))
    revision = CATALOGUE_BY_ID[result.attempts[3].config_id]
    best = CATALOGUE_BY_ID[find_config("joint", "similarity", "llm_label").config_id]
    differing = [f for f, v in factors_of(revision).items() if factors_of(best)[f] != v]
    assert len(differing) == 1
    assert result.attempts[3].config_id == find_config("joint", "fixed", "llm_label").config_id
    assert result.attempts[3].source == "reasoned"


def test_an_illegal_revision_is_replaced_by_the_first_allowed_move():
    client = FakeClient(ranking(E, S, O), {"change": "extraction=two_stage,oos_policy=tfidf_threshold"})
    result = ArchitectV2(client=client).design(SPEC, POOL, evaluator())
    assert result.attempts[3].source == "fallback"
    assert any("not an allowed one-factor change" in f for f in result.findings)


def test_the_revision_prompt_contains_the_real_development_scores():
    scores = {find_config("schema_guided", "similarity", "llm_label").config_id: 0.8771}
    client = FakeClient(ranking(E, S, O), {"change": "oos_policy=tfidf_threshold"})
    ArchitectV2(client=client).design(SPEC, POOL, evaluator(scores))
    assert "0.877" in client.prompts[-1]


def test_selection_uses_the_shared_rule():
    winner = find_config("schema_guided", "fixed", "llm_label").config_id
    client = FakeClient(ranking(E, S, O), {"change": "oos_policy=tfidf_threshold"})
    result = ArchitectV2(client=client).design(SPEC, POOL, evaluator({winner: 0.99}))
    assert result.selection.selected.config_id == winner


def test_a_crashed_candidate_still_uses_its_slot_and_is_not_selected():
    def evaluate(config):
        if config.config_id.startswith("schema-sim"):
            raise RuntimeError("boom")
        return evaluator()(config)
    client = FakeClient(ranking(E, S, O), {"change": "oos_policy=tfidf_threshold"})
    result = ArchitectV2(client=client).design(SPEC, POOL, evaluate)
    assert result.budget_used == 4
    assert result.attempts[0].error and result.selection.selected.config_id != result.attempts[0].config_id


def test_neighbours_differ_in_one_factor_and_skip_tried_ones():
    config = find_config("joint", "fixed", "llm_label")
    moves = neighbours(config, exclude={find_config("schema_guided", "fixed", "llm_label").config_id})
    assert len(moves) == 3  # two_stage, similarity, tfidf (schema_guided excluded)
    for cfg in moves.values():
        assert sum(factors_of(cfg)[f] != factors_of(config)[f] for f in factors_of(config)) == 1


def test_an_unknown_architect_version_is_refused():
    from src.architect.design_run import run_design
    with pytest.raises(ValueError, match="unknown architect version"):
        run_design(SPEC, None, runtime_client=None, load_cases=lambda p: POOL, architect_version="v3")
