"""Out-of-scope threshold tuning, one documented rule for every system.

B0's TF-IDF confidence, B3's maximum-softmax confidence and the catalogue's
TF-IDF out-of-scope policy all need a threshold. The plan requires the same
rule type for all of them and tuning on development data only
(PROJECT_PLAN.md sections 3 and 4), so the rule lives here.

**The rule.** Given a confidence score per development case and the gold
in-scope/out-of-scope labels, choose the threshold that maximises macro-F1
over the project's intent inventory *plus* the out-of-scope class, treating
every class with equal weight. Candidate thresholds are the observed
confidence values, so the search is exhaustive over distinct decisions rather
than over an arbitrary grid. Ties are broken toward the **lower** threshold,
which rejects fewer in-scope requests.

Tuning never sees test data, and the chosen value is recorded in the run
config so the decision is reproducible.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Sequence

OOS_LABEL = "none_of_the_above"


@dataclass
class ThresholdChoice:
    threshold: float
    macro_f1: float
    n_candidates: int
    criterion: str = "macro-F1 over intents plus the out-of-scope class, dev only"

    def as_dict(self) -> dict[str, object]:
        return {
            "threshold": self.threshold,
            "dev_macro_f1_at_threshold": self.macro_f1,
            "n_candidate_thresholds": self.n_candidates,
            "criterion": self.criterion,
            "tuned_on": "development split only",
        }


def macro_f1_with_oos(
    gold: Sequence[str], predicted: Sequence[str], labels: Sequence[str]
) -> float:
    """Macro-F1 over ``labels`` plus the out-of-scope class."""
    classes = list(dict.fromkeys([*labels, OOS_LABEL]))
    scores: list[float] = []
    for label in classes:
        tp = sum(1 for g, p in zip(gold, predicted) if g == label and p == label)
        fp = sum(1 for g, p in zip(gold, predicted) if g != label and p == label)
        fn = sum(1 for g, p in zip(gold, predicted) if g == label and p != label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        scores.append(
            2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        )
    return statistics.mean(scores) if scores else 0.0


def tune_binary_threshold(
    confidences: Sequence[float], in_scope: Sequence[bool]
) -> ThresholdChoice:
    """Tune a threshold whose only job is the in-scope/out-of-scope decision.

    The catalogue's TF-IDF out-of-scope policy rejects a request *before* any
    model call, so no intent prediction exists at tuning time and the macro-F1
    rule above cannot be applied. This variant therefore maximises F1 on the
    binary decision with out-of-scope as the positive class, still on
    development data only, still with ties broken toward the lower threshold.

    B0 and B3 use ``tune_threshold`` instead, because their classifiers produce
    an intent and a confidence together.
    """
    if not confidences:
        return ThresholdChoice(threshold=0.0, macro_f1=0.0, n_candidates=0, criterion="n/a")

    candidates = sorted({*confidences, min(confidences) - 1e-9})
    best: ThresholdChoice | None = None
    for threshold in candidates:
        tp = fp = fn = 0
        for confidence, is_in_scope in zip(confidences, in_scope):
            rejected = confidence < threshold
            if not is_in_scope:
                if rejected:
                    tp += 1
                else:
                    fn += 1
            elif rejected:
                fp += 1
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        if best is None or f1 > best.macro_f1:
            best = ThresholdChoice(
                threshold=float(threshold),
                macro_f1=f1,
                n_candidates=len(candidates),
                criterion=(
                    "F1 on the binary in-scope/out-of-scope decision, dev only "
                    "(no intent prediction exists before the model call)"
                ),
            )
    assert best is not None
    return best


def tune_threshold(
    confidences: Sequence[float],
    closed_set_predictions: Sequence[str],
    gold: Sequence[str],
    labels: Sequence[str],
) -> ThresholdChoice:
    """Pick the confidence threshold by the documented rule.

    ``closed_set_predictions`` are the classifier's intent predictions ignoring
    the out-of-scope question; a case is relabelled out-of-scope when its
    confidence falls *below* the threshold.
    """
    if not confidences:
        return ThresholdChoice(threshold=0.0, macro_f1=0.0, n_candidates=0)

    # Candidates: each observed confidence, plus a value below the minimum so
    # "reject nothing" is reachable.
    candidates = sorted({*confidences, min(confidences) - 1e-9})
    best: ThresholdChoice | None = None
    for threshold in candidates:
        predicted = [
            prediction if confidence >= threshold else OOS_LABEL
            for confidence, prediction in zip(confidences, closed_set_predictions)
        ]
        score = macro_f1_with_oos(gold, predicted, labels)
        # Strict improvement only, so ties keep the lower threshold.
        if best is None or score > best.macro_f1:
            best = ThresholdChoice(
                threshold=float(threshold), macro_f1=score, n_candidates=len(candidates)
            )
    assert best is not None
    return best
