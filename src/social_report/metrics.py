"""Scope-aware deterministic social-media calculations."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Union, cast

from .schemas import SCOPES
from .validation import flatten_asset_metrics, merge_review_status, validate_extraction

ENGAGEMENT_COMPONENTS = ("likes", "comments", "shares", "saves")
Number = Union[int, float]


def normalize_scope(item: Mapping[str, Any]) -> str:
    raw_scope = item.get("scope", "unknown")
    scope = raw_scope.lower().strip() if isinstance(raw_scope, str) else "unknown"
    if (
        item.get("has_ad_disclaimer")
        or item.get("ad_disclaimer")
        or item.get("ad_disclaimer_present")
    ):
        return "mixed_or_unknown"
    aliases = {"mixed": "mixed_or_unknown", "unknown_with_ads": "mixed_or_unknown"}
    scope = aliases.get(scope, scope)
    return scope if scope in SCOPES else "unknown"


def _number(value: Any) -> Optional[Number]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return cast(Number, value)


def calculate_single_item(item: Mapping[str, Any]) -> Dict[str, Any]:
    """Calculate audited metrics for one asset while preserving source fields."""

    result: Dict[str, Any] = dict(item)
    warnings = list(result.get("warnings") or [])
    result["warnings"] = warnings
    scope = normalize_scope(item)
    result["scope"] = scope

    values = {name: _number(item.get(name)) for name in ENGAGEMENT_COMPONENTS}
    reach = _number(item.get("reach"))
    platform_interactions = _number(item.get("platform_reported_interactions"))
    feed_shares = _number(item.get("feed_shares"))
    feed_reposts = _number(item.get("feed_reposts"))

    if scope == "mixed_or_unknown":
        warnings.append(
            "Insights include organic and paid data that cannot be separated; "
            "scope classified as mixed_or_unknown."
        )
    elif scope == "paid":
        warnings.append("Paid scope detected: do not interpret its rates as organic performance.")
    elif scope == "unknown":
        warnings.append("Scope is unknown; the asset is not included in an organic-only KPI.")

    if values["shares"] is None and (feed_shares is not None or feed_reposts is not None):
        result["feed_vs_insights_shares_discrepancy"] = True
        result["feed_vs_insights_note"] = (
            "Feed-visible shares/reposts are preserved separately and do not replace "
            "Insights shares."
        )
    elif (
        values["shares"] is not None and feed_shares is not None and values["shares"] != feed_shares
    ):
        result["feed_vs_insights_shares_discrepancy"] = True
        result["feed_vs_insights_note"] = (
            f"Insights shares ({values['shares']}) differs from feed-visible "
            f"shares ({feed_shares})."
        )
    else:
        result["feed_vs_insights_shares_discrepancy"] = False

    known_values = [value for value in values.values() if value is not None]
    missing = [name for name, value in values.items() if value is None]
    known_actions = sum(known_values) if known_values else None
    result["known_engagement_actions"] = known_actions
    result["engagement_is_complete"] = not missing
    result["missing_engagement_components"] = missing

    if platform_interactions is not None and known_actions is not None:
        discrepancy = platform_interactions - known_actions
        result["interaction_discrepancy_value"] = discrepancy
        result["interaction_discrepancy"] = discrepancy != 0
        result["uncategorized_interactions"] = discrepancy if discrepancy >= 0 else None
        if discrepancy < 0:
            warnings.append(
                "Platform interactions are lower than known actions; signed discrepancy "
                "is preserved for review."
            )
    else:
        result["interaction_discrepancy_value"] = None
        result["interaction_discrepancy"] = False
        result["uncategorized_interactions"] = None

    reach_is_approximate = bool(item.get("reach_is_approximate", False))
    contributing_approximate = any(
        bool(item.get(f"{name}_is_approximate", False))
        for name in ENGAGEMENT_COMPONENTS
        if values.get(name) is not None
    )
    er_is_approximate = reach_is_approximate or contributing_approximate

    if reach is not None and reach > 0 and known_actions is not None:
        engagement_rate = round((known_actions / reach) * 100.0, 4)
        if missing:
            result["calculated_er_by_reach"] = None
            result["er_lower_bound_by_reach"] = engagement_rate
            result["er_is_complete"] = False
            result["er_status"] = "incomplete_lower_bound"
            warnings.append(
                f"Incomplete engagement components: {missing} missing/unavailable. "
                f"Known-actions lower bound is {engagement_rate}%."
            )
        else:
            result["calculated_er_by_reach"] = engagement_rate
            result["er_lower_bound_by_reach"] = None
            result["er_is_complete"] = True
            result["er_status"] = "complete"
        result["er_is_approximate"] = er_is_approximate
    else:
        result["calculated_er_by_reach"] = None
        result["er_lower_bound_by_reach"] = None
        result["er_is_complete"] = False
        result["er_status"] = "unavailable"
        result["er_is_approximate"] = False

    saves = values["saves"]
    saves_is_approximate = bool(item.get("saves_is_approximate", False))
    result["save_rate_pct"] = (
        round((saves / reach) * 100.0, 4)
        if reach is not None and reach > 0 and saves is not None
        else None
    )
    result["save_rate_is_approximate"] = (
        bool(reach_is_approximate or saves_is_approximate)
        if result["save_rate_pct"] is not None
        else False
    )

    likes = values["likes"]
    comments = values["comments"]
    likes_is_approximate = bool(item.get("likes_is_approximate", False))
    comments_is_approximate = bool(item.get("comments_is_approximate", False))
    result["comment_to_like_ratio_pct"] = (
        round((comments / likes) * 100.0, 4)
        if likes is not None and likes > 0 and comments is not None
        else None
    )
    result["comment_to_like_ratio_is_approximate"] = (
        bool(likes_is_approximate or comments_is_approximate)
        if result["comment_to_like_ratio_pct"] is not None
        else False
    )

    initial_status = item.get("review_status", "verified")
    if warnings:
        result["review_status"] = merge_review_status(initial_status, "verified_with_warning")
    else:
        result["review_status"] = initial_status
    return result


def _sum_present(items: Iterable[Mapping[str, Any]], field: str) -> Optional[Number]:
    values = [_number(item.get(field)) for item in items]
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def _aggregate_bucket(items: List[Mapping[str, Any]], scope: str) -> Dict[str, Any]:
    audited = [calculate_single_item(item) for item in items]
    summary: Dict[str, Any] = {
        "scope": scope,
        "asset_count": len(audited),
        "total_views": _sum_present(audited, "views"),
        "total_likes": _sum_present(audited, "likes"),
        "total_comments": _sum_present(audited, "comments"),
        "total_shares": _sum_present(audited, "shares"),
        "total_saves": _sum_present(audited, "saves"),
        "sum_of_content_reach": _sum_present(audited, "reach"),
        "total_known_engagement_actions": _sum_present(audited, "known_engagement_actions"),
        "total_platform_reported_interactions": _sum_present(
            audited, "platform_reported_interactions"
        ),
        "reach_aggregation_warning": (
            "Sum of content-level Reach contains audience overlap and must not be interpreted "
            "as unique campaign Reach."
        ),
    }
    missing_assets = [
        str(item.get("id") or item.get("asset_group_id") or item.get("creator") or "unknown_asset")
        for item in audited
        if not item["engagement_is_complete"]
    ]
    reach = summary["sum_of_content_reach"]
    actions = summary["total_known_engagement_actions"]
    rate = round((actions / reach) * 100.0, 4) if reach and actions is not None else None
    if missing_assets:
        summary.update(
            {
                "weighted_calculated_er_by_reach": None,
                "weighted_er_lower_bound_by_reach": rate,
                "er_is_complete": False,
                "er_status": "incomplete_lower_bound" if rate is not None else "unavailable",
                "items_with_missing_components": missing_assets,
            }
        )
    else:
        summary.update(
            {
                "weighted_calculated_er_by_reach": rate,
                "weighted_er_lower_bound_by_reach": None,
                "er_is_complete": rate is not None,
                "er_status": "complete" if rate is not None else "unavailable",
            }
        )
    saves = summary["total_saves"]
    likes = summary["total_likes"]
    comments = summary["total_comments"]
    summary["overall_save_rate_pct"] = (
        round((saves / reach) * 100.0, 4) if reach and saves is not None else None
    )
    summary["overall_comment_to_like_ratio_pct"] = (
        round((comments / likes) * 100.0, 4) if likes and comments is not None else None
    )

    any_reach_approx = any(
        bool(item.get("reach_is_approximate", False))
        for item in audited
        if item.get("reach") is not None
    )
    any_action_approx = any(
        bool(item.get(f"{name}_is_approximate", False))
        for item in audited
        for name in ENGAGEMENT_COMPONENTS
        if item.get(name) is not None
    )
    any_saves_approx = any(
        bool(item.get("saves_is_approximate", False))
        for item in audited
        if item.get("saves") is not None
    )
    any_likes_approx = any(
        bool(item.get("likes_is_approximate", False))
        for item in audited
        if item.get("likes") is not None
    )
    any_comments_approx = any(
        bool(item.get("comments_is_approximate", False))
        for item in audited
        if item.get("comments") is not None
    )
    summary["sum_of_content_reach_is_approximate"] = (
        any_reach_approx if summary["sum_of_content_reach"] is not None else False
    )
    summary["total_known_engagement_actions_is_approximate"] = (
        any_action_approx if summary["total_known_engagement_actions"] is not None else False
    )
    summary["weighted_er_is_approximate"] = bool(
        (any_reach_approx or any_action_approx)
        and (
            summary.get("weighted_calculated_er_by_reach") is not None
            or summary.get("weighted_er_lower_bound_by_reach") is not None
        )
    )
    summary["overall_save_rate_is_approximate"] = bool(
        (any_reach_approx or any_saves_approx)
        if summary.get("overall_save_rate_pct") is not None
        else False
    )
    summary["overall_comment_to_like_ratio_is_approximate"] = bool(
        (any_likes_approx or any_comments_approx)
        if summary.get("overall_comment_to_like_ratio_pct") is not None
        else False
    )

    platform = summary["total_platform_reported_interactions"]
    if platform is not None and actions is not None:
        discrepancy = platform - actions
        summary["interaction_discrepancy_value"] = discrepancy
        summary["total_uncategorized_interactions"] = discrepancy if discrepancy >= 0 else None
    return summary


def aggregate_campaign(items: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Aggregate assets into isolated organic, paid, mixed and unknown buckets."""

    buckets: Dict[str, List[Mapping[str, Any]]] = {scope: [] for scope in SCOPES}
    for item in items:
        buckets[normalize_scope(item)].append(item)
    scope_buckets = {
        scope: _aggregate_bucket(bucket_items, scope) for scope, bucket_items in buckets.items()
    }
    populated = [scope for scope, bucket in buckets.items() if bucket]
    summary: Dict[str, Any] = {
        "scope_buckets": scope_buckets,
        "populated_scopes": populated,
        "reach_aggregation_warning": (
            "Reach is summed only within labeled scope buckets and is never unique campaign reach."
        ),
    }
    if len(populated) == 1:
        summary.update(scope_buckets[populated[0]])
    else:
        summary.update(
            {
                "scope": None,
                "weighted_calculated_er_by_reach": None,
                "weighted_er_lower_bound_by_reach": None,
                "er_is_complete": False,
                "er_status": "unavailable",
                "all_scope_totals": {
                    field: _sum_present(
                        [bucket for bucket in scope_buckets.values() if bucket["asset_count"]],
                        field,
                    )
                    for field in (
                        "total_views",
                        "total_likes",
                        "total_comments",
                        "total_shares",
                        "total_saves",
                        "sum_of_content_reach",
                        "total_known_engagement_actions",
                    )
                },
                "warnings": [
                    "Multiple scopes are present; no cross-scope engagement rate was calculated."
                ],
            }
        )
    return summary


def audit_campaign(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate canonical extraction output and perform deterministic auditing."""

    validated = validate_extraction(payload)
    flat_items = [flatten_asset_metrics(asset) for asset in validated["assets"]]
    audited_items = [calculate_single_item(item) for item in flat_items]
    campaign_summary = aggregate_campaign(flat_items)
    warnings = list(validated["warnings"])
    validated_status = validated["review_status"]
    item_statuses = [item.get("review_status", "verified") for item in audited_items]
    status = merge_review_status(validated_status, *item_statuses)
    if warnings:
        status = merge_review_status(status, "verified_with_warning")
    return {
        "items": audited_items,
        "campaign_summary": campaign_summary,
        "review_status": status,
        "warnings": warnings,
    }
