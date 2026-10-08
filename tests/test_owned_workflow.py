from __future__ import annotations

import json
import subprocess
import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from social_report.owned_analytics import analyze_owned_media
from social_report.owned_html import export_owned_html
from social_report.owned_pdf import find_pdf_browser, pdf_command, render_pdf
from social_report.owned_presentation import (
    action_label,
    default_insights,
    format_integer,
    format_money,
    format_multiple,
    format_percent_ratio,
    format_seconds_ms,
    validate_insights,
)
from social_report.owned_workflow import (
    make_snapshot,
    previous_completed_month,
    run_owned_workflow,
    snapshot_cache_key,
    snapshot_status,
)
from social_report.sources.meta.auth import MetaConfig
from social_report.sources.meta.client import MetaAPIError


def _report() -> dict[str, object]:
    return {
        "report_type": "owned_media",
        "api_version": "v26.0",
        "retrieved_at": "2026-10-01T12:00:00Z",
        "report_period": {"date_from": "2026-09-01", "date_to": "2026-09-30"},
        "instagram_profile": {"username": "测试-account", "followers_count": 100},
        "ad_account": {"name": "Synthetic Ads", "currency": "EUR"},
        "content": [
            {
                "identity": {
                    "media_id": "m1",
                    "timestamp": "2026-09-01T10:00:00+0000",
                    "media_product_type": "REELS",
                },
                "organic": {
                    "views": 200,
                    "reach": 100,
                    "platform_reported_total_interactions": 20,
                    "saved": 4,
                    "shares": 2,
                    "avg_watch_time_ms": 2500,
                },
                "paid": {"ad_insights": [{"spend": "10", "impressions": 1000}]},
            },
            {
                "identity": {
                    "media_id": "m2",
                    "timestamp": "2026-09-02T10:00:00+0000",
                    "media_product_type": "FEED",
                },
                "organic": {
                    "views": 100,
                    "reach": 100,
                    "platform_reported_total_interactions": 10,
                    "saved": 1,
                    "shares": 1,
                },
                "paid": None,
            },
        ],
        "ads": {
            "account": {"currency": "EUR"},
            "collection": {
                "scope": "report_period",
                "campaigns_in_period": 2,
                "adsets_in_period": 2,
                "ads_in_period": 2,
                "creatives_in_period": 2,
            },
            "campaigns": [
                {"id": "c1", "name": "Awareness <script>", "objective": "OUTCOME_AWARENESS"},
                {"id": "c2", "name": "Engagement", "objective": "OUTCOME_ENGAGEMENT"},
            ],
            "ads": [{"id": "a1"}, {"id": "a2"}],
            "creatives": [{"id": "cr1"}, {"id": "cr2"}],
            "insights": {
                "account": [
                    {
                        "spend": "30",
                        "impressions": 3000,
                        "reach": 2000,
                        "clicks": 90,
                        "frequency": "1.5",
                        "actions_normalized": {
                            "link_click": 40,
                            "landing_page_view": 30,
                            "post_engagement": 200,
                            "video_view": 800,
                        },
                    }
                ],
                "campaign": [
                    {
                        "campaign_id": "c1",
                        "campaign_name": "Awareness <script>",
                        "spend": "20",
                        "impressions": 2000,
                        "reach": 1500,
                        "actions_normalized": {},
                    },
                    {
                        "campaign_id": "c2",
                        "campaign_name": "Engagement",
                        "spend": "10",
                        "impressions": 1000,
                        "reach": 800,
                        "actions_normalized": {"post_engagement": 200},
                    },
                ],
            },
        },
        "paid_organic_matches": [
            {"creative_id": "cr1", "status": "matched", "organic_media_id": "m1"},
            {"creative_id": "cr2", "status": "unmatched", "organic_media_id": None},
        ],
        "warnings": ["Organic and paid reach are non-additive."],
    }


