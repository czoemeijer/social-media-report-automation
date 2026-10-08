from __future__ import annotations

import unittest

from social_report.sources.meta.ads import collect_ads, get_insights, normalize_ad_account_id
from social_report.sources.meta.auth import MetaConfig
from social_report.sources.meta.mapper import build_owned_media_report
from social_report.sources.meta.matching import match_paid_to_organic, normalize_permalink


class FakeAdsClient:
    config = MetaConfig(access_token="token")

    def paginate(self, path, params=None):
        yield {
            f"{params['level']}_id": "42",
            "spend": "12.30",
            "impressions": "100",
            "reach": "80",
            "actions": [{"action_type": "link_click", "value": "5"}],
            "cost_per_action_type": [{"action_type": "link_click", "value": "2.46"}],
        }

    def get(self, path, params=None):
        if path.startswith("act_"):
            return {"id": path, "currency": "EUR"}
        ids = str(params["ids"]).split(",")
        if "creative{" in str(params["fields"]):
            return {item: {"id": item, "creative": {"id": f"creative-{item}"}} for item in ids}
        return {item: {"id": item} for item in ids}


class AdsAndMatchingTest(unittest.TestCase):
    def test_account_id_and_four_insight_levels(self):
        self.assertEqual(normalize_ad_account_id("1"), "act_1")
        for level in ("account", "campaign", "adset", "ad"):
            row = get_insights(FakeAdsClient(), "1", level=level)[0]
            self.assertEqual(row["spend"], "12.30")
            self.assertEqual(row["impressions"], 100)
            self.assertEqual(row["actions_normalized"]["link_click"], 5)
            self.assertEqual(row["cost_per_action_normalized"]["link_click"], "2.46")
            self.assertEqual(row["scope"], "paid")

    def test_collect_ads_reads_period_insights_before_only_period_objects(self):
        client = FakeAdsClient()
        result = collect_ads(client, "1", date_from="2026-09-01", date_to="2026-09-30")
        self.assertEqual(result["collection"]["scope"], "report_period")
        self.assertEqual(result["collection"]["campaigns_in_period"], 1)
        self.assertEqual(result["collection"]["adsets_in_period"], 1)
        self.assertEqual(result["collection"]["ads_in_period"], 1)
        self.assertEqual(len(result["campaigns"]), 1)
        self.assertEqual(len(result["adsets"]), 1)
        self.assertEqual(len(result["ads"]), 1)
        self.assertEqual(len(result["creatives"]), 1)

    def test_source_media_id_has_priority_over_permalink(self):
        organic = [
            {"id": "organic-1", "permalink": "https://instagram.com/p/right/"},
            {"id": "organic-2", "permalink": "https://instagram.com/p/wrong/"},
        ]
        creative = {
            "id": "creative",
            "source_instagram_media_id": "organic-1",
            "instagram_permalink_url": "https://instagram.com/p/wrong/",
        }
        match = match_paid_to_organic([creative], organic)[0]
        self.assertEqual(match["organic_media_id"], "organic-1")
        self.assertEqual(match["match_method"], "source_instagram_media_id")

    def test_permalink_fallback_ambiguity_and_no_fuzzy_match(self):
        organic = [
            {"id": "1", "permalink": "https://www.instagram.com/p/same/?x=1"},
            {"id": "2", "permalink": "https://instagram.com/p/same/"},
        ]
        ambiguous = match_paid_to_organic(
            [{"id": "c", "instagram_permalink_url": "https://instagram.com/p/same"}], organic
        )[0]
        self.assertEqual(ambiguous["status"], "ambiguous")
        unmatched = match_paid_to_organic(
            [{"id": "c2", "name": "same caption"}], [{"id": "3", "caption": "same caption"}]
        )[0]
        self.assertEqual(unmatched["status"], "unmatched")
        self.assertEqual(
            normalize_permalink("https://www.instagram.com/p/x/?utm=1"), "https://instagram.com/p/x"
        )

    def test_mapper_keeps_domains_separate(self):
        instagram = {
            "profile": {"id": "ig"},
            "media": [
                {
                    "id": "m1",
                    "permalink": "https://instagram.com/p/1",
                    "insights": {"metrics": {"reach": 10}},
                }
            ],
        }
        ads = {
            "account": {"id": "act"},
            "creatives": [{"id": "c1", "source_instagram_media_id": "m1"}],
            "ads": [{"id": "ad1", "creative": {"id": "c1"}}],
            "insights": {"ad": [{"ad_id": "ad1", "reach": 20}]},
        }
        report = build_owned_media_report(instagram=instagram, ads=ads, api_version="v26.0")
        self.assertEqual(report["content"][0]["organic"]["reach"], 10)
        self.assertEqual(report["content"][0]["paid"]["ad_insights"][0]["reach"], 20)
        self.assertIn("non-additive", report["warnings"][0])

    def test_mapper_does_not_claim_reference_only_organic_metrics(self):
        report = build_owned_media_report(
            instagram={
                "profile": {"id": "ig"},
                "media": [
                    {
                        "id": "external-media",
                        "reference_only": True,
                        "authorized_owned": False,
                    }
                ],
            },
            ads={
                "creatives": [{"id": "creative", "source_instagram_media_id": "external-media"}],
                "ads": [],
                "insights": {"ad": []},
            },
            api_version="v26.0",
        )
        self.assertIsNone(report["content"][0]["organic"])
        self.assertEqual(report["content"][0]["scope"], "unknown")
        self.assertTrue(report["content"][0]["identity"]["reference_only"])


if __name__ == "__main__":
    unittest.main()
