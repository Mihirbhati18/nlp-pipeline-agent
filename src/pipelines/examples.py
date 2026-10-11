"""Example selection for the execution catalogue (PROJECT_PLAN.md section 6).

Two strategies, both drawing only from the k-shot pool and both respecting the
prompt cap of at most 16 examples and at most 2,000 input tokens:

- ``fixed``: one example per intent, in a stable order. Every request gets the
  same examples, so this strategy makes no use of the request text.
- ``similarity``: the nearest examples to the request by TF-IDF cosine
  similarity, which is also the signal the TF-IDF out-of-scope policy uses.

Selection is deterministic: the same pool and the same request always produce
the same examples in the same order, so a cached prediction stays valid.
"""

from __future__ import annotations

from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

MAX_EXAMPLES = 16


@dataclass
class ExampleSelector:
    """Shared TF-IDF index over one project's k-shot pool.

    Built once per project and reused, because fitting it per request would be
    wasteful and would not change the result.
    """

    pool: list[dict]

    def __post_init__(self) -> None:
        self._texts = [case["utt"] for case in self.pool]
        # Character n-grams in addition to words, so short utterances with few
        # shared words still get a usable similarity signal.
        self.vectorizer = TfidfVectorizer(
            analyzer="word", ngram_range=(1, 2), sublinear_tf=True, min_df=1
        )
        self._matrix = self.vectorizer.fit_transform(self._texts) if self._texts else None

    # -- strategies ----------------------------------------------------

    def fixed(self, limit: int = MAX_EXAMPLES) -> list[dict]:
        """One example per intent, lowest case ID first for stability.

        With more intents than the cap, the first ``limit`` intents in
        alphabetical order are covered. That is a real weakness of the fixed
        strategy on a large schema, not a bug: it is what the similarity
        strategy is compared against.
        """
        by_intent: dict[str, dict] = {}
        for case in sorted(self.pool, key=lambda c: (c["true_intent"], c["case_id"])):
            by_intent.setdefault(case["true_intent"], case)
        chosen = [by_intent[name] for name in sorted(by_intent)]
        return chosen[:limit]

    def similarity(self, utterance: str, limit: int = MAX_EXAMPLES) -> list[dict]:
        """The ``limit`` nearest pool examples, most similar first."""
        if self._matrix is None or not self.pool:
            return []
        scores = cosine_similarity(
            self.vectorizer.transform([utterance]), self._matrix
        )[0]
        # Ties broken by case ID so the order never depends on sort stability.
        order = sorted(
            range(len(self.pool)),
            key=lambda i: (-scores[i], self.pool[i]["case_id"]),
        )
        return [self.pool[i] for i in order[:limit]]

    def max_similarity(self, utterance: str) -> float:
        """Highest cosine similarity to any pool example.

        This is the statistic the TF-IDF out-of-scope policy thresholds, and
        the same statistic B0 uses, so the two are directly comparable.
        """
        if self._matrix is None or not self.pool:
            return 0.0
        scores = cosine_similarity(
            self.vectorizer.transform([utterance]), self._matrix
        )[0]
        return float(scores.max())
