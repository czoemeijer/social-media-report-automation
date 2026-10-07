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

    def test_schema_valid_wrong_numbers_scores_less_than_one(self):
        root = Path(__file__).resolve().parents[1]
        truth = json.loads(
            (root / "evals/fixtures/synthetic_campaign_001/ground_truth.json").read_text(
                encoding="utf-8"
            )
        )
        prediction = json.loads(
            (root / "evals/fixtures/synthetic_campaign_001/ground_truth.json").read_text(
                encoding="utf-8"
            )
        )
        # Modify numbers in prediction to be intentionally wrong while maintaining valid schema
        for asset in prediction["assets"]:
            if "reach" in asset["metrics"]:
                asset["metrics"]["reach"]["value"] = 999999
            if "likes" in asset["metrics"]:
                asset["metrics"]["likes"]["value"] = 123456

        scores = evaluate(prediction, truth)
        self.assertLess(scores["final_numerical_consistency"], 1.0)
        self.assertGreaterEqual(scores["final_numerical_consistency"], 0.0)


if __name__ == "__main__":
    unittest.main()
