from __future__ import annotations

import unittest

from social_report.sources.meta.auth import MetaConfig
from social_report.sources.meta.client import MetaAPIError
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


class DirectClient:
    def __init__(self, responses=None, failures=()):
        self.responses = responses or {}
        self.failures = set(failures)

    def get(self, path, params=None):
        if path in self.failures:
            raise MetaAPIError("not accessible", status=403, code=10)
        return self.responses[path]


class MetaDiscoveryTest(unittest.TestCase):
    def test_single_relationship_auto_resolves(self):
        assets = discover_assets(FakeClient())
        selected = resolve_assets(assets, MetaConfig(access_token="token"))
        self.assertEqual(selected["page_id"], "page-1")
        self.assertEqual(selected["ig_user_id"], "ig-1")
        self.assertEqual(selected["ad_account_id"], "act_1")
        self.assertEqual(selected["validation"]["page"], "ENUMERATED")

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

    def test_explicit_page_can_be_directly_accessible_without_enumeration(self):
        client = DirectClient({"configured-page": {"id": "configured-page"}})
        selected = resolve_assets(
            {"pages": [], "ad_accounts": []},
            MetaConfig(access_token="token", page_id="configured-page"),
            client=client,
            resolve_ad_account=False,
        )
        self.assertEqual(selected["page_id"], "configured-page")
        self.assertEqual(selected["validation"]["page"], "DIRECTLY_ACCESSIBLE")

    def test_direct_page_relationship_confirms_direct_instagram(self):
        client = DirectClient(
            {
                "configured-page": {
                    "id": "configured-page",
                    "instagram_business_account": {"id": "configured-ig"},
                },
                "configured-ig": {"id": "configured-ig"},
            }
        )
        selected = resolve_assets(
            {"pages": [], "ad_accounts": []},
            MetaConfig(
                access_token="token",
                page_id="configured-page",
                ig_user_id="configured-ig",
            ),
            client=client,
            resolve_ad_account=False,
        )
        self.assertEqual(
            selected["validation"]["page_instagram_relationship"],
            "RELATIONSHIP_VERIFIED",
        )
        self.assertEqual(selected["validation"]["instagram"], "DIRECTLY_ACCESSIBLE")

    def test_explicit_page_direct_failure_is_rejected(self):
        with self.assertRaisesRegex(AssetResolutionError, "not directly accessible"):
            resolve_assets(
                {"pages": [], "ad_accounts": []},
                MetaConfig(access_token="token", page_id="configured-page"),
                client=DirectClient(failures=("configured-page",)),
                resolve_ad_account=False,
            )

    def test_direct_page_link_to_different_instagram_is_rejected(self):
        client = DirectClient(
            {
                "configured-page": {
                    "id": "configured-page",
                    "instagram_business_account": {"id": "different-ig"},
                },
                "configured-ig": {"id": "configured-ig"},
            }
        )
        with self.assertRaisesRegex(AssetResolutionError, "not linked"):
            resolve_assets(
                {"pages": [], "ad_accounts": []},
                MetaConfig(
                    access_token="token",
                    page_id="configured-page",
                    ig_user_id="configured-ig",
                ),
                client=client,
                resolve_ad_account=False,
            )

    def test_explicit_ad_account_can_be_directly_accessible_without_enumeration(self):
        client = DirectClient({"act_42": {"id": "act_42", "account_status": 1}})
        selected = resolve_assets(
            {"pages": [], "ad_accounts": []},
            MetaConfig(access_token="token", ad_account_id="42"),
            client=client,
            resolve_page=False,
        )
        self.assertEqual(selected["ad_account_id"], "act_42")
        self.assertEqual(selected["validation"]["ad_account"], "DIRECTLY_ACCESSIBLE")


if __name__ == "__main__":
    unittest.main()
