from __future__ import annotations

import json
import unittest

from social_report.sources.meta.usage import UsageTracker, parse_usage_headers, quota_health


class MetaUsageTest(unittest.TestCase):
    def test_absent_and_malformed_headers_are_unknown(self):
        tracker = UsageTracker()
        tracker.observe({"X-App-Usage": "not-json"})
        self.assertEqual(tracker.summary()["status"], "UNKNOWN")
        self.assertEqual(parse_usage_headers({}), {})

    def test_all_official_headers_are_sanitized_and_nested_usage_is_flattened(self):
        tracker = UsageTracker()
        tracker.observe(
            {
                "x-app-usage": json.dumps(
                    {"call_count": 72, "total_cputime": 12, "total_time": 15, "ignored": 999}
                ),
                "X-Ad-Account-Usage": json.dumps(
                    {
                        "acc_id_util_pct": 40,
                        "reset_time_duration": 9,
                        "ads_api_access_tier": "standard_access",
                        "account_id": "secret-account",
                    }
                ),
                "X-Business-Use-Case-Usage": json.dumps(
                    {
                        "private-business-id": [
                            {
                                "type": "ads_insights",
                                "call_count": 88,
                                "total_cputime": 4,
                                "total_time": 5,
                                "estimated_time_to_regain_access": 2,
                            }
                        ]
                    }
                ),
            }
        )
        summary = tracker.summary()
        self.assertEqual(summary["status"], "HIGH")
        self.assertEqual(summary["max_utilization_pct"], 88)
        self.assertEqual(summary["estimated_regain_seconds"], 120)
        rendered = json.dumps(summary)
        self.assertNotIn("private-business-id", rendered)
        self.assertNotIn("secret-account", rendered)
        self.assertNotIn("ignored", rendered)

    def test_project_thresholds_and_explicit_block(self):
        self.assertEqual(quota_health(None), "UNKNOWN")
        self.assertEqual(quota_health(69.9), "HEALTHY")
        self.assertEqual(quota_health(70), "ELEVATED")
        self.assertEqual(quota_health(85), "HIGH")
        self.assertEqual(quota_health(95), "CRITICAL")
        self.assertEqual(quota_health(1, blocked=True), "BLOCKED")


if __name__ == "__main__":
    unittest.main()
