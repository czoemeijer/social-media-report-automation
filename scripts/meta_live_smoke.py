#!/usr/bin/env python3
"""Bounded read-only Meta smoke test that emits only sanitized capability evidence."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from social_report.sources.meta.ads import collect_ads  # noqa: E402
from social_report.sources.meta.auth import MetaConfig, load_env_file  # noqa: E402
from social_report.sources.meta.client import MetaAPIError, MetaClient  # noqa: E402
from social_report.sources.meta.discovery import (  # noqa: E402
    AssetResolutionError,
    discover_assets,
    resolve_assets,
)
from social_report.sources.meta.facebook import get_page  # noqa: E402
from social_report.sources.meta.instagram import (  # noqa: E402
    collect_instagram,
    resolve_creative_media_references,
)
from social_report.sources.meta.matching import match_paid_to_organic  # noqa: E402


def main() -> int:
    load_env_file(ROOT / ".env.local")
    config = MetaConfig.from_env()
    client = MetaClient(config)
    checks: Dict[str, object] = {
        "api_version": config.graph_version,
        "read_only": True,
    }
    identity = client.get("me", {"fields": "id"})
    checks["identity"] = bool(identity.get("id"))
    discovered = discover_assets(client)
    selected = resolve_assets(discovered, config)
    checks["pages_accessible"] = len(discovered.get("pages", []))
    checks["ad_accounts_accessible"] = len(discovered.get("ad_accounts", []))
    page_id = selected.get("page_id")
    ig_id = selected.get("ig_user_id")
    ad_id = selected.get("ad_account_id")
    if not page_id or not ig_id or not ad_id:
        raise AssetResolutionError("Page, Instagram, and Ad Account selectors must resolve")
    checks["page_read"] = bool(get_page(client, page_id).get("id"))
    instagram = collect_instagram(client, ig_id, limit=25, max_items=25)
    media_value = instagram.get("media", [])
    media = (
        [row for row in media_value if isinstance(row, dict)]
        if isinstance(media_value, list)
        else []
    )
    checks["instagram_profile_read"] = isinstance(instagram.get("profile"), dict)
    checks["media_count_sampled"] = len(media)
    feed = [row for row in media if str(row.get("media_product_type", "")).upper() == "FEED"]
    reels = [row for row in media if str(row.get("media_product_type", "")).upper() == "REELS"]
    checks["feed_insights"] = bool(feed and feed[0].get("insights"))
    checks["reel_insights"] = bool(reels and reels[0].get("insights"))
    reel_insights = reels[0].get("insights", {}) if reels else {}
    reel_metrics = reel_insights.get("metrics", {}) if isinstance(reel_insights, dict) else {}
    checks["reel_watch_time"] = bool(
        isinstance(reel_metrics, dict)
        and (
            reel_metrics.get("avg_watch_time_ms") is not None
            or reel_metrics.get("total_watch_time_ms") is not None
        )
    )
    ads = collect_ads(client, ad_id)
    checks["ad_account_read"] = isinstance(ads.get("account"), dict)
    checks["campaigns_read"] = len(ads.get("campaigns", []))
    insight_value = ads.get("insights", {})
    insights = insight_value if isinstance(insight_value, dict) else {}
    for level in ("account", "campaign", "adset", "ad"):
        checks[f"{level}_insights_rows"] = len(insights.get(level, []))
        checks[f"{level}_insights_read"] = True
    creative_value = ads.get("creatives", [])
    creatives = (
        [row for row in creative_value if isinstance(row, dict)]
        if isinstance(creative_value, list)
        else []
    )
    augmented_media = resolve_creative_media_references(
        client,
        ig_id,
        media,
        creatives,
        max_lookups=20,
    )
    checks["reference_media_resolved"] = len(augmented_media) - len(media)
    checks["owned_reference_media"] = sum(
        bool(row.get("authorized_owned"))
        for row in augmented_media
        if row.get("reference_only") is not None
    )
    matches = match_paid_to_organic(creatives, augmented_media)
    checks["creatives_read"] = len(creatives)
    checks["exact_paid_organic_matches"] = sum(row["status"] == "matched" for row in matches)
    required = (
        "identity",
        "page_read",
        "instagram_profile_read",
        "feed_insights",
        "reel_insights",
        "reel_watch_time",
        "ad_account_read",
        "campaign_insights_read",
        "adset_insights_read",
        "ad_insights_read",
        "exact_paid_organic_matches",
    )
    checks["status"] = "PASS" if all(checks.get(name) for name in required) else "FAIL"
    print(json.dumps(checks, indent=2, sort_keys=True))
    return 0 if checks["status"] == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (MetaAPIError, AssetResolutionError, ValueError) as exc:
        print(
            json.dumps(
                {
                    "status": "FAIL",
                    "error_type": type(exc).__name__,
                    "http_status": getattr(exc, "status", None),
                    "meta_code": getattr(exc, "code", None),
                },
                sort_keys=True,
            )
        )
        raise SystemExit(1) from None
