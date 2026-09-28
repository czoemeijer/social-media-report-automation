#!/usr/bin/env python3
"""
test_calculate_metrics.py
Unit and integration tests for calculate_metrics.py script and end-to-end flow.
"""

import sys
import os
import unittest
import json
import subprocess

SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "skills", "social-report-audit", "scripts", "calculate_metrics.py"))


class TestScriptCLI(unittest.TestCase):

    def test_cli_single_item(self):
        input_data = {
            "creator": "Synthetic Creator",
            "platform": "instagram",
            "content_format": "reel",
            "reach": 10000,
            "likes": 420,
            "comments": 18,
            "shares": 32,
            "saves": 80,
            "scope": "organic"
        }
        proc = subprocess.run(
            [sys.executable, SCRIPT_PATH],
            input=json.dumps(input_data),
            capture_output=True,
            text=True,
            check=True
        )
        res = json.loads(proc.stdout)
        self.assertEqual(res["known_engagement_actions"], 550)
        self.assertAlmostEqual(res["calculated_er_by_reach"], 5.50, places=2)
        self.assertAlmostEqual(res["save_rate_pct"], 0.80, places=2)
        self.assertAlmostEqual(res["comment_to_like_ratio_pct"], 4.2857, places=2)

    def test_cli_campaign_batch(self):
        batch = [
            {"creator": "Creator 1", "reach": 5000, "likes": 200, "comments": 10, "shares": 5, "saves": 35},
            {"creator": "Creator 2", "reach": 8000, "likes": 350, "comments": 25, "shares": 15, "saves": 60}
        ]
        proc = subprocess.run(
            [sys.executable, SCRIPT_PATH],
            input=json.dumps(batch),
            capture_output=True,
            text=True,
            check=True
        )
        res = json.loads(proc.stdout)
        summary = res["campaign_summary"]
        self.assertEqual(summary["sum_of_content_reach"], 13000)
        # Total known actions: (200+10+5+35) + (350+25+15+60) = 250 + 450 = 700
        self.assertEqual(summary["total_known_engagement_actions"], 700)
        # Weighted ER: 700 / 13000 * 100 = 5.3846%
        self.assertAlmostEqual(summary["weighted_calculated_er_by_reach"], 5.3846, places=2)
        self.assertIn("audience overlap", summary["reach_aggregation_warning"])

    def test_missing_reach_unavailable(self):
        input_data = {
            "creator": "Incomplete Data",
            "likes": 50,
            "comments": 5,
            "shares": 1,
            "saves": 4,
            "reach": None
        }
        proc = subprocess.run(
            [sys.executable, SCRIPT_PATH],
            input=json.dumps(input_data),
            capture_output=True,
            text=True,
            check=True
        )
        res = json.loads(proc.stdout)
        self.assertEqual(res["known_engagement_actions"], 60)
        self.assertIsNone(res["calculated_er_by_reach"])


if __name__ == "__main__":
    unittest.main()
