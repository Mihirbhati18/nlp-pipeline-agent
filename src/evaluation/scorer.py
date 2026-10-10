"""The common scorer (PROJECT_PLAN.md section 5).

One implementation, used by every system, so no system is scored by its own
rules. It computes the primary metrics:

- intent macro-F1 on in-scope requests, where an out-of-scope rejection of an
  in-scope request is an error
- entity span F1 by exact type and character span, micro-averaged
- out-of-scope precision, recall, F1 and the in-scope false-rejection rate
- schema validity before and after repair
- unsupported extraction rate, with its numerator and denominator published
- runtime failure, retry and fallback rates
- latency, taken only from uncached timing runs

and the secondary metrics: end-to-end exact match and unsupported request rate.

Rules this file keeps:

- Failed, malformed and missing responses stay in every denominator. Nothing is
  dropped to make a score look better.
- A case with no prediction at all is recorded as a missing response, not
  skipped.
- Unsupported extraction rate is None (reported as N/A) when nothing was
  predicted, never 0.
- Out-of-scope requests have no supported entity to extract, so entity F1 is
  computed over in-scope requests; entities predicted on out-of-scope requests
  are still counted in the unsupported-extraction and request-level metrics.
"""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from .span_rule import locate_entities

OOS_LABEL = "none_of_the_above"
METRIC_DEFINITIONS_VERSION = "1.2"

# A prediction's status. Only OK and OOS are usable answers.
STATUS_OK = "ok"
STATUS_OOS = "oos"
STATUS_INVALID = "invalid"  # output never became valid, even after repair
STATUS_ERROR = "error"  # timeout, exception or refused call
STATUS_MISSING = "missing"  # no prediction recorded for an evaluated case
FAILURE_STATUSES = (STATUS_INVALID, STATUS_ERROR, STATUS_MISSING)


@dataclass
class Prediction:
    """One system's answer for one case."""

    case_id: str
    status: str
    intent: str | None = None
    entities: list[dict] = field(default_factory=list)
    # Schema validity of the raw output, before any repair attempt. None when
    # the system has no repair stage, in which case the final value is used.
    schema_valid_raw: bool | None = None
    schema_valid_final: bool = False
    retries: int = 0
    fallback_used: bool = False
    error: str | None = None

    @property
    def is_failure(self) -> bool:
        return self.status in FAILURE_STATUSES


def _f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def _predicted_label(prediction: Prediction) -> str | None:
    """The label a prediction actually asserts.

    A failure asserts nothing: it is wrong for the gold intent but does not
    become a false positive for any other intent.
    """
    if prediction.status == STATUS_OOS:
        return OOS_LABEL
    if prediction.status == STATUS_OK:
        return prediction.intent
    return None


