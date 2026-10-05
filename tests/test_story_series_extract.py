import os
import sys
import json
import unittest
import importlib.util
import subprocess

SCRIPT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "skills", "story-series-extract", "scripts", "extract_story_series.py"))

spec = importlib.util.spec_from_file_location("extract_story_series", SCRIPT_PATH)
mod = importlib.util.module_from_spec(spec)
sys.modules["extract_story_series"] = mod
spec.loader.exec_module(mod)

extract_story_series_summary = mod.extract_story_series_summary


class TestStorySeriesExtract(unittest.TestCase):
    def test_sample_story_series(self):
        sample_data = {
            "campaign": "FreshBite – Letní smoothie výzva",
            "stories": [
                {
                    "views": 320,
                    "reach": 250,
                    "interactions": 12,
                    "profile_visits": 4,
                },
                {
                    "views": 280,
                    "reach": 210,
                    "interactions": 8,
                    "profile_visits": 2,
                    "poll_result": "ovocné 65 % / zeleninové 35 %",
                },
            ],
        }
        res = extract_story_series_summary(sample_data)
        self.assertEqual(res["total_views"], 600)
        self.assertEqual(res["views_breakdown"], "600 (320 + 280)")
        self.assertEqual(res["reach_str"], "250 - maximální dosah na začátku série")
        self.assertEqual(res["profile_visits"], 6)
        self.assertEqual(res["total_interactions"], 20)
        self.assertEqual(res["interactions_breakdown"], "20 (12 + 8)")
        self.assertEqual(res["drop_off_rate_str"], "16,0 %")
        self.assertEqual(res["poll_result"], "ovocné 65 % / zeleninové 35 %")

        expected_markdown = (
            "Souhrnný výkon série\n"
            "Zobrazení: 600 (320 + 280)\n"
            "Reach: 250 - maximální dosah na začátku série\n"
            "Návštěvy profilu: 6\n"
            "Interakce: 20 (12 + 8)\n"
            "Míra opuštění: 16,0 %\n"
            "Výsledek ankety/kvízu: ovocné 65 % / zeleninové 35 %"
        )
        self.assertEqual(res["markdown"], expected_markdown)

    def test_synthetic_series_with_quiz(self):
        user_data = {
            "stories": [
                {
                    "views": 450,
                    "reach": 380,
                    "interactions": 15,
                    "profile_visits": 3,
                },
                {
                    "views": 390,
                    "reach": 304,
                    "interactions": 10,
                    "profile_visits": 1,
                    "poll_result": "88 % zvolilo správnou odpověď",
                },
            ],
            "drop_off_rate": "20,0 %",
        }
        res = extract_story_series_summary(user_data)
        self.assertEqual(res["total_views"], 840)
        self.assertEqual(res["views_breakdown"], "840 (450 + 390)")
        self.assertEqual(res["reach_str"], "380 - maximální dosah na začátku série")
        self.assertEqual(res["profile_visits"], 4)
        self.assertEqual(res["total_interactions"], 25)
        self.assertEqual(res["interactions_breakdown"], "25 (15 + 10)")
        self.assertEqual(res["drop_off_rate_str"], "20,0 %")
        self.assertEqual(res["poll_result"], "88 % zvolilo správnou odpověď")


if __name__ == "__main__":
    unittest.main()