class OwnedAnalyticsTest(unittest.TestCase):
    def test_analysis_exposes_rates_actions_objectives_and_period_matching(self):
        analysis = analyze_owned_media(_report())
        self.assertEqual(
            analysis["organic"]["weighted_content_rates"]["content_weighted_interaction_rate"],
            "0.15",
        )
        self.assertEqual(analysis["organic"]["reels"]["avg_watch_time_ms"]["mean"], "2500")
        self.assertEqual(analysis["paid"]["account"]["all_clicks"], "90")
        self.assertEqual(analysis["paid"]["account"]["link_clicks"]["value"], "40")
        self.assertEqual(analysis["paid"]["account"]["landing_page_views"]["value"], "30")
        self.assertFalse(analysis["paid"]["account"]["post_reactions"]["available"])
        self.assertEqual(
            {row["objective_group"] for row in analysis["paid"]["objective_groups"]},
            {"awareness", "engagement"},
        )
        self.assertEqual(analysis["matching"]["paid_ads_in_period"], 2)
        self.assertEqual(analysis["matching"]["exact_creative_matches"], 1)
        self.assertEqual(analysis["matching"]["unmatched_creatives"], 1)
        self.assertEqual(analysis["matching"]["matched_owned_media_items"], 1)
        self.assertEqual(analysis["matching"]["exact_match_coverage"], "0.5")
        self.assertEqual(
            analysis["comparisons"]["paid_recorded_action_ratios"]["landing_views_per_link_click"],
            "0.75",
        )
        self.assertIn("1 Sep - Reels", analysis["organic"]["items"][0]["label"])

    def test_presentation_formatting_and_human_action_labels(self):
        self.assertEqual(format_integer(6206), "6,206")
        self.assertEqual(format_money("28016.12", "CZK"), "28,016 CZK")
        self.assertEqual(format_percent_ratio("0.024649"), "2.46%")
        self.assertEqual(format_seconds_ms("5701.5"), "5.70 s")
        self.assertEqual(format_multiple("1.55357"), "1.55×")
        self.assertEqual(action_label("landing_page_view"), "Landing-page views")

    def test_narrative_schema_validates_evidence_and_default_fallback(self):
        analysis = analyze_owned_media(_report())
        narrative = default_insights(analysis)
        self.assertGreaterEqual(len(narrative["executive_summary"]), 3)
        with self.assertRaisesRegex(ValueError, "does not exist"):
            validate_insights(
                {
                    "executive_summary": [{"text": "Claim", "evidence_refs": ["organic.missing"]}],
                    "observations": [],
                    "recommendations": [],
                },
                analysis,
            )

    def test_html_is_self_contained_deterministic_escaped_and_unicode_safe(self):
        report = _report()
        analysis = analyze_owned_media(report)
        narrative = default_insights(analysis)
        first = export_owned_html(report, analysis, narrative, language="zh")
        self.assertEqual(first, export_owned_html(report, analysis, narrative, language="zh"))
        document = first.decode("utf-8")
        self.assertIn("自有媒体效果报告", document)
        self.assertIn("测试-account", document)
        self.assertNotIn("Awareness <script>", document)
        self.assertIn("Awareness &lt;script&gt;", document)
        self.assertGreaterEqual(document.count('data-chart="'), 8)
        self.assertNotIn("<script", document)
        self.assertNotIn("https://", document)
        self.assertIn("@media print", document)
        self.assertIn("@page", document)
        self.assertNotIn("landing_page_view", document)
        self.assertIn("Landing-page views", document)

    def test_pdf_renderer_discovery_and_command(self):
        self.assertIsNone(find_pdf_browser({"SOCIAL_REPORT_BROWSER": "/missing/browser"}))
        with TemporaryDirectory() as temp:
            root = Path(temp)
            command = pdf_command(
                Path("/browser"),
                root / "report.html",
                root / "report.pdf",
                user_data_dir=root / "profile",
            )
            self.assertIn("--headless=new", command)
            self.assertIn("--no-pdf-header-footer", command)
            self.assertTrue(command[-1].startswith("file://"))

    def test_pdf_renderer_accepts_completed_file_and_replaces_target(self):
        class FakeProcess:
            returncode = None

            def __init__(self, command, **kwargs):
                del kwargs
                output = next(value for value in command if value.startswith("--print-to-pdf="))
                Path(output.split("=", 1)[1]).write_bytes(b"%PDF-1.4\n" + b"page\n" * 300)

            def poll(self):
                return self.returncode

            def terminate(self):
                self.returncode = 0

            def wait(self, timeout):
                del timeout
                return self.returncode

            def kill(self):
                self.returncode = -9

        with TemporaryDirectory() as temp:
            root = Path(temp)
            html_path = root / "report.html"
            pdf_path = root / "report.pdf"
            html_path.write_text("<html></html>", encoding="utf-8")
            pdf_path.write_bytes(b"old")
            with (
                patch("social_report.owned_pdf.find_pdf_browser", return_value=Path("/browser")),
                patch("social_report.owned_pdf.subprocess.Popen", side_effect=FakeProcess),
                patch("social_report.owned_pdf.time.sleep"),
            ):
                result = render_pdf(html_path, pdf_path)
            self.assertEqual(result["status"], "PASS")
            self.assertTrue(pdf_path.read_bytes().startswith(b"%PDF-"))

    def test_pdf_renderer_unavailable_preserves_existing_target(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            pdf_path = root / "report.pdf"
            pdf_path.write_bytes(b"existing")
            with patch("social_report.owned_pdf.find_pdf_browser", return_value=None):
                result = render_pdf(root / "report.html", pdf_path)
            self.assertEqual(result["status"], "PDF_RENDERER_UNAVAILABLE")
            self.assertEqual(pdf_path.read_bytes(), b"existing")


class OwnedWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.config = MetaConfig(access_token="not-written-to-snapshot")
        self.now = datetime(2026, 10, 8, 12, 0, tzinfo=timezone.utc)
        self.pdf_patcher = patch(
            "social_report.owned_workflow.render_pdf", side_effect=self._fake_pdf
        )
        self.pdf_patcher.start()

    def tearDown(self):
        self.pdf_patcher.stop()

    @staticmethod
    def _fake_pdf(html_path, pdf_path):
        pdf_path.write_bytes(b"%PDF-1.4\n" + b"synthetic\n" * 200)
        return {"status": "PASS", "path": str(pdf_path), "bytes": pdf_path.stat().st_size}

    def test_period_cache_key_and_snapshot_freshness(self):
        self.assertEqual(previous_completed_month(date(2026, 10, 8)), ("2026-09-01", "2026-09-30"))
        snapshot = make_snapshot(
            _report(),
            api_version="v26.0",
            assets={"ig_user_id": "ig", "ad_account_id": "act"},
            created_at="2026-10-08T11:00:00+00:00",
        )
        status = snapshot_status(
            snapshot,
            date_from="2026-09-01",
            date_to="2026-09-30",
            api_version="v26.0",
            now=self.now,
        )
        self.assertTrue(status["valid"])
        self.assertTrue(status["fresh"])
        first = snapshot_cache_key(
            provider="meta",
            api_version="v26.0",
            period=_report()["report_period"],
            assets={"ig_user_id": "ig"},
        )
        second = snapshot_cache_key(
            provider="meta",
            api_version="v26.0",
            period=_report()["report_period"],
            assets={"ig_user_id": "different"},
        )
        self.assertNotEqual(first, second)
        self.assertNotIn("not-written-to-snapshot", json.dumps(snapshot))

    def test_fresh_snapshot_is_reused_without_acquisition_and_writes_bundle(self):
        snapshot = make_snapshot(
            _report(),
            api_version="v26.0",
            assets={"ig_user_id": "ig", "ad_account_id": "act"},
            created_at="2026-10-08T11:00:00+00:00",
        )
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")

            def unexpected(*args):
                self.fail("fresh snapshot must prevent live acquisition")

            result = run_owned_workflow(
                self.config,
                output_dir=root,
                date_from="2026-09-01",
                date_to="2026-09-30",
                now=self.now,
                acquire=unexpected,
            )
            self.assertEqual(result["snapshot_mode"], "snapshot")
            for name in result["files"]:
                self.assertTrue((root / name).exists(), name)
            self.assertIn("insights.json", result["files"])
            self.assertIn("report.pdf", result["files"])

    def test_refresh_fetches_once_and_then_cli_and_skill_reuse_same_snapshot(self):
        calls = []

        def acquire(config, start, end, budget):
            calls.append((start, end))
            return _report(), {"ig_user_id": "ig", "ad_account_id": "act"}

        with TemporaryDirectory() as temp:
            root = Path(temp)
            result = run_owned_workflow(
                self.config,
                output_dir=root,
                date_from="2026-09-01",
                date_to="2026-09-30",
                refresh=True,
                now=self.now,
                acquire=acquire,
            )
            self.assertEqual(result["snapshot_mode"], "live")
            self.assertEqual(calls, [("2026-09-01", "2026-09-30")])
            env = {
                "PYTHONPATH": str(Path.cwd() / "src"),
                "SOCIAL_REPORT_BROWSER": "/missing/browser",
            }
            cli_dir = root / "cli"
            skill_dir = root / "skill"
            common = [
                "report",
                "--from",
                "2026-09-01",
                "--to",
                "2026-09-30",
                "--snapshot-input",
                str(root / "snapshot.json"),
            ]
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "social_report.cli",
                    "meta",
                    *common,
                    "--output-dir",
                    str(cli_dir),
                ],
                check=True,
                env=env,
                capture_output=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    "skills/owned-media-report/scripts/owned_media_report.py",
                    *common,
                    "--output-dir",
                    str(skill_dir),
                ],
                check=True,
                env=env,
                capture_output=True,
            )
            for name in (
                "analysis.json",
                "insights.json",
                "report.json",
                "report.csv",
                "report.md",
                "report.html",
            ):
                self.assertEqual((cli_dir / name).read_bytes(), (skill_dir / name).read_bytes())

    def test_rate_limit_uses_valid_same_period_stale_snapshot(self):
        snapshot = make_snapshot(
            _report(),
            api_version="v26.0",
            assets={"ig_user_id": "ig", "ad_account_id": "act"},
            created_at="2026-09-01T00:00:00+00:00",
        )
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")

            def limited(*args):
                raise MetaAPIError("rate limited", status=429, code=4)

            result = run_owned_workflow(
                self.config,
                output_dir=root,
                date_from="2026-09-01",
                date_to="2026-09-30",
                now=self.now,
                acquire=limited,
            )
            self.assertEqual(result["snapshot_mode"], "snapshot_rate_limit_fallback")
            self.assertFalse(result["snapshot_status"]["fresh"])

    def test_no_token_uses_matching_stale_snapshot_without_meta_request(self):
        snapshot = make_snapshot(
            _report(),
            api_version="v26.0",
            assets={"ig_user_id": "ig", "ad_account_id": "act"},
            created_at="2026-09-01T00:00:00+00:00",
        )
        with TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "snapshot.json").write_text(json.dumps(snapshot), encoding="utf-8")

            def unexpected(*args):
                self.fail("offline snapshot render must not call Meta")

            result = run_owned_workflow(
                MetaConfig(access_token=""),
                output_dir=root,
                date_from="2026-09-01",
                date_to="2026-09-30",
                now=self.now,
                acquire=unexpected,
            )
            self.assertEqual(result["snapshot_mode"], "snapshot_stale_offline")

    def test_no_snapshot_and_no_token_returns_stable_auth_error(self):
        with (
            TemporaryDirectory() as temp,
            self.assertRaisesRegex(ValueError, "AUTH_REQUIRED_FOR_FRESH_FETCH"),
        ):
            run_owned_workflow(
                MetaConfig(access_token=""),
                output_dir=Path(temp),
                date_from="2026-09-01",
                date_to="2026-09-30",
                now=self.now,
            )


if __name__ == "__main__":
    unittest.main()
