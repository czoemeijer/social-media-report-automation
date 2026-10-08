"""Instagram Professional profile, media, and media Insights reads."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .client import MetaAPIError, MetaClient
from .insights import insight_values
from .models import provenance, utc_now

COMMON_MEDIA_METRICS = (
    "views",
    "reach",
    "likes",
    "comments",
    "saved",
    "shares",
    "total_interactions",
)
REEL_METRICS = ("ig_reels_avg_watch_time", "ig_reels_video_view_total_time")


def validate_date_range(date_from: Optional[str], date_to: Optional[str]) -> None:
    try:
        start = date.fromisoformat(date_from) if date_from else None
        end = date.fromisoformat(date_to) if date_to else None
    except ValueError as exc:
        raise ValueError("Dates must use YYYY-MM-DD") from exc
    if start and end and start > end:
        raise ValueError("--from must not be after --to")


def get_profile(client: MetaClient, ig_user_id: str) -> Mapping[str, Any]:
    return client.get(
        ig_user_id,
        {"fields": "id,username,name,followers_count,media_count"},
    )


def get_media_identity(client: MetaClient, media_id: str) -> Mapping[str, Any]:
    return client.get(
        media_id,
        {"fields": ("id,caption,media_type,media_product_type,permalink,timestamp,owner")},
    )


def resolve_creative_media_references(
    client: MetaClient,
    ig_user_id: str,
    media: Sequence[Mapping[str, Any]],
    creatives: Sequence[Mapping[str, Any]],
    *,
    max_lookups: int = 50,
) -> List[Mapping[str, Any]]:
    """Resolve exact creative source IDs without claiming unauthorized organic Insights."""

    result = list(media)
    known = {str(item.get("id")) for item in result if item.get("id")}
    attempted: set[str] = set()
    for creative in creatives:
        source_id = creative.get("source_instagram_media_id")
        media_id = str(source_id) if source_id else ""
        if not media_id or media_id in known or media_id in attempted:
            continue
        if len(attempted) >= max_lookups:
            break
        attempted.add(media_id)
        try:
            identity = dict(get_media_identity(client, media_id))
        except MetaAPIError:
            continue
        if str(identity.get("id", "")) != media_id:
            continue
        owner = identity.get("owner")
        owner_id = owner.get("id") if isinstance(owner, dict) else owner
        is_owned = str(owner_id or "") == str(ig_user_id)
        identity["reference_only"] = not is_owned
        identity["authorized_owned"] = is_owned
        if is_owned:
            identity["insights"] = get_media_insights(client, identity)
        result.append(identity)
        known.add(media_id)
    return result


def list_media(
    client: MetaClient,
    ig_user_id: str,
    *,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 100,
    max_items: Optional[int] = None,
) -> List[Mapping[str, Any]]:
    validate_date_range(date_from, date_to)
    params: Dict[str, object] = {
        "fields": "id,caption,media_type,media_product_type,permalink,timestamp",
        "limit": min(max(limit, 1), 100),
    }
    if date_from:
        params["since"] = date_from
    if date_to:
        params["until"] = date_to
    result: List[Mapping[str, Any]] = []
    for item in client.paginate(f"{ig_user_id}/media", params):
        result.append(item)
        if max_items is not None and len(result) >= max_items:
            break
    return result


def get_media_insights(
    client: MetaClient,
    media: Mapping[str, Any],
    metrics: Optional[Sequence[str]] = None,
) -> Dict[str, object]:
    media_id = str(media.get("id", ""))
    if not media_id:
        raise ValueError("Instagram media id is required")
    requested = list(metrics or COMMON_MEDIA_METRICS)
    if str(media.get("media_product_type", "")).upper() == "REELS":
        requested.extend(metric for metric in REEL_METRICS if metric not in requested)
    available: Dict[str, object] = {}
    unavailable: List[str] = []
    try:
        available.update(
            insight_values(client.get(f"{media_id}/insights", {"metric": ",".join(requested)}))
        )
        unavailable.extend(metric for metric in requested if metric not in available)
    except MetaAPIError:
        for metric in requested:
            try:
                values = insight_values(client.get(f"{media_id}/insights", {"metric": metric}))
                if metric in values:
                    available[metric] = values[metric]
                else:
                    unavailable.append(metric)
            except MetaAPIError:
                unavailable.append(metric)
    retrieved_at = utc_now()
    normalized: Dict[str, object] = {
        "views": available.get("views"),
        "reach": available.get("reach"),
        "likes": available.get("likes"),
        "comments": available.get("comments"),
        "saved": available.get("saved"),
        "shares": available.get("shares"),
        "platform_reported_total_interactions": available.get("total_interactions"),
        "avg_watch_time_ms": available.get("ig_reels_avg_watch_time"),
        "total_watch_time_ms": available.get("ig_reels_video_view_total_time"),
    }
    return {
        "metrics": normalized,
        "raw_metrics": available,
        "unavailable_metrics": sorted(set(unavailable)),
        "provenance": [
            provenance(
                platform="instagram",
                object_type="media",
                object_id=media_id,
                metric_name=metric,
                api_version=client.config.graph_version,
                scope="organic",
                retrieved_at=retrieved_at,
            )
            for metric in available
        ],
    }


def collect_instagram(
    client: MetaClient,
    ig_user_id: str,
    *,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 100,
    max_items: Optional[int] = None,
) -> Dict[str, object]:
    profile = get_profile(client, ig_user_id)
    media = list_media(
        client,
        ig_user_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        max_items=max_items,
    )
    enriched: List[Dict[str, object]] = []
    for item in media:
        normalized = dict(item)
        normalized["insights"] = get_media_insights(client, item)
        enriched.append(normalized)
    return {
        "profile": profile,
        "media": enriched,
        "api_version": client.config.graph_version,
    }
