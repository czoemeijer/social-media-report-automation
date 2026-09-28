#!/usr/bin/env python3
"""
test_regression_cases.py
Automated regression and audit test suite for social-report-audit.
Tests all regression cases and edge cases defined in project specifications
using anonymized creator identifiers to protect privacy.
"""

import sys
import os
import unittest

# Add script directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "skills", "social-report-audit", "scripts")))

from calculate_metrics import calculate_single_item, aggregate_campaign


class TestRegressionCases(unittest.TestCase):

    def test_regression_case_1_facebook(self):
        """
        REGRESSION CASE 1 — Creator A — Facebook
        Views = 15,020, Saves = 9, Reach = cca 11,500, Likes = 398, Comments = 28, Shares = 2
        Known actions: 398 + 28 + 2 + 9 = 437
        Calculated ER by Reach: 437 / 11,500 * 100 ≈ 3.80% (approximate)
        """
        item = {
            "creator": "Creator A",
            "platform": "facebook",
            "views": 15020,
            "likes": 398,
            "comments": 28,
            "shares": 2,
            "saves": 9,
            "reach": 11500,
            "reach_is_approximate": True,
            "scope": "organic"
        }
        res = calculate_single_item(item)
        self.assertEqual(res["known_engagement_actions"], 437)
        self.assertAlmostEqual(res["calculated_er_by_reach"], 3.8000, places=2)
        self.assertTrue(res["er_is_approximate"])

    def test_regression_case_2_instagram(self):
        """
        REGRESSION CASE 2 — Creator A — Instagram
        Views = 26,437, Saves = 39, Reach = 17,664, Likes = 1,225, Comments = 64, Shares = 3
        Known actions: 1,225 + 64 + 3 + 39 = 1,331
        Calculated ER: 1,331 / 17,664 * 100 ≈ 7.53%
        Crucial check: Exact 1,225 must NOT be rounded down to 1,100!
        """
        item = {
            "creator": "Creator A",
            "platform": "instagram",
            "views": 26437,
            "likes": 1225,
            "comments": 64,
            "shares": 3,
            "saves": 39,
            "reach": 17664,
            "reach_is_approximate": False,
            "scope": "organic"
        }
        res = calculate_single_item(item)
        self.assertEqual(res["likes"], 1225)
        self.assertEqual(res["known_engagement_actions"], 1331)
        self.assertAlmostEqual(res["calculated_er_by_reach"], 7.5348, places=2)
        self.assertFalse(res["er_is_approximate"])

    def test_regression_case_3_creator_b(self):
        """
        REGRESSION CASE 3 — Creator B
        Likes = 130, Comments = 6, Shares = 3, Saves = 111, Reach = 7,563
        Known actions: 130 + 6 + 3 + 111 = 250
        Calculated ER: 250 / 7,563 * 100 ≈ 3.31%
        """
        item = {
            "creator": "Creator B",
            "platform": "instagram",
            "views": 13029,
            "likes": 130,
            "comments": 6,
            "shares": 3,
            "saves": 111,
            "reach": 7563,
            "scope": "organic"
        }
        res = calculate_single_item(item)
        self.assertEqual(res["known_engagement_actions"], 250)
        self.assertAlmostEqual(res["calculated_er_by_reach"], 3.3056, places=2)
        # Check save rate
        self.assertAlmostEqual(res["save_rate_pct"], 1.4677, places=2)

    def test_regression_case_4_creator_c_reel(self):
        """
        REGRESSION CASE 4 — Creator C — Reel
        Likes = 123, Comments = 2, Shares = 2, Saves = 49, Reach = 6,402
        Known actions: 123 + 2 + 2 + 49 = 176
        Calculated ER: 176 / 6,402 * 100 ≈ 2.75%
        """
        item = {
            "creator": "Creator C",
            "platform": "instagram",
            "views": 11405,
            "likes": 123,
            "comments": 2,
            "shares": 2,
            "saves": 49,
            "reach": 6402,
            "scope": "organic"
        }
        res = calculate_single_item(item)
        self.assertEqual(res["known_engagement_actions"], 176)
        self.assertAlmostEqual(res["calculated_er_by_reach"], 2.7491, places=2)

    def test_regression_case_5_interaction_bug_prevention(self):
        """
        REGRESSION CASE 5 — Fix the 2,071 vs 2,107 Interaction Bug
        Likes = 1,753, Comments = 100, Shares = 10, Saves = 208
        Expected known engagement actions = 2,071 (NOT 2,107).
        If platform reports 2,107, uncategorized interactions must equal 36.
        """
        item = {
            "creator": "Aggregated Content",
            "likes": 1753,
            "comments": 100,
            "shares": 10,
            "saves": 208,
            "reach": 52280,
            "platform_reported_interactions": 2107,
            "scope": "organic"
        }
        res = calculate_single_item(item)
        self.assertEqual(res["known_engagement_actions"], 2071)
        self.assertNotEqual(res["known_engagement_actions"], 2107)
        self.assertEqual(res["uncategorized_interactions"], 36)
        self.assertTrue(res["interaction_discrepancy"])


class TestEdgeCasesAndSafety(unittest.TestCase):

    def test_missing_reach(self):
        item = {"likes": 100, "comments": 10, "shares": 5, "saves": 10, "reach": None}
        res = calculate_single_item(item)
        self.assertIsNone(res["calculated_er_by_reach"])

    def test_zero_reach(self):
        item = {"likes": 100, "comments": 10, "shares": 5, "saves": 10, "reach": 0}
        res = calculate_single_item(item)
        self.assertIsNone(res["calculated_er_by_reach"])

    def test_zero_likes(self):
        item = {"likes": 0, "comments": 5, "shares": 2, "saves": 3, "reach": 1000}
        res = calculate_single_item(item)
        self.assertEqual(res["known_engagement_actions"], 10)
        self.assertIsNone(res["comment_to_like_ratio_pct"])

    def test_paid_scope_warning(self):
        item = {"likes": 50, "comments": 2, "shares": 1, "saves": 4, "reach": 50000, "scope": "paid"}
        res = calculate_single_item(item)
        self.assertTrue(any("Paid scope detected" in w for w in res.get("warnings", [])))

    def test_campaign_aggregation_warning(self):
        items = [
            {"creator": "A", "likes": 100, "comments": 10, "shares": 5, "saves": 10, "reach": 2000},
            {"creator": "B", "likes": 200, "comments": 20, "shares": 10, "saves": 20, "reach": 3000},
        ]
        agg = aggregate_campaign(items)
        self.assertEqual(agg["sum_of_content_reach"], 5000)
        self.assertIn("audience overlap", agg["reach_aggregation_warning"])
        self.assertAlmostEqual(agg["weighted_calculated_er_by_reach"], 7.50, places=2)


if __name__ == "__main__":
    unittest.main()
