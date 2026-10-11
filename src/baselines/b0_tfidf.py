"""B0: the simple reference baseline (PROJECT_PLAN.md section 3).

A TF-IDF intent classifier with a documented out-of-scope threshold. It makes
**no model calls at all**, so it is the cheapest system in the comparison and
the sanity floor: if an LLM pipeline cannot beat this, that is the result.

Deliberate limits, to be stated plainly rather than hidden:

- **It extracts no entities.** It is an intent classifier. Its entity F1 is
  therefore 0 and its unsupported-extraction rate is N/A. That is the honest
  consequence of the baseline's design, not a scoring artefact.
- It is trained on the same k = 10 examples per intent that every LLM system
  receives, so the data regime is matched.
- It never sees out-of-scope examples, like every other system here. The
  out-of-scope decision is a confidence threshold tuned on development data by
  the shared rule in ``src/evaluation/thresholds.py``.

B0 is a sanity reference, not a state-of-the-art claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

from ..evaluation.scorer import STATUS_OK, STATUS_OOS, Prediction
from ..evaluation.thresholds import ThresholdChoice, tune_threshold


@dataclass
class B0TfidfClassifier:
    """Fit on a k-shot pool, tune the threshold on development data, predict."""

    labels: Sequence[str]
    random_state: int = 0
    threshold_choice: ThresholdChoice | None = None
    model: Any = field(default=None, repr=False)

    def fit(self, pool: Sequence[dict]) -> "B0TfidfClassifier":
        texts = [case["utt"] for case in pool]
        targets = [case["true_intent"] for case in pool]
        self.model = make_pipeline(
            TfidfVectorizer(analyzer="word", ngram_range=(1, 2), sublinear_tf=True, min_df=1),
            # scikit-learn 1.5+ is multinomial by default for this solver, so
            # the confidence is a single softmax over intents rather than
            # per-class one-vs-rest. The `multi_class` argument is deprecated
            # and deliberately not passed.
            LogisticRegression(max_iter=2000, C=10.0, random_state=self.random_state),
        )
        self.model.fit(texts, targets)
        return self

    # -- confidence ----------------------------------------------------

    def _closed_set(self, utterances: Sequence[str]) -> tuple[list[str], list[float]]:
        """Intent predictions ignoring out-of-scope, with their confidence."""
        probabilities = self.model.predict_proba(utterances)
        classes = list(self.model.classes_)
        predictions: list[str] = []
        confidences: list[float] = []
        for row in probabilities:
            best = int(row.argmax())
            predictions.append(classes[best])
            confidences.append(float(row[best]))
        return predictions, confidences

    def tune(self, dev_cases: Sequence[dict]) -> ThresholdChoice:
        """Tune the out-of-scope threshold on development data only."""
        utterances = [case["utt"] for case in dev_cases]
        gold = [
            case["true_intent"] if case["in_scope"] else "none_of_the_above"
            for case in dev_cases
        ]
        predictions, confidences = self._closed_set(utterances)
        self.threshold_choice = tune_threshold(confidences, predictions, gold, self.labels)
        return self.threshold_choice

    # -- prediction ----------------------------------------------------

    def predict(self, cases: Sequence[dict]) -> list[Prediction]:
        if self.threshold_choice is None:
            raise ValueError("call tune() on development data before predicting")
        threshold = self.threshold_choice.threshold
        predictions, confidences = self._closed_set([case["utt"] for case in cases])

        out: list[Prediction] = []
        for case, intent, confidence in zip(cases, predictions, confidences):
            rejected = confidence < threshold
            out.append(
                Prediction(
                    case_id=case["case_id"],
                    status=STATUS_OOS if rejected else STATUS_OK,
                    intent=None if rejected else intent,
                    # No entity extraction: B0 is an intent classifier.
                    entities=[],
                    # Its output is constructed, not generated, so it always
                    # satisfies the contract.
                    schema_valid_raw=True,
                    schema_valid_final=True,
                )
            )
        return out

    def config(self) -> dict[str, Any]:
        return {
            "system": "B0",
            "description": "TF-IDF + multinomial logistic regression intent classifier",
            "extracts_entities": False,
            "model_calls": 0,
            "random_state": self.random_state,
            "threshold": self.threshold_choice.as_dict() if self.threshold_choice else None,
        }
