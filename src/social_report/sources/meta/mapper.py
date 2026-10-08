"""Map Meta-native collections into the canonical owned-media report shape."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Mapping, Optional

from .matching import match_paid_to_organic
from .models import provenance, utc_now


def _in_report_period(
    item: Mapping[str, object], date_from: Optional[str], date_to: Optional[str]
) -> bool:
    if not date_from and not date_to:
        return True
    timestamp = item.get("timestamp")
    if not isinstance(timestamp, str):
        return False
    try:
        published = date.fromisoformat(timestamp[:10])
    except ValueError:
        return False
    return not (date_from and published < date.fromisoformat(date_from)) and not (
        date_to and published > date.fromisoformat(date_to)
    )


def build_owned_media_report(
    *,
    instagram: Mapping[str, object],
    ads: Mapping[str, object],
    api_version: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, object]:
    raw_media = instagram.get("media", [])
    all_media = (
        [item for item in raw_media if isinstance(item, dict)]
        if isinstance(raw_media, list)
        else []
    )
    media = [item for item in all_media if _in_report_period(item, date_from, date_to)]
    raw_creatives = ads.get("creatives", [])
    creatives = (
        [item for item in raw_creatives if isinstance(item, dict)]
        if isinstance(raw_creatives, list)
        else []
    )
    matches = match_paid_to_organic(creatives, all_media)
    match_by_media = {
        str(item["organic_media_id"]): item
        for item in matches
        if item.get("status") == "matched" and item.get("organic_media_id")
    }
    raw_ads = ads.get("ads", [])
    ad_rows = (
        [item for item in raw_ads if isinstance(item, dict)] if isinstance(raw_ads, list) else []
    )
    raw_insights = ads.get("insights", {})
    ad_insights = raw_insights.get("ad", []) if isinstance(raw_insights, dict) else []
    insights_by_ad = (
        {
            str(item.get("ad_id")): item
            for item in ad_insights
            if isinstance(item, dict) and item.get("ad_id")
        }
        if isinstance(ad_insights, list)
        else {}
    )
    paid_by_media: Dict[str, List[Mapping[str, object]]] = {}
    creative_matches = {
        str(item.get("creative_id")): str(item.get("organic_media_id"))
        for item in matches
        if item.get("status") == "matched"
        and item.get("creative_id")
        and item.get("organic_media_id")
    }
    for ad in ad_rows:
        creative = ad.get("creative")
        creative_id = creative.get("id") if isinstance(creative, dict) else None
        media_id = creative_matches.get(str(creative_id)) if creative_id else None
        insight = insights_by_ad.get(str(ad.get("id")))
        if media_id and insight:
            paid_by_media.setdefault(media_id, []).append(insight)
    contents: List[Dict[str, object]] = []
    for item in media:
        media_id = str(item.get("id", ""))
        insight_block = item.get("insights")
        metrics = insight_block.get("metrics", {}) if isinstance(insight_block, dict) else {}
        contents.append(
            {
                "identity": {
                    "platform": "instagram",
                    "media_id": media_id,
                    "permalink": item.get("permalink"),
                    "timestamp": item.get("timestamp"),
                    "media_type": item.get("media_type"),
                    "media_product_type": item.get("media_product_type"),
                    "caption": item.get("caption"),
                    "title": item.get("title"),
                    "reference_only": bool(item.get("reference_only", False)),
                    "authorized_owned": bool(item.get("authorized_owned", True)),
                },
                "organic": metrics if not item.get("reference_only") else None,
                "paid": {
                    "ad_insights": paid_by_media.get(media_id, []),
                    "reach_is_non_additive_with_organic": True,
                }
                if paid_by_media.get(media_id)
                else None,
                "paid_match": match_by_media.get(media_id),
                "scope": "unknown" if item.get("reference_only") else "organic",
            }
        )
    return {
        "report_type": "owned_media",
        "api_version": api_version,
        "retrieved_at": utc_now(),
        "report_period": {"date_from": date_from, "date_to": date_to},
        "instagram_profile": instagram.get("profile"),
        "ad_account": ads.get("account"),
        "content": contents,
        "ads": ads,
        "paid_organic_matches": matches,
        "provenance": provenance(
            platform="meta",
            object_type="owned_media_report",
            object_id=None,
            metric_name=None,
            api_version=api_version,
            scope="unknown",
        ),
        "warnings": [
            "Organic reach and paid reach are separate non-additive audience domains.",
            "Reference-only creative media identifies content exactly but does not claim "
            "private organic Insights.",
            *(
                [
                    f"{len(all_media) - len(media)} resolved media item(s) outside the report "
                    "period were excluded from organic content tables."
                ]
                if len(all_media) != len(media)
                else []
            ),
        ],
    }
