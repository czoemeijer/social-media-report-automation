from __future__ import annotations

import unittest

from social_report.sources.meta.auth import MetaConfig
from social_report.sources.meta.discovery import (
    AssetResolutionError,
    discover_assets,
    resolve_assets,
)


class FakeClient:
    def get(self, path, params=None):
        return {"id": "user"}

    def paginate(self, path, params=None):
        if path == "me/accounts":
            yield {"id": "page-1", "instagram_business_account": {"id": "ig-1"}}
        elif path == "me/adaccounts":
            yield {"id": "act_1", "account_status": 1}


class MetaDiscoveryTest(unittest.TestCase):
    def test_single_relationship_auto_resolves(self):
        assets = discover_assets(FakeClient())
        selected = resolve_assets(assets, MetaConfig(access_token="token"))
        self.assertEqual(
            selected,
            {"page_id": "page-1", "ig_user_id": "ig-1", "ad_account_id": "act_1"},
        )

    def test_multiple_pages_require_explicit_selection(self):
        assets = {
            "pages": [{"id": "2"}, {"id": "1"}],
            "ad_accounts": [],
        }
        with self.assertRaisesRegex(AssetResolutionError, "Multiple Pages"):
            resolve_assets(assets, MetaConfig(access_token="token"))
        selected = resolve_assets(
            assets, MetaConfig(access_token="token", page_id="2", ig_user_id="ig")
        )
        self.assertEqual(selected["page_id"], "2")

    def test_page_without_instagram_and_no_page_are_supported(self):
        selected = resolve_assets(
            {"pages": [{"id": "page"}], "ad_accounts": []},
            MetaConfig(access_token="token"),
        )
        self.assertIsNone(selected["ig_user_id"])
        empty = resolve_assets({"pages": [], "ad_accounts": []}, MetaConfig(access_token="token"))
        self.assertIsNone(empty["page_id"])

    def test_multiple_ad_accounts_and_inaccessible_selector_fail(self):
        assets = {"pages": [], "ad_accounts": [{"id": "act_1"}, {"id": "act_2"}]}
        with self.assertRaisesRegex(AssetResolutionError, "Multiple Ad Accounts"):
            resolve_assets(assets, MetaConfig(access_token="token"))
        with self.assertRaisesRegex(AssetResolutionError, "not accessible"):
            resolve_assets(assets, MetaConfig(access_token="token", ad_account_id="act_missing"))

    def test_inactive_account_is_not_auto_selected(self):
        selected = resolve_assets(
            {"pages": [], "ad_accounts": [{"id": "act_1", "account_status": 2}]},
            MetaConfig(access_token="token"),
        )
        self.assertIsNone(selected["ad_account_id"])

    def test_resolves_only_the_asset_kind_requested(self):
        assets = {
            "pages": [{"id": "page", "instagram_business_account": {"id": "ig"}}],
            "ad_accounts": [{"id": "act_1"}, {"id": "act_2"}],
        }
        selected = resolve_assets(
            assets,
            MetaConfig(access_token="token"),
            resolve_ad_account=False,
        )
        self.assertEqual(selected["ig_user_id"], "ig")
        self.assertIsNone(selected["ad_account_id"])

    def test_explicit_instagram_id_disambiguates_pages(self):
        assets = {
            "pages": [
                {"id": "one", "instagram_business_account": {"id": "ig-one"}},
                {"id": "two", "instagram_business_account": {"id": "ig-two"}},
            ],
            "ad_accounts": [],
        }
        selected = resolve_assets(
            assets,
            MetaConfig(access_token="token", ig_user_id="ig-two"),
            resolve_ad_account=False,
        )
        self.assertEqual(selected["page_id"], "two")

    def test_unique_linked_instagram_page_is_the_compatible_default(self):
        assets = {
            "pages": [
                {"id": "page-only"},
                {"id": "linked", "instagram_business_account": {"id": "ig"}},
            ],
            "ad_accounts": [],
        }
        selected = resolve_assets(assets, MetaConfig(access_token="token"))
        self.assertEqual(selected["page_id"], "linked")
        self.assertEqual(selected["ig_user_id"], "ig")


if __name__ == "__main__":
    unittest.main()
