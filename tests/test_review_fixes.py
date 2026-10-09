from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from social_report.intake import match_asset_files
from social_report.metrics import audit_campaign, calculate_single_item
from social_report.reporting import export_csv, export_markdown, sanitize_csv_cell
from social_report.stories import _diff_hours, summarize_story_series
from social_report.validation import merge_review_status, validate_extraction


class MockFile:
    def __init__(self, filename: str):
        self.filename = filename


class ReviewFixesRegressionTest(unittest.TestCase):
    """Exhaustive regression suite for the 10 Copilot review findings."""

    # -------------------------------------------------------------------------
    # Finding 1: Ambiguous Basename Matching & Transport-Safe File Selection
    # -------------------------------------------------------------------------
    def test_select_asset_files_hierarchy_and_ambiguity_rejection(self):
        files = [
            MockFile("sr_111111111111__campaign_alice_screen.png"),
            MockFile("sr_222222222222__campaign_bob_screen.png"),
            MockFile("sr_333333333333__campaign_alice_unique.png"),
        ]

        # 1. Exact path matches specific file via transport name
        matched_alice = match_asset_files(files, ["campaign/alice/screen.png"])
        self.assertEqual(len(matched_alice), 1)
        self.assertEqual(matched_alice[0].filename, "sr_111111111111__campaign_alice_screen.png")

        # 2. Ambiguous basename matching raises deterministic ValueError
        with self.assertRaisesRegex(ValueError, "ambiguous file reference 'screen.png'"):
            match_asset_files(files, ["screen.png"])

        # 3. Unambiguous unique filename matches cleanly
        matched_unique = match_asset_files(files, ["unique.png"])
        self.assertEqual(len(matched_unique), 1)
        self.assertEqual(matched_unique[0].filename, "sr_333333333333__campaign_alice_unique.png")

    # -------------------------------------------------------------------------
    # Finding 3 & 5: Review-Status Propagation Invariant (Severity Lattice)
    # -------------------------------------------------------------------------
    def test_merge_review_status_severity_lattice(self):
        # verified < verified_with_warning < needs_review < rejected
        self.assertEqual(merge_review_status("verified"), "verified")
        self.assertEqual(merge_review_status("verified", "verified_with_warning"), "verified_with_warning")
        self.assertEqual(merge_review_status("verified_with_warning", "needs_review"), "needs_review")
        self.assertEqual(merge_review_status("needs_review", "rejected"), "rejected")
        self.assertEqual(merge_review_status("rejected", "verified"), "rejected")
        self.assertEqual(merge_review_status("rejected", "needs_review", "verified_with_warning"), "rejected")
        self.assertEqual(merge_review_status("verified", "verified"), "verified")

    def test_review_status_propagation_in_calculation_and_audit(self):
        # 1. rejected asset with calculation warning remains rejected
        item_rejected = calculate_single_item(
            {
                "asset_group_id": "r1",
                "likes": 100,
                "comments": 10,
                "shares": 5,
                "saves": 2,
                "reach": 50,  # interactions (117) > reach (50) -> triggers warning
                "review_status": "rejected",
            }
        )
        self.assertEqual(item_rejected["review_status"], "rejected")
        self.assertTrue(len(item_rejected["warnings"]) > 0)

        # 2. needs_review asset without calculation warning remains needs_review
        item_nr_no_warn = calculate_single_item(
            {
                "asset_group_id": "nr1",
                "likes": 10,
                "comments": 1,
                "shares": 1,
                "saves": 1,
                "reach": 1000,
                "review_status": "needs_review",
            }
        )
        self.assertEqual(item_nr_no_warn["review_status"], "needs_review")

        # 3. verified asset with calculation warning becomes verified_with_warning
        item_verified_warn = calculate_single_item(
            {
                "asset_group_id": "vw1",
                "likes": 100,
                "comments": 10,
                "shares": 5,
                "saves": 2,
                "reach": 50,  # warning triggered
                "review_status": "verified",
            }
        )
        self.assertEqual(item_verified_warn["review_status"], "verified_with_warning")

        # 4. Campaign audit preserves rejected status at aggregate level
        campaign = {
            "assets": [
                {
                    "asset_group_id": "a1",
                    "platform": "instagram",
                    "content_format": "post",
                    "scope": "organic",
                    "review_status": "rejected",
                    "metrics": {
                        "reach": {"value": 1000, "precision": "exact"},
                        "likes": {"value": 50, "precision": "exact"},
                        "comments": {"value": 5, "precision": "exact"},
                        "shares": {"value": 2, "precision": "exact"},
                        "saves": {"value": 1, "precision": "exact"},
                    },
                },
                {
                    "asset_group_id": "a2",
                    "platform": "instagram",
                    "content_format": "post",
                    "scope": "organic",
                    "review_status": "verified",
                    "metrics": {
                        "reach": {"value": 1000, "precision": "exact"},
                        "likes": {"value": 50, "precision": "exact"},
                        "comments": {"value": 5, "precision": "exact"},
                        "shares": {"value": 2, "precision": "exact"},
                        "saves": {"value": 1, "precision": "exact"},
                    },
                },
            ]
        }
        audited = audit_campaign(campaign)
        self.assertEqual(audited["review_status"], "rejected")
        self.assertEqual(audited["items"][0]["review_status"], "rejected")
        self.assertEqual(audited["items"][1]["review_status"], "verified")

    def test_markdown_report_displays_warning_for_needs_review_and_rejected(self):
        # Needs review banner
        md_nr = export_markdown({"review_status": "needs_review", "warnings": ["low confidence"]}).decode("utf-8")
        self.assertIn("NEEDS_REVIEW", md_nr)

        # Rejected banner
        md_rej = export_markdown({"review_status": "rejected", "warnings": ["conflicting data"]}).decode("utf-8")
        self.assertIn("REJECTED", md_rej)

        # Verified has no warning banner
        md_ok = export_markdown({"review_status": "verified", "warnings": []}).decode("utf-8")
        self.assertNotIn("NEEDS_REVIEW", md_ok)
        self.assertNotIn("REJECTED", md_ok)

    # -------------------------------------------------------------------------
    # Finding 4 & 6: CSV Formula Injection Prevention
    # -------------------------------------------------------------------------
    def test_sanitize_csv_cell(self):
        dangerous_inputs = [
            "=HYPERLINK('http://malicious.com')",
            "+SUM(A1:A10)",
            "-1+1",
            "@SUM(B1:B10)",
            "\t=cmd|' /C calc'!A0",
            "\r=cmd|' /C calc'!A0",
            "\n=cmd|' /C calc'!A0",
            "   =SUM(1, 2)",
            "  +12345",
            "  -secret",
            "  @mention",
        ]
        for payload in dangerous_inputs:
            sanitized = sanitize_csv_cell(payload)
            self.assertTrue(
                sanitized.startswith("'"),
                f"Payload {payload!r} was not prefixed with single quote: {sanitized!r}",
            )

        # Safe inputs remain unchanged
        self.assertEqual(sanitize_csv_cell("normal text"), "normal text")
        self.assertEqual(sanitize_csv_cell("123"), "123")
        self.assertEqual(sanitize_csv_cell(42), 42)
        self.assertIsNone(sanitize_csv_cell(None))

    def test_export_csv_escapes_injected_formulas_without_mutating_json(self):
        audit_payload = {
            "campaign": "=HYPERLINK('http://evil.com', 'campaign')",
            "creator": "+SUM(1,2)",
            "client": "-cmd|' /C calc'!A0",
            "assets": [
                {
                    "asset_group_id": "@EVIL",
                    "platform": "instagram",
                    "content_format": "post",
                    "scope": "organic",
                    "creator": "=1+1",
                    "review_status": "verified",
                    "metrics": {
                        "reach": {"value": 1000},
                        "likes": {"value": 100},
                    },
                    "calculations": {
                        "calculated_er_by_reach": 0.1,
                    },
                    "warnings": [],
                }
            ],
        }
        csv_str = export_csv(audit_payload).decode("utf-8")
        self.assertIn("'=1+1", csv_str)
        self.assertIn("'@EVIL", csv_str)
        # Verify original JSON structure was not mutated
        self.assertEqual(audit_payload["campaign"], "=HYPERLINK('http://evil.com', 'campaign')")
        self.assertEqual(audit_payload["creator"], "+SUM(1,2)")
        self.assertEqual(audit_payload["assets"][0]["creator"], "=1+1")

    # -------------------------------------------------------------------------
    # Finding 7: Targeted Second Pass Preservation & Filtering
    # -------------------------------------------------------------------------
    def test_targeted_second_pass_filters_and_merges(self):
        # Test campaign with 20 assets, exactly 1 needing review
        assets = []
        for i in range(20):
            status = "needs_review" if i == 7 else "verified"
            assets.append({
                "asset_group_id": f"asset_{i}",
                "review_status": status,
                "metrics": {"reach": {"value": 1000, "precision": "exact"}},
            })
        campaign = {"assets": assets}

        # 1. filter_review_assets code logic
        review_assets = [
            a for a in campaign.get("assets", [])
            if a.get("review_status") in ("needs_review", "rejected")
        ]
        self.assertEqual(len(review_assets), 1)
        self.assertEqual(review_assets[0]["asset_group_id"], "asset_7")

        # 2. merge_reviewed_assets code logic
        corrected_assets = [
            {
                "asset_group_id": "asset_7",
                "review_status": "verified",
                "metrics": {"reach": {"value": 1500, "precision": "exact"}},
            }
        ]
        corrected_map = {a["asset_group_id"]: a for a in corrected_assets}
        merged = []
        for a in campaign["assets"]:
            gid = a["asset_group_id"]
            if gid in corrected_map:
                merged.append(corrected_map[gid])
            else:
                merged.append(a)

        self.assertEqual(len(merged), 20)
        # The 19 untouched assets are identical objects
        for i in range(20):
            if i == 7:
                self.assertEqual(merged[i]["review_status"], "verified")
                self.assertEqual(merged[i]["metrics"]["reach"]["value"], 1500)
            else:
                self.assertIs(merged[i], assets[i])

    # -------------------------------------------------------------------------
    # Finding 8 & 10: Precision Propagation Invariant
    # -------------------------------------------------------------------------
    def test_engagement_rate_precision_propagation(self):
        # 1. If reach is exact, but likes is approximate -> ER is approximate
        item_approx_likes = calculate_single_item(
            {
                "asset_group_id": "p1",
                "likes": 100,
                "comments": 10,
                "shares": 5,
                "saves": 2,
                "reach": 1000,
                "likes_is_approximate": True,
                "reach_is_approximate": False,
            }
        )
        self.assertTrue(item_approx_likes["er_is_approximate"])

        # 2. If comments is approximate -> ER is approximate
        item_approx_comments = calculate_single_item(
            {
                "asset_group_id": "p2",
                "likes": 100,
                "comments": 10,
                "shares": 5,
                "saves": 2,
                "reach": 1000,
                "comments_is_approximate": True,
                "reach_is_approximate": False,
            }
        )
        self.assertTrue(item_approx_comments["er_is_approximate"])

        # 3. If shares is approximate -> ER is approximate
        item_approx_shares = calculate_single_item(
            {
                "asset_group_id": "p3",
                "likes": 100,
                "comments": 10,
                "shares": 5,
                "saves": 2,
                "reach": 1000,
                "shares_is_approximate": True,
                "reach_is_approximate": False,
            }
        )
        self.assertTrue(item_approx_shares["er_is_approximate"])

        # 4. If saves is approximate -> ER is approximate and save rate is approximate
        item_approx_saves = calculate_single_item(
            {
                "asset_group_id": "p4",
                "likes": 100,
                "comments": 10,
                "shares": 5,
                "saves": 2,
                "reach": 1000,
                "saves_is_approximate": True,
                "reach_is_approximate": False,
            }
        )
        self.assertTrue(item_approx_saves["er_is_approximate"])
        self.assertTrue(item_approx_saves["save_rate_is_approximate"])

        # 5. Comment to like ratio is approximate if comments or likes approximate
        self.assertTrue(item_approx_likes["comment_to_like_ratio_is_approximate"])
        self.assertTrue(item_approx_comments["comment_to_like_ratio_is_approximate"])

        # 6. Completely exact item -> exact ER
        item_exact = calculate_single_item(
            {
                "asset_group_id": "p5",
                "likes": 100,
                "comments": 10,
                "shares": 5,
                "saves": 2,
                "reach": 1000,
                "reach_is_approximate": False,
                "likes_is_approximate": False,
                "comments_is_approximate": False,
                "shares_is_approximate": False,
                "saves_is_approximate": False,
            }
        )
        self.assertFalse(item_exact["er_is_approximate"])
        self.assertFalse(item_exact["save_rate_is_approximate"])
        self.assertFalse(item_exact["comment_to_like_ratio_is_approximate"])

    def test_bucket_weighted_er_precision_propagation(self):
        # Campaign with one exact asset and one approximate asset
        campaign = {
            "assets": [
                {
                    "asset_group_id": "b1",
                    "platform": "instagram",
                    "content_format": "post",
                    "scope": "organic",
                    "review_status": "verified",
                    "metrics": {
                        "reach": {"value": 1000, "precision": "exact"},
                        "likes": {"value": 50, "precision": "exact"},
                        "comments": {"value": 10, "precision": "exact"},
                        "shares": {"value": 5, "precision": "exact"},
                        "saves": {"value": 2, "precision": "exact"},
                    },
                },
                {
                    "asset_group_id": "b2",
                    "platform": "instagram",
                    "content_format": "post",
                    "scope": "organic",
                    "review_status": "verified",
                    "metrics": {
                        "reach": {"value": 1000, "precision": "exact"},
                        "likes": {"value": 50, "precision": "approximate"},
                        "comments": {"value": 10, "precision": "exact"},
                        "shares": {"value": 5, "precision": "exact"},
                        "saves": {"value": 2, "precision": "exact"},
                    },
                },
            ]
        }
        audited = audit_campaign(campaign)
        organic_bucket = audited["campaign_summary"]["scope_buckets"]["organic"]
        # Bucket weighted ER must be approximate because asset b2 has approximate likes
        self.assertTrue(organic_bucket["weighted_er_is_approximate"])

    # -------------------------------------------------------------------------
    # Finding 9 & 11: Story Datetime Safety
    # -------------------------------------------------------------------------
    def test_story_datetime_timezone_safety(self):
        # 1. aware + aware same timezone: diff computed without error
        t1 = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc)
        diff = _diff_hours(t2, t1)
        self.assertEqual(diff, 2.0)

        # 2. aware + aware different timezone offsets: diff computed without error
        tz_plus2 = timezone(timedelta(hours=2))
        t3 = datetime(2026, 10, 1, 16, 0, tzinfo=tz_plus2)  # 14:00 UTC
        diff_tz = _diff_hours(t3, t1)
        self.assertEqual(diff_tz, 2.0)

        # 3. naive + naive: diff computed without error
        t_naive1 = datetime(2026, 10, 1, 12, 0)
        t_naive2 = datetime(2026, 10, 1, 15, 0)
        diff_naive = _diff_hours(t_naive2, t_naive1)
        self.assertEqual(diff_naive, 3.0)

        # 4. aware + naive: DOES NOT RAISE TypeError, returns None from _diff_hours
        diff_mixed = _diff_hours(t2, t_naive1)
        self.assertIsNone(diff_mixed)

        # 5. summarize_story_series with mixed aware + naive does not raise TypeError
        mixed_series = {
            "stories": [
                {
                    "publication_time": "2026-10-01T12:00:00+00:00",
                    "capture_time": "2026-10-01T14:00:00+00:00",
                    "views": 1000,
                },
                {
                    "publication_time": "2026-10-01T13:00:00",  # naive
                    "capture_time": "2026-10-01T15:00:00",  # naive
                    "views": 800,
                },
            ]
        }
        res_mixed = summarize_story_series(mixed_series)
        self.assertFalse(res_mixed["temporally_comparable"])
        self.assertIsNone(res_mixed["drop_off_rate_pct"])
        self.assertTrue(any("mixed" in w.lower() for w in res_mixed["warnings"]))

    def test_validate_extraction_unsupported_review_status_normalized(self):
        payload = {
            "assets": [
                {
                    "asset_group_id": "asset_1",
                    "platform": "instagram",
                    "content_format": "post",
                    "scope": "organic",
                    "review_status": "unknown",
                    "metrics": {
                        "reach": {"value": 100, "precision": "exact"},
                    },
                }
            ]
        }
        res = validate_extraction(payload)
        self.assertEqual(res["assets"][0]["review_status"], "needs_review")
        self.assertTrue(any("unsupported review_status 'unknown'" in w for w in res["warnings"]))
        self.assertEqual(res["review_status"], "needs_review")

    def test_validate_extraction_string_metrics_and_key_normalization(self):
        payload = {
            "assets": [
                {
                    "asset_group_id": "asset_str",
                    "platform": "instagram",
                    "content_format": "post",
                    "scope": "organic",
                    "review_status": "verified",
                    "metrics": {
                        "Profile visits": 12,
                        "views": "1.2k",
                        "reach": "1,100",
                        "likes": 640,
                    },
                }
            ]
        }
        res = validate_extraction(payload)
        metrics = res["assets"][0]["metrics"]
        self.assertIn("profile_visits", metrics)
        self.assertEqual(metrics["profile_visits"]["value"], 12)
        self.assertEqual(metrics["profile_visits"]["precision"], "exact")
        self.assertEqual(metrics["views"]["value"], 1200)
        self.assertEqual(metrics["views"]["precision"], "approximate")
        self.assertEqual(metrics["views"]["evidence_text"], "1.2k")
        self.assertEqual(metrics["reach"]["value"], 1100)
        self.assertEqual(metrics["reach"]["precision"], "exact")
        self.assertEqual(metrics["likes"]["value"], 640)
        self.assertEqual(metrics["likes"]["precision"], "exact")


if __name__ == "__main__":
    unittest.main()