def _percentile(values: Sequence[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = fraction * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    weight = position - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def score(
    cases: Iterable[dict],
    predictions: Iterable[Prediction],
    *,
    labels: Sequence[str] | None = None,
    latencies: Sequence[float] | None = None,
    cold_start_s: float | None = None,
    design_cost: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score one system on one project's split.

    ``cases`` are prepared cases from ``data/processed``; ``latencies`` come
    only from an uncached timing run.

    ``labels`` is the project's declared in-scope intent inventory. Passing it
    keeps macro-F1 comparable across systems, because every system is then
    averaged over the same label set rather than over whichever labels it
    happened to predict. It defaults to the labels present in the gold data. A
    predicted label outside this set is an invented label: the case counts as
    wrong and the prediction is reported under
    ``invalid_label_predictions``, but it is never charged as a false positive
    to a real intent.
    """
    cases = list(cases)
    by_id = {p.case_id: p for p in predictions}

    missing_ids = [c["case_id"] for c in cases if c["case_id"] not in by_id]
    for case_id in missing_ids:
        by_id[case_id] = Prediction(case_id=case_id, status=STATUS_MISSING)

    extra_ids = sorted(set(by_id) - {c["case_id"] for c in cases})

    # -- intent macro-F1 over in-scope requests ------------------------
    tp: Counter = Counter()
    fp: Counter = Counter()
    fn: Counter = Counter()
    in_scope_cases = [c for c in cases if c["in_scope"]]
    gold_labels = sorted(labels) if labels else sorted({c["true_intent"] for c in in_scope_cases})
    label_set = set(gold_labels)
    invalid_label_predictions: Counter = Counter()

    for case in in_scope_cases:
        gold = case["true_intent"]
        predicted = _predicted_label(by_id[case["case_id"]])
        if predicted == gold:
            tp[gold] += 1
        else:
            fn[gold] += 1
            if predicted is not None and predicted != OOS_LABEL:
                if predicted in label_set:
                    fp[predicted] += 1
                else:
                    invalid_label_predictions[predicted] += 1

    per_intent = {}
    for label in gold_labels:
        precision, recall, f1 = _f1(tp[label], fp[label], fn[label])
        per_intent[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": tp[label] + fn[label],
        }
    intent_macro_f1 = (
        statistics.mean(v["f1"] for v in per_intent.values()) if per_intent else None
    )
    intent_accuracy = (
        sum(tp.values()) / len(in_scope_cases) if in_scope_cases else None
    )

    # -- out-of-scope detection, out-of-scope as the positive class ----
    oos_tp = oos_fp = oos_fn = 0
    in_scope_rejected = 0
    for case in cases:
        prediction = by_id[case["case_id"]]
        predicted_oos = prediction.status == STATUS_OOS
        if not case["in_scope"]:
            if predicted_oos:
                oos_tp += 1
            else:
                oos_fn += 1
        else:
            if predicted_oos:
                oos_fp += 1
                in_scope_rejected += 1
    oos_precision, oos_recall, oos_f1 = _f1(oos_tp, oos_fp, oos_fn)

    # -- entity span F1, micro, over in-scope requests ------------------
    entity_tp = entity_fp = entity_fn = 0
    unsupported_items = 0
    predicted_items = 0
    requests_with_unsupported = 0
    case_entity_exact: dict[str, bool] = {}

    for case in cases:
        prediction = by_id[case["case_id"]]
        located = locate_entities(case["utt"], prediction.entities)
        predicted_items += len(located)
        case_unsupported = sum(1 for e in located if not e.supported)
        unsupported_items += case_unsupported
        if case_unsupported:
            requests_with_unsupported += 1

        if not case["in_scope"]:
            # No supported entity exists for an out-of-scope request; its
            # predicted entities are captured by the unsupported metrics above.
            continue

        gold = Counter((e["type"], e["start"], e["end"]) for e in case["entities"])
        found = Counter(
            (e.type, e.start, e.end) for e in located if e.supported
        )
        matched = sum((gold & found).values())
        entity_tp += matched
        # Unsupported predictions are false positives (rule step 3).
        entity_fp += sum((found - gold).values()) + case_unsupported
        entity_fn += sum((gold - found).values())
        case_entity_exact[case["case_id"]] = (
            matched == sum(gold.values()) and not (found - gold) and not case_unsupported
        )

    entity_precision, entity_recall, entity_f1 = _f1(entity_tp, entity_fp, entity_fn)

    # -- schema validity, before and after repair ----------------------
    total = len(cases)
    valid_final = sum(1 for c in cases if by_id[c["case_id"]].schema_valid_final)
    raw_known = [
        by_id[c["case_id"]].schema_valid_raw
        for c in cases
        if by_id[c["case_id"]].schema_valid_raw is not None
    ]
    schema_validity_raw = (sum(raw_known) / total) if raw_known else None

    # -- runtime failures -----------------------------------------------
    status_counts = Counter(by_id[c["case_id"]].status for c in cases)
    failures = sum(status_counts[s] for s in FAILURE_STATUSES)
    retries = sum(by_id[c["case_id"]].retries for c in cases)
    fallbacks = sum(1 for c in cases if by_id[c["case_id"]].fallback_used)

    # -- end-to-end exact match (secondary) -----------------------------
    exact = 0
    for case in cases:
        prediction = by_id[case["case_id"]]
        decision_right = _predicted_label(prediction) == (
            case["true_intent"] if case["in_scope"] else OOS_LABEL
        )
        if case["in_scope"]:
            entities_right = case_entity_exact.get(case["case_id"], False)
        else:
            # The correct entity set for a rejected request is the empty one.
            entities_right = not prediction.entities
        if decision_right and entities_right and prediction.schema_valid_final:
            exact += 1

    latencies = list(latencies or [])

    return {
        "metric_definitions_version": METRIC_DEFINITIONS_VERSION,
        "n_cases": total,
        "n_in_scope": len(in_scope_cases),
        "n_out_of_scope": total - len(in_scope_cases),
        "missing_responses": len(missing_ids),
        "unexpected_prediction_ids": extra_ids,
        "intent_label_set": gold_labels,
        "invalid_label_predictions": dict(invalid_label_predictions),
        "primary": {
            "intent_macro_f1": intent_macro_f1,
            "intent_accuracy_in_scope": intent_accuracy,
            "entity_span_precision": entity_precision,
            "entity_span_recall": entity_recall,
            "entity_span_f1": entity_f1,
            "entity_counts": {"tp": entity_tp, "fp": entity_fp, "fn": entity_fn},
            "oos_precision": oos_precision,
            "oos_recall": oos_recall,
            "oos_f1": oos_f1,
            "oos_counts": {"tp": oos_tp, "fp": oos_fp, "fn": oos_fn},
            "false_rejection_rate_in_scope": (
                in_scope_rejected / len(in_scope_cases) if in_scope_cases else None
            ),
            "schema_validity_after_repair": valid_final / total if total else None,
            "schema_validity_before_repair": schema_validity_raw,
            "unsupported_extraction_rate": (
                unsupported_items / predicted_items if predicted_items else None
            ),
            "unsupported_extraction_counts": {
                "unsupported_items": unsupported_items,
                "predicted_items": predicted_items,
            },
            "runtime_failure_rate": failures / total if total else None,
            "runtime_failure_counts": dict(status_counts),
            "retries": retries,
            "fallback_rate": fallbacks / total if total else None,
            "latency_median_s": statistics.median(latencies) if latencies else None,
            "latency_p95_s": _percentile(latencies, 0.95),
            "latency_n_timed": len(latencies),
            "cold_start_s": cold_start_s,
            "design_cost": design_cost,
        },
        "secondary": {
            "end_to_end_exact_match": exact / total if total else None,
            "unsupported_request_rate": (
                requests_with_unsupported / total if total else None
            ),
        },
        "per_intent": per_intent,
    }
