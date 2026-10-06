from __future__ import annotations

import unittest

from social_report.dedup import classify_hash_relationship
from social_report.metrics import aggregate_campaign, calculate_single_item
from social_report.stories import summarize_story_series
from social_report.validation import validate_extraction


class CoreSemanticsTest(unittest.TestCase):
    def test_scope_defaults_to_unknown(self):
        result = calculate_single_item(
            {"reach": 100, "likes": 1, "comments": 0, "shares": 0, "saves": 0}
        )
        self.assertEqual(result["scope"], "unknown")

    def test_paid_and_organic_are_separate(self):
        result = aggregate_campaign(
            [
                {
                    "scope": "organic",
                    "reach": 100,
                    "likes": 10,
                    "comments": 0,
                    "shares": 0,
                    "saves": 0,
                },
                {
                    "scope": "paid",
                    "reach": 1000,
                    "likes": 100,
                    "comments": 0,
                    "shares": 0,
                    "saves": 0,
                },
            ]
        )
        self.assertEqual(result["scope_buckets"]["organic"]["sum_of_content_reach"], 100)
        self.assertEqual(result["scope_buckets"]["paid"]["sum_of_content_reach"], 1000)
        self.assertIsNone(result["weighted_calculated_er_by_reach"])

    def test_negative_interaction_discrepancy_is_not_uncategorized(self):
        result = calculate_single_item(
            {
                "scope": "organic",
                "reach": 100,
                "likes": 10,
                "comments": 2,
                "shares": 1,
                "saves": 1,
                "platform_reported_interactions": 12,
            }
        )
        self.assertEqual(result["interaction_discrepancy_value"], -2)
        self.assertIsNone(result["uncategorized_interactions"])

    def test_missing_and_zero_measurements_are_distinct(self):
        validated = validate_extraction(
            {
                "asset_group_id": "asset_1",
                "scope": "unknown",
                "metrics": {
                    "shares": {"value": None, "precision": "missing"},
                    "comments": {"value": 0, "precision": "exact"},
                },
            }
        )
        metrics = validated["assets"][0]["metrics"]
        self.assertIsNone(metrics["shares"]["value"])
        self.assertEqual(metrics["comments"]["value"], 0)

    def test_low_confidence_requests_review(self):
        result = validate_extraction(
            {
                "asset_group_id": "asset_1",
                "scope": "unknown",
                "metrics": {
                    "shares": {
                        "value": 5,
                        "precision": "exact",
                        "confidence": 0.5,
                        "source_file": "a.png",
                    }
                },
            }
        )
        self.assertEqual(result["review_status"], "needs_review")

    def test_story_missing_does_not_become_zero(self):
        result = summarize_story_series(
            {"stories": [{"views": 100, "reach": 90}, {"views": None, "reach": 80}]}
        )
        self.assertEqual(result["total_views"], 100)
        self.assertIn("lower bound", result["warnings"][0])

    def test_story_incompatible_snapshots_disable_drop_off(self):
        result = summarize_story_series(
            {
                "stories": [
                    {"reach": 100, "snapshot_stage": "final"},
                    {"reach": 80, "snapshot_stage": "4h"},
                ]
            }
        )
        self.assertIsNone(result["drop_off_rate_pct"])
        self.assertFalse(result["temporally_comparable"])

    def test_story_reach_increase_is_not_clamped(self):
        result = summarize_story_series({"stories": [{"reach": 80}, {"reach": 100}]})
        self.assertIsNone(result["drop_off_rate_pct"])
        self.assertTrue(any("exceeds" in warning for warning in result["warnings"]))

    def test_hash_relationships(self):
        self.assertEqual(classify_hash_relationship("a" * 64, "a" * 64), "exact_duplicate")
        self.assertEqual(
            classify_hash_relationship("a" * 64, "b" * 64, "0000000000000000", "0000000000000001"),
            "near_duplicate",
        )


if __name__ == "__main__":
    unittest.main()
