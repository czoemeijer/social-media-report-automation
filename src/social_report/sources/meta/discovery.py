"""Authorized Page, Instagram Professional, and Ad Account discovery."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Sequence, TypedDict

from .auth import MetaConfig
from .client import MetaAPIError, MetaClient


class AssetResolutionError(ValueError):
    """Raised when asset selection is missing, invalid, or ambiguous."""


class ResolvedAssets(TypedDict):
    page_id: Optional[str]
    ig_user_id: Optional[str]
    ad_account_id: Optional[str]
    validation: Dict[str, str]


def discover_assets(client: MetaClient) -> Dict[str, object]:
    identity = client.get("me", {"fields": "id,name"})
    pages = list(
        client.paginate(
            "me/accounts",
            {
                "fields": "id,name,instagram_business_account{id,username}",
                "limit": 100,
            },
        )
    )
    ad_accounts = list(
        client.paginate(
            "me/adaccounts",
            {
                "fields": "id,name,account_status,currency,timezone_name",
                "limit": 100,
            },
        )
    )
    pages.sort(key=lambda item: str(item.get("id", "")))
    ad_accounts.sort(key=lambda item: str(item.get("id", "")))
    return {"identity": identity, "pages": pages, "ad_accounts": ad_accounts}


def _select(
    candidates: Sequence[Mapping[str, Any]], explicit_id: Optional[str], kind: str
) -> Optional[Mapping[str, Any]]:
    if explicit_id:
        normalized = explicit_id.removeprefix("act_") if kind == "Ad Account" else explicit_id
        matches = [
            item
            for item in candidates
            if str(item.get("id", "")).removeprefix("act_") == normalized
        ]
        if not matches:
            raise AssetResolutionError(f"Configured {kind} is not accessible")
        return matches[0]
    if not candidates:
        return None
    if len(candidates) > 1:
        ids = ", ".join(str(item.get("id", "unknown")) for item in candidates)
        raise AssetResolutionError(f"Multiple {kind}s are accessible; select one explicitly: {ids}")
    return candidates[0]


def resolve_assets(
    discovery: Mapping[str, object],
    config: MetaConfig,
    *,
    client: Optional[MetaClient] = None,
    resolve_page: bool = True,
    resolve_ad_account: bool = True,
) -> ResolvedAssets:
    raw_pages = discovery.get("pages", [])
    raw_accounts = discovery.get("ad_accounts", [])
    pages = (
        [item for item in raw_pages if isinstance(item, dict)]
        if isinstance(raw_pages, list)
        else []
    )
    accounts = (
        [item for item in raw_accounts if isinstance(item, dict)]
        if isinstance(raw_accounts, list)
        else []
    )
    validation: Dict[str, str] = {}
    page_candidates = pages
    if resolve_page and not config.page_id:
        linked_pages = [
            item for item in pages if isinstance(item.get("instagram_business_account"), dict)
        ]
        if config.ig_user_id:
            linked_pages = [
                item
                for item in linked_pages
                if str(item["instagram_business_account"].get("id", "")) == config.ig_user_id
            ]
        if linked_pages:
            page_candidates = linked_pages
    page: Optional[Mapping[str, Any]] = None
    if resolve_page and config.page_id and client:
        try:
            page = client.get(
                config.page_id,
                {"fields": "id,name,instagram_business_account{id,username}"},
            )
        except MetaAPIError as exc:
            raise AssetResolutionError("Configured Page is not directly accessible") from exc
        if str(page.get("id", "")) != config.page_id:
            raise AssetResolutionError("Configured Page direct lookup returned another object")
        validation["page"] = "DIRECTLY_ACCESSIBLE"
    elif resolve_page:
        page = _select(page_candidates, config.page_id, "Page")
        if page:
            validation["page"] = "ENUMERATED"
    active_accounts = [item for item in accounts if item.get("account_status") in {None, 1, "1"}]
    account: Optional[Mapping[str, Any]] = None
    if resolve_ad_account and config.ad_account_id and client:
        account_id = config.ad_account_id
        account_path = account_id if account_id.startswith("act_") else f"act_{account_id}"
        try:
            account = client.get(
                account_path,
                {"fields": "id,name,account_status,currency,timezone_name"},
            )
        except MetaAPIError as exc:
            raise AssetResolutionError("Configured Ad Account is not directly accessible") from exc
        returned_id = str(account.get("id", "")).removeprefix("act_")
        if returned_id != account_id.removeprefix("act_"):
            raise AssetResolutionError(
                "Configured Ad Account direct lookup returned another object"
            )
        if account.get("account_status") not in {None, 1, "1"}:
            raise AssetResolutionError("Configured Ad Account is not active")
        validation["ad_account"] = "DIRECTLY_ACCESSIBLE"
    elif resolve_ad_account:
        account = _select(active_accounts, config.ad_account_id, "Ad Account")
        if account:
            validation["ad_account"] = "ENUMERATED"
    ig_id = config.ig_user_id
    if resolve_page and ig_id and client:
        try:
            instagram = client.get(
                ig_id,
                {"fields": "id,username,name,followers_count,media_count"},
            )
        except MetaAPIError as exc:
            raise AssetResolutionError(
                "Configured Instagram account is not directly accessible"
            ) from exc
        if str(instagram.get("id", "")) != ig_id:
            raise AssetResolutionError("Configured Instagram direct lookup returned another object")
        validation["instagram"] = "DIRECTLY_ACCESSIBLE"
    if not ig_id and page:
        linked = page.get("instagram_business_account")
        if isinstance(linked, dict) and linked.get("id"):
            ig_id = str(linked["id"])
            validation["instagram"] = "ENUMERATED"
    if config.ig_user_id and page:
        linked = page.get("instagram_business_account")
        linked_id = str(linked.get("id")) if isinstance(linked, dict) and linked.get("id") else None
        if linked_id and linked_id != config.ig_user_id:
            raise AssetResolutionError(
                "Configured Instagram account is not linked to the selected Page"
            )
        validation["page_instagram_relationship"] = (
            "RELATIONSHIP_VERIFIED" if linked_id else "RELATIONSHIP_UNVERIFIED"
        )
    return {
        "page_id": str(page["id"]) if page and page.get("id") else None,
        "ig_user_id": ig_id,
        "ad_account_id": str(account["id"]) if account and account.get("id") else None,
        "validation": validation,
    }
