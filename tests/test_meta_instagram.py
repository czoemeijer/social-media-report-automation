from __future__ import annotations

import unittest

from social_report.sources.meta.auth import MetaConfig
from social_report.sources.meta.client import MetaAPIError
from social_report.sources.meta.instagram import (
    collect_instagram,
    get_media_insights,
    list_media,
    resolve_creative_media_references,
    validate_date_range,
)


class FakeInstagramClient:
    def __init__(self, fail_group=False):
        self.config = MetaConfig(access_token="token")
        self.fail_group = fail_group

    def get(self, path, params=None):
        if path == "ig-1":
            return {"id": "ig-1", "username": "synthetic"}
        metric = params["metric"]
        if self.fail_group and "," in metric:
            raise MetaAPIError("unsupported", status=400)
        values = {
            "views": 10,
            "reach": 0,
            "likes": 2,
            "comments": 1,
            "saved": 3,
            "shares": 4,
            "total_interactions": 11,
            "ig_reels_avg_watch_time": 1200,
            "ig_reels_video_view_total_time": 12000,
        }
        rows = [
            {"name": name, "values": [{"value": values[name]}]}
            for name in metric.split(",")
            if name in values
        ]
        return {"data": rows}

    def paginate(self, path, params=None):
        yield {"id": "image", "media_type": "IMAGE", "media_product_type": "FEED"}
        yield {
            "id": "reel",
            "media_type": "VIDEO",
            "media_product_type": "REELS",
        }
        yield {
            "id": "carousel",
            "media_type": "CAROUSEL_ALBUM",
            "media_product_type": "FEED",
        }


class InstagramTest(unittest.TestCase):
    def test_all_observed_media_types_and_reel_watch_time(self):
        result = collect_instagram(FakeInstagramClient(), "ig-1")
        self.assertEqual(len(result["media"]), 3)
        reel = result["media"][1]
        self.assertEqual(reel["insights"]["metrics"]["avg_watch_time_ms"], 1200)
        self.assertEqual(reel["insights"]["metrics"]["total_watch_time_ms"], 12000)

    def test_group_failure_falls_back_per_metric_and_preserves_zero(self):
        media = {"id": "image", "media_product_type": "FEED"}
        result = get_media_insights(FakeInstagramClient(fail_group=True), media)
        self.assertEqual(result["metrics"]["reach"], 0)
        self.assertIsNone(result["metrics"]["avg_watch_time_ms"])
        self.assertNotIn("reach", result["unavailable_metrics"])

    def test_absent_metric_is_unavailable_not_zero(self):
        result = get_media_insights(
            FakeInstagramClient(),
            {"id": "image", "media_product_type": "FEED"},
            metrics=("views", "not_supported"),
        )
        self.assertIn("not_supported", result["unavailable_metrics"])
        self.assertNotIn("not_supported", result["raw_metrics"])

    def test_date_validation(self):
        with self.assertRaises(ValueError):
            validate_date_range("2026-02-02", "2026-02-01")
        with self.assertRaises(ValueError):
            list_media(FakeInstagramClient(), "ig", date_from="bad")

    def test_creative_source_identity_is_reference_only_for_other_owner(self):
        class ReferenceClient(FakeInstagramClient):
            def get(self, path, params=None):
                if path == "source-1":
                    return {
                        "id": "source-1",
                        "owner": {"id": "other-owner"},
                        "permalink": "https://instagram.com/p/source-1",
                    }
                return super().get(path, params)

        result = resolve_creative_media_references(
            ReferenceClient(),
            "ig-1",
            [],
            [{"source_instagram_media_id": "source-1"}],
        )
        self.assertEqual(result[0]["id"], "source-1")
        self.assertTrue(result[0]["reference_only"])
        self.assertFalse(result[0]["authorized_owned"])
        self.assertNotIn("insights", result[0])


if __name__ == "__main__":
    unittest.main()
