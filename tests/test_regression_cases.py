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
        Views = 12,000, Saves = 6, Reach = cca 10,000, Likes = 300, Comments = 20, Shares = 4
        Known actions: 300 + 20 + 4 + 6 = 330
        Calculated ER by Reach: 330 / 10,000 * 100 = 3.30% (approximate)
        """
        item = {
            "creator": "Creator A",
            "platform": "facebook",
            "views": 12000,
            "likes": 300,
            "comments": 20,
            "shares": 4,
            "saves": 6,
            "reach": 10000,
            "reach_is_approximate": True,
            "scope": "organic"
        }
        res = calculate_single_item(item)
        self.assertEqual(res["known_engagement_actions"], 330)
        self.assertAlmostEqual(res["calculated_er_by_reach"], 3.3000, places=2)
        self.assertTrue(res["er_is_approximate"])

    def test_regression_case_2_instagram(self):
        """
        REGRESSION CASE 2 — Creator A — Instagram
        Views = 24,000, Saves = 30, Reach = 16,000, Likes = 1,125, Comments = 50, Shares = 5
        Known actions: 1,125 + 50 + 5 + 30 = 1,210
        Calculated ER: 1,210 / 16,000 * 100 = 7.56%
        Crucial check: Exact 1,125 must NOT be rounded down to 1,000 or 1,100!
        """
        item = {
            "creator": "Creator A",
            "platform": "instagram",
            "views": 24000,
            "likes": 1125,
            "comments": 50,
            "shares": 5,
            "saves": 30,
            "reach": 16000,
            "reach_is_approximate": False,
            "scope": "organic"
        }
        res = calculate_single_item(item)
        self.assertEqual(res["likes"], 1125)
        self.assertEqual(res["known_engagement_actions"], 1210)
        self.assertAlmostEqual(res["calculated_er_by_reach"], 7.5625, places=2)
        self.assertFalse(res["er_is_approximate"])

    def test_regression_case_3_creator_b(self):
        """
        REGRESSION CASE 3 — Creator B
        Likes = 140, Comments = 8, Shares = 2, Saves = 110, Reach = 7,500
        Known actions: 140 + 8 + 2 + 110 = 260
        Calculated ER: 260 / 7,500 * 100 ≈ 3.47%
        """
        item = {
            "creator": "Creator B",
            "platform": "instagram",
            "views": 12500,
            "likes": 140,
            "comments": 8,
            "shares": 2,
            "saves": 110,
            "reach": 7500,
            "scope": "organic"
        }
        res = calculate_single_item(item)
        self.assertEqual(res["known_engagement_actions"], 260)
        self.assertAlmostEqual(res["calculated_er_by_reach"], 3.4667, places=2)
        # Check save rate
        self.assertAlmostEqual(res["save_rate_pct"], 1.4667, places=2)

    def test_regression_case_4_creator_c_reel(self):
        """
        REGRESSION CASE 4 — Creator C — Reel
        Likes = 120, Comments = 4, Shares = 2, Saves = 54, Reach = 6,000
        Known actions: 120 + 4 + 2 + 54 = 180
        Calculated ER: 180 / 6,000 * 100 = 3.00%
        """
        item = {
            "creator": "Creator C",
            "platform": "instagram",
            "views": 10000,
            "likes": 120,
            "comments": 4,
            "shares": 2,
            "saves": 54,
            "reach": 6000,
            "scope": "organic"
        }
        res = calculate_single_item(item)
        self.assertEqual(res["known_engagement_actions"], 180)
        self.assertAlmostEqual(res["calculated_er_by_reach"], 3.0000, places=2)

    def test_regression_case_5_interaction_bug_prevention(self):
        """
        REGRESSION CASE 5 — Fix the Interaction Discrepancy Bug
        Likes = 1,600, Comments = 80, Shares = 12, Saves = 188
        Expected known engagement actions = 1,880.
        If platform reports 1,920, uncategorized interactions must equal 40.
        """
        item = {
            "creator": "Aggregated Content",
            "likes": 1600,
            "comments": 80,
            "shares": 12,
            "saves": 188,
            "reach": 45000,
            "platform_reported_interactions": 1920,
            "scope": "organic"
        }
        res = calculate_single_item(item)
        self.assertEqual(res["known_engagement_actions"], 1880)
        self.assertNotEqual(res["known_engagement_actions"], 1920)
        self.assertEqual(res["uncategorized_interactions"], 40)
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


class TestPostAuditRefinements(unittest.TestCase):
    """
    Regression tests for post-test audit refinements:
    - Incomplete engagement actions must not be presented as complete ER (lower bound only)
    - Ads disclaimer ("Insights include data from your post/reel and any ads") requires mixed_or_unknown scope
    - Absence of metric on screenshot is not equivalent to zero (null vs 0)
    - Feed-visible shares/reposts tracked separately from canonical Insights shares without overwriting
    - Exact reproduction and auditing of synthetic dual-asset retail campaign
    """

    def test_incomplete_engagement_actions_lower_bound(self):
        """
        When an engagement component (e.g. shares is None / unreadable / --) is missing:
        - calculated_er_by_reach MUST be None (never presented as complete)
        - er_is_complete must be False
        - er_status must be 'incomplete_lower_bound'
        - er_lower_bound_by_reach must provide the deterministic minimum
        - known_engagement_actions must report the sum of visible components
        """
        item = {
            "creator": "Synthetic Retail Hub",
            "reach": 1000,
            "likes": 80,
            "comments": 10,
            "saves": 10,
            "shares": None
        }
        res = calculate_single_item(item)
        self.assertEqual(res["known_engagement_actions"], 100)
        self.assertFalse(res["engagement_is_complete"])
        self.assertEqual(res["missing_engagement_components"], ["shares"])
        self.assertIsNone(res["calculated_er_by_reach"])
        self.assertFalse(res["er_is_complete"])
        self.assertEqual(res["er_status"], "incomplete_lower_bound")
        self.assertAlmostEqual(res["er_lower_bound_by_reach"], 10.00, places=2)
        self.assertTrue(any("Incomplete engagement components" in w for w in res.get("warnings", [])))

    def test_mixed_or_unknown_scope_via_ads_disclaimer(self):
        """
        If Instagram Insights displays 'Insights include data from your post/reel and any ads'
        without a separate Ad breakdown, scope must be classified as mixed_or_unknown
        and explicit warning regarding inseparable organic and paid contributions must be present.
        """
        item = {
            "creator": "Synthetic Brand Account",
            "has_ad_disclaimer": True,
            "likes": 50,
            "comments": 2,
            "shares": 1,
            "saves": 3,
            "reach": 1000
        }
        res = calculate_single_item(item)
        self.assertEqual(res["scope"], "mixed_or_unknown")
        self.assertTrue(any("cannot be separated" in w for w in res.get("warnings", [])))

    def test_absence_vs_zero_metric_preservation(self):
        """
        Absence of a metric line (e.g., Reel omitting External link taps) must remain None (unavailable),
        while an explicit zero (e.g., Business address taps: 0) must remain 0.
        """
        item = {
            "creator": "Synthetic Video Asset",
            "follows": 7,
            "external_link_taps": None,
            "business_address_taps": 0
        }
        res = calculate_single_item(item)
        self.assertIsNone(res.get("external_link_taps"))
        self.assertEqual(res.get("business_address_taps"), 0)
        self.assertEqual(res.get("follows"), 7)

    def test_feed_shares_separation_and_discrepancy(self):
        """
        Feed-visible send/share (paper plane = 5) and reposts (arrows = 2) must be preserved
        in distinct fields and must NOT overwrite canonical Insights shares (which is None / --).
        """
        item = {
            "creator": "Synthetic Video Asset",
            "likes": 800,
            "comments": 0,
            "saves": 10,
            "shares": None,
            "feed_shares": 5,
            "feed_reposts": 2,
            "reach": 8000
        }
        res = calculate_single_item(item)
        self.assertIsNone(res["shares"])
        self.assertEqual(res["feed_shares"], 5)
        self.assertEqual(res["feed_reposts"], 2)
        self.assertTrue(res["feed_vs_insights_shares_discrepancy"])
        # Canonical known actions must NOT silently include feed_shares
        self.assertEqual(res["known_engagement_actions"], 810)
        self.assertAlmostEqual(res["er_lower_bound_by_reach"], 10.1250, places=2)
        self.assertIsNone(res["calculated_er_by_reach"])

    def test_mixed_content_campaign_full_audit(self):
        """
        Full regression verification of the dual-asset retail campaign synthetic dataset:
        - Asset 1 (Static post 'Food Storage Guide'):
          Views: 4000, Reach: 1500, Likes: 120, Comments: 0, Saves: 5, Shares: None.
          Ad disclaimer: True -> scope: mixed_or_unknown.
          Known actions: 125, Lower bound ER: 8.3333%, Complete ER: None.
          External link taps: 15, Business address taps: 0.
        - Asset 2 (Reel 'Store Launch Announcement'):
          Views: 15000, Reach: 8000, Likes: 800, Comments: 0, Saves: 10, Shares: None.
          Feed shares: 5, Feed reposts: 2.
          Ad disclaimer: True -> scope: mixed_or_unknown.
          Known actions: 810, Lower bound ER: 10.1250%, Complete ER: None.
          External link taps: None (unavailable), Follows: 5.
        """
        post_item = {
            "id": "post_food_storage",
            "title": "Food Storage Guide (Static Graphic)",
            "content_format": "feed_post",
            "views": 4000,
            "reach": 1500,
            "likes": 120,
            "comments": 0,
            "saves": 5,
            "shares": None,
            "has_ad_disclaimer": True,
            "external_link_taps": 15,
            "profile_visits": 1,
            "business_address_taps": 0,
            "follows": 0
        }
        reel_item = {
            "id": "reel_store_launch",
            "title": "New Store Launch Announcement (Reel)",
            "content_format": "reel",
            "views": 15000,
            "reach": 8000,
            "likes": 800,
            "comments": 0,
            "saves": 10,
            "shares": None,
            "feed_shares": 5,
            "feed_reposts": 2,
            "has_ad_disclaimer": True,
            "external_link_taps": None,
            "follows": 5
        }

        res_post = calculate_single_item(post_item)
        self.assertEqual(res_post["scope"], "mixed_or_unknown")
        self.assertEqual(res_post["known_engagement_actions"], 125)
        self.assertIsNone(res_post["calculated_er_by_reach"])
        self.assertAlmostEqual(res_post["er_lower_bound_by_reach"], 8.3333, places=2)
        self.assertEqual(res_post["external_link_taps"], 15)
        self.assertEqual(res_post["business_address_taps"], 0)

        res_reel = calculate_single_item(reel_item)
        self.assertEqual(res_reel["scope"], "mixed_or_unknown")
        self.assertEqual(res_reel["known_engagement_actions"], 810)
        self.assertIsNone(res_reel["calculated_er_by_reach"])
        self.assertAlmostEqual(res_reel["er_lower_bound_by_reach"], 10.1250, places=2)
        self.assertIsNone(res_reel["external_link_taps"])
        self.assertEqual(res_reel["follows"], 5)
        self.assertEqual(res_reel["feed_shares"], 5)
        self.assertEqual(res_reel["feed_reposts"], 2)

        # Campaign aggregation
        agg = aggregate_campaign([post_item, reel_item])
        self.assertEqual(agg["total_views"], 19000)
        self.assertEqual(agg["sum_of_content_reach"], 9500)
        self.assertEqual(agg["total_likes"], 920)
        self.assertEqual(agg["total_comments"], 0)
        self.assertEqual(agg["total_saves"], 15)
        self.assertEqual(agg["total_known_engagement_actions"], 935)
        self.assertIsNone(agg["weighted_calculated_er_by_reach"])
        self.assertAlmostEqual(agg["weighted_er_lower_bound_by_reach"], 9.8421, places=2)
        self.assertEqual(agg["scope"], "mixed_or_unknown")
        self.assertFalse(agg["er_is_complete"])
        self.assertEqual(agg["er_status"], "incomplete_lower_bound")


if __name__ == "__main__":
    unittest.main()
