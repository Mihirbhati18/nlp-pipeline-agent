"""The fixed 12-configuration execution catalogue (PROJECT_PLAN.md section 6).

Three factors:

| Factor | Options |
|---|---|
| Extraction strategy | joint single call; two-stage (intent, then that intent's slots); schema-guided JSON with field descriptions |
| Example selection | fixed (one per intent); similarity-retrieved |
| Out-of-scope policy | LLM "none of the above" label; TF-IDF similarity threshold tuned on development data |

3 x 2 x 2 = 12 configurations. All are trusted Python components; no generated
code is executed. B1, B2, B4 and A1 all run through this same catalogue, so a
quality difference between them cannot come from different runtime code.

B1 is fixed to one predeclared configuration: joint single call, fixed
examples, LLM label (``joint-fixed-llm``).

Prompt-size cap: at most 16 examples and at most 2,000 input tokens. Examples
are dropped first; intent and entity definitions are never truncated.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import product
from typing import Any, Callable

from ..analyzer.spec import OOS_LABEL, ProjectSpec
from ..evaluation.output_schema import ParsedOutput, parse_output, repair_instruction
from ..evaluation.scorer import STATUS_INVALID, STATUS_OOS, Prediction
from ..llm.client import MAX_EXAMPLES, MAX_INPUT_TOKENS, LLMClient, estimate_tokens
from .examples import ExampleSelector

EXTRACTION = ("joint", "two_stage", "schema_guided")
EXAMPLE_SELECTION = ("fixed", "similarity")
OOS_POLICY = ("llm_label", "tfidf_threshold")

B1_CONFIG_ID = "joint-fixed-llm"


@dataclass(frozen=True)
class Config:
    """One catalogue entry. Declarative: it names strategies, it is not code."""

    extraction: str
    example_selection: str
    oos_policy: str

    @property
    def config_id(self) -> str:
        short = {
            "joint": "joint",
            "two_stage": "twostage",
            "schema_guided": "schema",
            "fixed": "fixed",
            "similarity": "sim",
            "llm_label": "llm",
            "tfidf_threshold": "tfidf",
        }
        return f"{short[self.extraction]}-{short[self.example_selection]}-{short[self.oos_policy]}"

    @property
    def calls_per_request(self) -> int:
        """Logical model calls one request costs, before any repair retry.

        Two-stage makes two. A TF-IDF rejection makes none, but that depends on
        the request, so it is not reflected here; the budget uses this as the
        upper figure.
        """
        return 2 if self.extraction == "two_stage" else 1

    def as_dict(self) -> dict[str, Any]:
        return {
            "config_id": self.config_id,
            "extraction": self.extraction,
            "example_selection": self.example_selection,
            "oos_policy": self.oos_policy,
            "calls_per_request": self.calls_per_request,
        }


def build_catalogue() -> list[Config]:
    """The 12 configurations, in a fixed order that never changes."""
    return [
        Config(extraction=e, example_selection=s, oos_policy=o)
        for e, s, o in product(EXTRACTION, EXAMPLE_SELECTION, OOS_POLICY)
    ]


CATALOGUE = build_catalogue()
CATALOGUE_BY_ID = {c.config_id: c for c in CATALOGUE}


def get_config(config_id: str) -> Config:
    if config_id not in CATALOGUE_BY_ID:
        raise KeyError(
            f"{config_id!r} is not a catalogue configuration; "
            f"valid ids: {', '.join(sorted(CATALOGUE_BY_ID))}"
        )
    return CATALOGUE_BY_ID[config_id]


# -- prompt rendering --------------------------------------------------


def _definition_lines(spec: ProjectSpec, *, with_descriptions: bool, oos: bool) -> list[str]:
    lines = ["Supported requests:"]
    for intent in spec.intents:
        if with_descriptions and intent.description:
            lines.append(f"- {intent.name}: {intent.description}")
        else:
            lines.append(f"- {intent.name}")
    if oos:
        lines.append(f"- {OOS_LABEL}: the request is not one of the supported requests above")
    return lines


def _entity_lines(spec: ProjectSpec, types: list[str], *, with_descriptions: bool) -> list[str]:
    lines = ["Information to extract, copied exactly as written in the request:"]
    described = {e.name: e.description for e in spec.entity_types}
    for name in types:
        description = described.get(name)
        if with_descriptions and description:
            lines.append(f"- {name}: {description}")
        else:
            lines.append(f"- {name}")
    return lines


def _example_lines(examples: list[dict], *, entities: bool) -> list[str]:
    lines = ["Examples:"]
    for case in examples:
        answer: dict[str, Any] = {"intent": case["true_intent"]}
        if entities:
            answer["entities"] = [
                {"type": e["type"], "text": e["text"]} for e in case["entities"]
            ]
        lines.append(f"Request: {case['utt']}")
        lines.append(f"Answer: {json.dumps(answer, ensure_ascii=False)}")
    return lines


def _assemble(header: list[str], examples: list[dict], footer: list[str], *, entities: bool) -> tuple[str, int]:
    """Join the parts, dropping examples until the token cap is met.

    Definitions are never truncated, so if even zero examples exceeds the cap
    the prompt is returned oversized and the client rejects it rather than
    silently shipping a damaged prompt.
    """
    chosen = list(examples[:MAX_EXAMPLES])
    while True:
        parts = list(header)
        if chosen:
            parts += [""] + _example_lines(chosen, entities=entities)
        parts += [""] + footer
        prompt = "\n".join(parts)
        if estimate_tokens(prompt) <= MAX_INPUT_TOKENS or not chosen:
            return prompt, len(chosen)
        chosen.pop()


def render_prompt(
    config: Config,
    spec: ProjectSpec,
    utterance: str,
    examples: list[dict],
    *,
    stage: str = "joint",
    intent: str | None = None,
) -> tuple[str, int]:
    """Render one request's prompt. Returns (prompt, examples actually included).

    ``stage`` is "joint" for single-call strategies, or "intent"/"entities" for
    the two-stage strategy's two calls.
    """
    offer_oos = config.oos_policy == "llm_label"
    described = config.extraction == "schema_guided"

    if stage == "intent":
        header = ["Name the single supported request this message is. Reply with JSON only.", ""]
        header += _definition_lines(spec, with_descriptions=described, oos=offer_oos)
        footer = [
            'Reply exactly: {"intent": "<one name from the list>"}',
            "",
            f"Request: {utterance}",
            "Answer:",
        ]
        return _assemble(header, examples, footer, entities=False)

    if stage == "entities":
        types = spec.slots_by_intent.get(intent or "", spec.entity_type_names)
        header = [
            f"The request is {intent}. Extract only the information listed below. "
            "Reply with JSON only.",
            "",
        ]
        header += _entity_lines(spec, types or [], with_descriptions=described)
        footer = [
            'Reply exactly: {"entities": [{"type": "<a type from the list>", '
            '"text": "<text copied exactly from the request>"}]}',
            "Use an empty list if the request contains none of them. Never invent a value.",
            "",
            f"Request: {utterance}",
            "Answer:",
        ]
        # Entity-stage examples show only the slots this intent carries.
        filtered = [
            {
                **case,
                "entities": [e for e in case["entities"] if e["type"] in set(types or [])],
            }
            for case in examples
            if case["true_intent"] == intent
        ] or examples
        return _assemble(header, filtered, footer, entities=True)

    header = ["Label this request and extract its information. Reply with JSON only.", ""]
    header += _definition_lines(spec, with_descriptions=described, oos=offer_oos)
    header += [""] + _entity_lines(spec, spec.entity_type_names, with_descriptions=described)
    footer = [
        'Reply exactly: {"intent": "<one name>", "entities": [{"type": "<a type>", '
        '"text": "<text copied exactly from the request>"}]}',
        "Use an empty list if there is nothing to extract. Never invent a value.",
        "",
        f"Request: {utterance}",
        "Answer:",
    ]
    return _assemble(header, examples, footer, entities=True)


# -- execution ---------------------------------------------------------


@dataclass
class RunOutcome:
    """What running one configuration on one case produced."""

    prediction: Prediction
    logical_calls: int
    physical_calls: int
    cache_hits: int
    prompt_tokens: int
    repaired: bool
    rejected_by_threshold: bool
    events: list[dict]


@dataclass
class ConfigRunner:
    """Executes one catalogue configuration over a project's cases."""

    config: Config
    spec: ProjectSpec
    client: LLMClient
    selector: ExampleSelector
    # Tuned on development data only; required by the tfidf_threshold policy.
    oos_threshold: float | None = None
    allow_repair: bool = True

    def __post_init__(self) -> None:
        if self.config.oos_policy == "tfidf_threshold" and self.oos_threshold is None:
            raise ValueError(
                f"{self.config.config_id} needs an oos_threshold tuned on development data"
            )

    def _examples(self, utterance: str) -> list[dict]:
        if self.config.example_selection == "fixed":
            return self.selector.fixed()
        return self.selector.similarity(utterance)

    def _parse(self, raw: str) -> ParsedOutput:
        return parse_output(
            raw,
            labels=self.spec.intent_names,
            entity_types=self.spec.entity_type_names,
        )

    def run_case(self, case: dict) -> RunOutcome:
        utterance = case["utt"]
        events: list[dict] = []
        logical = physical = hits = tokens = 0
        repaired = False

        # The TF-IDF policy decides out-of-scope before spending a call.
        if self.config.oos_policy == "tfidf_threshold":
            similarity = self.selector.max_similarity(utterance)
            if similarity < (self.oos_threshold or 0.0):
                events.append(
                    {
                        "kind": "tfidf_rejection",
                        "case_id": case["case_id"],
                        "max_similarity": similarity,
                        "threshold": self.oos_threshold,
                    }
                )
                return RunOutcome(
                    prediction=Prediction(
                        case_id=case["case_id"],
                        status=STATUS_OOS,
                        schema_valid_raw=True,
                        schema_valid_final=True,
                    ),
                    logical_calls=0,
                    physical_calls=0,
                    cache_hits=0,
                    prompt_tokens=0,
                    repaired=False,
                    rejected_by_threshold=True,
                    events=events,
                )

        examples = self._examples(utterance)

        if self.config.extraction == "two_stage":
            prompt, n_examples = render_prompt(
                self.config, self.spec, utterance, examples, stage="intent"
            )
            record = self.client.generate(prompt, max_examples_used=n_examples)
            logical += 1
            physical += 0 if record.cache_hit else 1
            hits += 1 if record.cache_hit else 0
            tokens += record.prompt_tokens or 0
            if record.error:
                return self._failure(case, record.error, logical, physical, hits, tokens, events)

            first = self._parse(record.text)
            if first.intent is None:
                return self._invalid(case, first, logical, physical, hits, tokens, events)
            if first.status == STATUS_OOS:
                prediction = first.as_prediction(case["case_id"])
                return RunOutcome(prediction, logical, physical, hits, tokens, False, False, events)

            prompt2, n_examples2 = render_prompt(
                self.config,
                self.spec,
                utterance,
                examples,
                stage="entities",
                intent=first.intent,
            )
            record2 = self.client.generate(prompt2, max_examples_used=n_examples2)
            logical += 1
            physical += 0 if record2.cache_hit else 1
            hits += 1 if record2.cache_hit else 0
            tokens += record2.prompt_tokens or 0
            if record2.error:
                return self._failure(case, record2.error, logical, physical, hits, tokens, events)

            # The entity stage returns only entities; the intent comes from stage one.
            merged = f'{{"intent": {json.dumps(first.intent)}, "entities": {_entities_json(record2.text)}}}'
            parsed = self._parse(merged)
        else:
            prompt, n_examples = render_prompt(self.config, self.spec, utterance, examples)
            record = self.client.generate(prompt, max_examples_used=n_examples)
            logical += 1
            physical += 0 if record.cache_hit else 1
            hits += 1 if record.cache_hit else 0
            tokens += record.prompt_tokens or 0
            if record.error:
                return self._failure(case, record.error, logical, physical, hits, tokens, events)
            parsed = self._parse(record.text)

        raw_valid = parsed.schema_valid

        # One repair retry, which is a new counted call with its own cache entry.
        if not parsed.schema_valid and self.allow_repair:
            instruction = repair_instruction(
                parsed, self.spec.intent_names, self.spec.entity_type_names
            )
            repair_prompt = f"{prompt}\n\n{instruction}\nAnswer:"
            retry = self.client.generate_repair(repair_prompt)
            logical += 1
            physical += 0 if retry.cache_hit else 1
            hits += 1 if retry.cache_hit else 0
            tokens += retry.prompt_tokens or 0
            repaired = True
            events.append({"kind": "repair_attempt", "case_id": case["case_id"]})
            if not retry.error:
                repaired_parse = self._parse(retry.text)
                if repaired_parse.schema_valid:
                    parsed = repaired_parse

        prediction = parsed.as_prediction(case["case_id"], retries=1 if repaired else 0)
        # Schema validity before repair is reported separately from after.
        prediction.schema_valid_raw = raw_valid
        return RunOutcome(
            prediction=prediction,
            logical_calls=logical,
            physical_calls=physical,
            cache_hits=hits,
            prompt_tokens=tokens,
            repaired=repaired,
            rejected_by_threshold=False,
            events=events,
        )

    # -- failure paths --------------------------------------------------

    def _failure(self, case, error, logical, physical, hits, tokens, events) -> RunOutcome:
        events.append({"kind": "runtime_failure", "case_id": case["case_id"], "error": error})
        return RunOutcome(
            prediction=Prediction(
                case_id=case["case_id"], status="error", error=error, schema_valid_final=False
            ),
            logical_calls=logical,
            physical_calls=physical,
            cache_hits=hits,
            prompt_tokens=tokens,
            repaired=False,
            rejected_by_threshold=False,
            events=events,
        )

    def _invalid(self, case, parsed, logical, physical, hits, tokens, events) -> RunOutcome:
        prediction = parsed.as_prediction(case["case_id"])
        prediction.status = STATUS_INVALID
        prediction.schema_valid_final = False
        return RunOutcome(
            prediction=prediction,
            logical_calls=logical,
            physical_calls=physical,
            cache_hits=hits,
            prompt_tokens=tokens,
            repaired=False,
            rejected_by_threshold=False,
            events=events,
        )


def _entities_json(raw: str) -> str:
    """Pull the entity list out of a stage-two reply, or return an empty list.

    An unreadable stage-two reply yields no entities, and the merged output is
    then scored as a missed-entity case rather than being dropped.
    """
    try:
        data = json.loads(raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
    except (json.JSONDecodeError, AttributeError):
        return "[]"
    if isinstance(data, dict) and isinstance(data.get("entities"), list):
        return json.dumps(data["entities"], ensure_ascii=False)
    if isinstance(data, list):
        return json.dumps(data, ensure_ascii=False)
    return "[]"
