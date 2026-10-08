from __future__ import annotations

import csv
import io
import unittest
from decimal import Decimal

from social_report.owned_reporting import export_owned_csv, export_owned_json, export_owned_markdown
from social_report.sources.meta.mapper import build_owned_media_report


def _content(
    media_id: str,
    *,
    timestamp: str = "2026-09-01T10:00:00+0000",
    product_type: str = "FEED",
    organic: object = None,
    paid_rows: object = None,
    reference_only: bool = False,
) -> dict[str, object]:
    return {
        "identity": {
            "platform": "instagram",
            "media_id": media_id,
            "permalink": f"https://instagram.com/p/{media_id}",
            "timestamp": timestamp,
            "media_type": "VIDEO" if product_type == "REELS" else "IMAGE",
            "media_product_type": product_type,
            "reference_only": reference_only,
            "authorized_owned": not reference_only,
        },
        "organic": organic,
        "paid": {"ad_insights": paid_rows, "reach_is_non_additive_with_organic": True}
        if paid_rows
        else None,
        "paid_match": {"status": "matched"} if paid_rows else None,
        "scope": "unknown" if reference_only else "organic",
    }


def _payload() -> dict[str, object]:
    return {
        "report_type": "owned_media",
        "api_version": "v26.0",
        "retrieved_at": "2026-10-08T12:00:00Z",
        "report_period": {"date_from": "2026-09-01", "date_to": "2026-09-30"},
        "instagram_profile": {
            "username": "owned-account",
            "followers_count": 1000,
            "media_count": 50,
        },
        "ad_account": {
            "name": "Owned Ads",
            "currency": "EUR",
            "timezone_name": "Europe/Prague",
        },
        "content": [],
        "ads": {
            "campaigns": [],
            "insights": {
                "account": [
                    {
                        "spend": "123.45",
                        "impressions": 10000,
                        "reach": 8000,
                        "clicks": 200,
                        "frequency": "1.25",
                    }
                ],
                "campaign": [],
            },
        },
        "paid_organic_matches": [],
        "warnings": ["Organic reach and paid reach are separate non-additive audience domains."],
    }


class OwnedReportingTest(unittest.TestCase):
    def test_mapper_records_explicit_report_period(self):
        report = build_owned_media_report(
            instagram={"media": []},
            ads={"creatives": [], "ads": [], "insights": {}},
            api_version="v26.0",
            date_from="2026-09-01",
            date_to="2026-09-30",
        )
        self.assertEqual(
            report["report_period"],
            {"date_from": "2026-09-01", "date_to": "2026-09-30"},
        )

    def test_markdown_uses_account_paid_kpis_without_summing_organic_reach(self):
        payload = _payload()
        payload["content"] = [
            _content(
                "one",
                organic={
                    "views": 100,
                    "reach": 80,
                    "likes": 5,
                    "platform_reported_total_interactions": 8,
                },
            ),
            _content(
                "two",
                organic={
                    "views": 200,
                    "reach": 120,
                    "likes": 9,
                    "platform_reported_total_interactions": 12,
                },
            ),
        ]
        markdown = export_owned_markdown(payload).decode()
        self.assertIn("- Period: 2026-09-01 to 2026-09-30", markdown)
        self.assertIn("- Spend: 123.45 EUR", markdown)
        self.assertIn("- Reach: 8,000", markdown)
        self.assertIn("- Known views: 300", markdown)
        self.assertIn("- Known platform-reported interactions: 20", markdown)
        self.assertIn("Aggregate organic reach: Not reported", markdown)
        self.assertNotIn("Aggregate organic reach: 200", markdown)

    def test_multi_ad_csv_sums_additive_fields_but_not_reach(self):
        payload = _payload()
        payload["content"] = [
            _content(
                "one",
                organic={"views": 100, "reach": 80},
                paid_rows=[
                    {
                        "spend": "1.50",
                        "impressions": 100,
                        "reach": 70,
                        "clicks": 1,
                    },
                    {
                        "spend": "2.50",
                        "impressions": 300,
                        "reach": 200,
                        "clicks": 6,
                    },
                ],
            )
        ]
        row = next(csv.DictReader(io.StringIO(export_owned_csv(payload).decode("utf-8-sig"))))
        self.assertEqual(row["paid_ad_count"], "2")
        self.assertEqual(row["paid_spend"], "4.00")
        self.assertEqual(row["paid_impressions"], "400")
        self.assertEqual(row["paid_clicks"], "7")
        self.assertEqual(row["paid_ctr"], "1.7500")
        self.assertEqual(row["paid_reach"], "")
        self.assertEqual(row["paid_reach_note"], "non-additive across rows")
        markdown = export_owned_markdown(payload).decode()
        self.assertIn("Not additive (2 ads)", markdown)

    def test_reels_watch_time_missing_values_and_reference_only_rows(self):
        payload = _payload()
        payload["content"] = [
            _content(
                "reel",
                product_type="REELS",
                organic={
                    "views": 500,
                    "reach": None,
                    "avg_watch_time_ms": 2500,
                    "total_watch_time_ms": 7200000,
                },
            ),
            _content("external", organic=None, reference_only=True),
        ]
        markdown = export_owned_markdown(payload).decode()
        self.assertIn("| Media #02 | 2.50 | 2.00 | 500 | Unavailable |", markdown)
        self.assertIn("2 (1 reference-only)", markdown)
        self.assertNotIn("external | Unavailable", markdown)

    def test_campaign_ranking_escaping_and_output_are_deterministic(self):
        payload = _payload()
        payload["content"] = [
            _content("z", organic={"views": 10, "reach": 5, "likes": 1}),
            _content("a", organic={"views": 10, "reach": 5, "likes": 1}),
        ]
        payload["ads"] = {
            "campaigns": [],
            "insights": {
                "account": _payload()["ads"]["insights"]["account"],  # type: ignore[index]
                "campaign": [
                    {
                        "campaign_id": "2",
                        "campaign_name": "Second",
                        "spend": "5",
                        "impressions": 100,
                    },
                    {
                        "campaign_id": "1",
                        "campaign_name": "Best | campaign\nname",
                        "spend": "8",
                        "impressions": 100,
                    },
                ],
            },
        }
        first = export_owned_markdown(payload)
        self.assertEqual(first, export_owned_markdown(payload))
        markdown = first.decode()
        self.assertIn("Most viewed organic item: Media #01 (10)", markdown)
        self.assertIn("Best \\| campaign name", markdown)
        self.assertLess(markdown.index("Best \\| campaign name"), markdown.index("Second"))

    def test_empty_report_decimal_budget_currency_and_json(self):
        payload = _payload()
        payload["ads"] = {"campaigns": [], "insights": {"account": [], "campaign": []}}
        payload["budget_reconciliation"] = {
            "summary": {
                "planned_spend": Decimal("100.10"),
                "actual_spend": Decimal("90.05"),
                "variance": Decimal("-10.05"),
                "matched": 1,
                "unmatched": 0,
                "ambiguous": 0,
                "needs_review": 0,
            }
        }
        markdown = export_owned_markdown(payload).decode()
        self.assertIn("_No data available._", markdown)
        self.assertIn("Planned spend: 100.10 EUR", markdown)
        self.assertIn("Spend: Unavailable", markdown)
        encoded = export_owned_json(payload).decode()
        self.assertIn('"planned_spend": "100.10"', encoded)
        self.assertEqual(export_owned_json(payload), export_owned_json(payload))


if __name__ == "__main__":
    unittest.main()
