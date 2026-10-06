from __future__ import annotations

import json
import unittest
from pathlib import Path

from evals.evaluate import evaluate


class EvaluationTest(unittest.TestCase):
    def test_perfect_fixture_scores_one(self):
        root = Path(__file__).resolve().parents[1]
        truth = json.loads(
            (root / "evals/fixtures/synthetic_campaign_001/ground_truth.json").read_text(
                encoding="utf-8"
            )
        )
        scores = evaluate(truth, truth)
        for name in (
            "field_extraction_accuracy",
            "exact_number_fidelity",
            "null_vs_zero_accuracy",
            "scope_classification_accuracy",
            "asset_grouping_pairwise_f1",
            "story_grouping_accuracy",
            "final_numerical_consistency",
        ):
            self.assertEqual(scores[name], 1.0, name)


if __name__ == "__main__":
    unittest.main()
