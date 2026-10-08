"""Deterministic, presentation-neutral analytics for owned-media reports."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from statistics import median
from typing import Dict, List, Mapping, Optional, Sequence


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, dict) else {}


def _rows(value: object) -> List[Mapping[str, object]]:
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _decimal(value: object) -> Optional[Decimal]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _value(value: Optional[Decimal]) -> Optional[str]:
    if value is None:
        return None
    return format(value.quantize(Decimal("0.000001")).normalize(), "f")


def _sum(rows: Sequence[Mapping[str, object]], key: str) -> Optional[Decimal]:
    values = [_decimal(row.get(key)) for row in rows]
    present = [value for value in values if value is not None]
    return sum(present, Decimal("0")) if present else None


def _ratio(numerator: object, denominator: object, multiplier: str = "1") -> Optional[Decimal]:
    top = _decimal(numerator)
    bottom = _decimal(denominator)
    return top / bottom * Decimal(multiplier) if top is not None and bottom else None


def _distribution(values: Sequence[Optional[Decimal]]) -> Mapping[str, object]:
    known = [value for value in values if value is not None]
    return {
        "known_count": len(known),
        "mean": _value(sum(known, Decimal("0")) / len(known)) if known else None,
        "median": _value(Decimal(str(median(known)))) if known else None,
    }


def _format(identity: Mapping[str, object]) -> str:
    product = str(identity.get("media_product_type") or "").upper()
    media_type = str(identity.get("media_type") or "").upper()
    return "Reels" if product == "REELS" else "Feed/Carousel" if product or media_type else "Other"


def _short_content_name(value: object) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return None
    text = re.sub(r"[_|]+", " ", value)
    text = re.sub(r"^(?:IG|FB)\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\d{1,2}[. /-]\d{1,2}(?:[. /-]\d{2,4})?\s+", "", text)
    text = re.sub(r"\s+\d[\d .]*(?:Kč|CZK|EUR|USD)\s*$", "", text, flags=re.IGNORECASE)
    text = " ".join(text.split()).strip(" -/")
    return text[:64].rstrip() if text else None


def _published_label(value: object) -> str:
    text = str(value or "")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.strftime("%d %b").lstrip("0")
    except ValueError:
        return text[:10] or "Undated"


def _human_content_label(
    row: Mapping[str, object],
    identity: Mapping[str, object],
    ads_by_id: Mapping[str, Mapping[str, object]],
) -> str:
    topic = _short_content_name(identity.get("caption") or identity.get("title"))
    if topic is None:
        paid_rows = _rows(_mapping(row.get("paid")).get("ad_insights"))
        topic = next(
            (
                name
                for insight in paid_rows
                if (
                    name := _short_content_name(
                        ads_by_id.get(str(insight.get("ad_id")), {}).get("name")
                    )
                )
            ),
            None,
        )
    published = _published_label(identity.get("timestamp"))
    return f"{published} - {topic}" if topic else f"{published} - {_format(identity)}"


def _actions(rows: Sequence[Mapping[str, object]]) -> Dict[str, Decimal]:
    result: Dict[str, Decimal] = {}
    for row in rows:
        for name, value in _mapping(row.get("actions_normalized")).items():
            number = _decimal(value)
            if number is not None:
                result[str(name)] = result.get(str(name), Decimal("0")) + number
    return result


def _action_metric(actions: Mapping[str, Decimal], name: str) -> Mapping[str, object]:
    value = actions.get(name)
    return {"available": value is not None, "value": _value(value)}


def _paid_summary(rows: Sequence[Mapping[str, object]]) -> Mapping[str, object]:
    spend = _sum(rows, "spend")
    impressions = _sum(rows, "impressions")
    clicks = _sum(rows, "clicks")
    reach = _decimal(rows[0].get("reach")) if len(rows) == 1 else None
    actions = _actions(rows)
    return {
        "spend": _value(spend),
        "impressions": _value(impressions),
        "reach": _value(reach),
        "all_clicks": _value(clicks),
        "ctr_percent": _value(_ratio(clicks, impressions, "100")),
        "cpc": _value(spend / clicks) if spend is not None and clicks else None,
        "cpm": _value(spend / impressions * 1000) if spend is not None and impressions else None,
        "frequency": _value(_decimal(rows[0].get("frequency"))) if len(rows) == 1 else None,
        "actions": {name: _value(value) for name, value in sorted(actions.items())},
        "link_clicks": _action_metric(actions, "link_click"),
        "landing_page_views": _action_metric(actions, "landing_page_view"),
        "post_engagements": _action_metric(actions, "post_engagement"),
        "post_reactions": _action_metric(actions, "post_reaction"),
        "video_views": _action_metric(actions, "video_view"),
        "post_saves": _action_metric(actions, "onsite_conversion.post_save"),
    }


def _organic(report: Mapping[str, object]) -> Mapping[str, object]:
    content = sorted(
        _rows(report.get("content")),
        key=lambda row: (
            str(_mapping(row.get("identity")).get("timestamp") or ""),
            str(_mapping(row.get("identity")).get("media_id") or ""),
        ),
    )
    owned = [row for row in content if isinstance(row.get("organic"), dict)]
    ads = _mapping(report.get("ads"))
    ads_by_id = {str(row.get("id")): row for row in _rows(ads.get("ads")) if row.get("id")}
    items: List[Mapping[str, object]] = []
    formats: Dict[str, List[Mapping[str, object]]] = {}
    for index, row in enumerate(owned, 1):
        identity = _mapping(row.get("identity"))
        metrics = _mapping(row.get("organic"))
        item_format = _format(identity)
        item = {
            "label": _human_content_label(row, identity, ads_by_id),
            "audit_alias": f"Media #{index:02d}",
            "media_id": identity.get("media_id"),
            "published": str(identity.get("timestamp") or "")[:10] or None,
            "format": item_format,
            "views": metrics.get("views"),
            "reach": metrics.get("reach"),
            "interactions": metrics.get("platform_reported_total_interactions"),
            "saves": metrics.get("saved"),
            "shares": metrics.get("shares"),
            "avg_watch_time_ms": metrics.get("avg_watch_time_ms"),
        }
        items.append(item)
        formats.setdefault(item_format, []).append(item)

    totals = {
        key: _value(_sum([_mapping(row.get("organic")) for row in owned], source))
        for key, source in (
            ("views", "views"),
            ("likes", "likes"),
            ("comments", "comments"),
            ("saves", "saved"),
            ("shares", "shares"),
            ("platform_reported_interactions", "platform_reported_total_interactions"),
        )
    }
    reach_sum = _sum([_mapping(row.get("organic")) for row in owned], "reach")
    weighted_rates = {
        "content_weighted_interaction_rate": _value(
            _ratio(totals["platform_reported_interactions"], reach_sum)
        ),
        "content_weighted_save_rate": _value(_ratio(totals["saves"], reach_sum)),
        "content_weighted_share_rate": _value(_ratio(totals["shares"], reach_sum)),
        "content_weighted_views_per_reach": _value(_ratio(totals["views"], reach_sum)),
    }
    comparisons: List[Mapping[str, object]] = []
    for name in sorted(formats):
        rows = formats[name]
        comparisons.append(
            {
                "format": name,
                "count": len(rows),
                "views": _distribution([_decimal(row.get("views")) for row in rows]),
                "reach": _distribution([_decimal(row.get("reach")) for row in rows]),
                "interactions": _distribution([_decimal(row.get("interactions")) for row in rows]),
                "interaction_per_reach": _distribution(
                    [_ratio(row.get("interactions"), row.get("reach")) for row in rows]
                ),
                "save_per_reach": _distribution(
                    [_ratio(row.get("saves"), row.get("reach")) for row in rows]
                ),
                "share_per_reach": _distribution(
                    [_ratio(row.get("shares"), row.get("reach")) for row in rows]
                ),
                "views_per_reach": _distribution(
                    [_ratio(row.get("views"), row.get("reach")) for row in rows]
                ),
            }
        )
    reels = [row for row in items if row["format"] == "Reels"]
    return {
        "item_count": len(owned),
        "known_totals": totals,
        "weighted_content_rates": weighted_rates,
        "reach_warning": (
            "Rates use the sum of content-level reach as a weighting denominator; audiences may "
            "overlap, so this is not unique account reach."
        ),
        "format_comparison": comparisons,
        "reels": {
            "count": len(reels),
            "views": _distribution([_decimal(row.get("views")) for row in reels]),
            "reach": _distribution([_decimal(row.get("reach")) for row in reels]),
            "avg_watch_time_ms": _distribution(
                [_decimal(row.get("avg_watch_time_ms")) for row in reels]
            ),
            "views_per_reach": _distribution(
                [_ratio(row.get("views"), row.get("reach")) for row in reels]
            ),
            "interaction_per_reach": _distribution(
                [_ratio(row.get("interactions"), row.get("reach")) for row in reels]
            ),
            "shares": _distribution([_decimal(row.get("shares")) for row in reels]),
            "saves": _distribution([_decimal(row.get("saves")) for row in reels]),
            "limitations": "No completion or retention claim is derived without duration data.",
        },
        "items": items,
    }


def _objective_group(value: object) -> str:
    text = str(value or "UNKNOWN").upper()
    for group in ("AWARENESS", "ENGAGEMENT", "TRAFFIC", "SALES"):
        if group in text:
            return group.lower()
    return "other"


def _campaign_metrics(row: Mapping[str, object]) -> Mapping[str, object]:
    summary = _paid_summary([row])
    return {
        key: summary.get(key)
        for key in (
            "spend",
            "impressions",
            "reach",
            "all_clicks",
            "ctr_percent",
            "cpc",
            "cpm",
            "frequency",
            "link_clicks",
            "landing_page_views",
            "post_engagements",
            "post_reactions",
            "video_views",
            "post_saves",
        )
    }


def _campaigns(report: Mapping[str, object]) -> List[Mapping[str, object]]:
    ads = _mapping(report.get("ads"))
    insights = _mapping(ads.get("insights"))
    metadata = {str(row.get("id")): row for row in _rows(ads.get("campaigns")) if row.get("id")}
    result: List[Dict[str, object]] = []
    for row in _rows(insights.get("campaign")):
        campaign_id = str(row.get("campaign_id") or "unknown")
        objective = metadata.get(campaign_id, {}).get("objective")
        actions = _actions([row])
        spend = _decimal(row.get("spend"))
        impressions = _decimal(row.get("impressions"))
        link_clicks = actions.get("link_click")
        landing_views = actions.get("landing_page_view")
        engagements = actions.get("post_engagement")
        purchases = sum(
            (
                value
                for name, value in actions.items()
                if name == "purchase" or name.endswith("purchase")
            ),
            Decimal("0"),
        )
        group = _objective_group(objective)
        efficiency_name: Optional[str] = None
        efficiency_value: Optional[Decimal] = None
        if group == "awareness":
            efficiency_name = "cpm"
            efficiency_value = (
                spend / impressions * 1000 if spend is not None and impressions else None
            )
        elif group == "engagement":
            efficiency_name = "cost_per_post_engagement"
            efficiency_value = spend / engagements if spend is not None and engagements else None
        elif group == "traffic":
            efficiency_name = (
                "cost_per_landing_page_view" if landing_views else "cost_per_link_click"
            )
            denominator = landing_views or link_clicks
            efficiency_value = spend / denominator if spend is not None and denominator else None
        elif group == "sales":
            efficiency_name = "cost_per_purchase"
            efficiency_value = spend / purchases if spend is not None and purchases else None
        result.append(
            {
                "campaign_id": campaign_id,
                "campaign_name": row.get("campaign_name")
                or metadata.get(campaign_id, {}).get("name"),
                "objective": objective,
                "objective_group": group,
                "metrics": _campaign_metrics(row),
                "purchase_actions": _value(purchases) if purchases else None,
                "efficiency_metric": efficiency_name,
                "efficiency_value": _value(efficiency_value),
            }
        )
    for group in sorted({str(row["objective_group"]) for row in result}):
        comparable = [
            row
            for row in result
            if row["objective_group"] == group and row["efficiency_value"] is not None
        ]
        comparable.sort(
            key=lambda row: (
                _decimal(row["efficiency_value"]) or Decimal("0"),
                str(row["campaign_id"]),
            )
        )
        ranks = {str(row["campaign_id"]): rank for rank, row in enumerate(comparable, 1)}
        for row in result:
            if row["objective_group"] == group:
                row["rank_within_objective"] = ranks.get(str(row["campaign_id"]))
    return sorted(result, key=lambda row: (str(row["objective_group"]), str(row["campaign_id"])))


def analyze_owned_media(report: Mapping[str, object]) -> Dict[str, object]:
    """Build the compact context consumed by Skills and deterministic renderers."""

    ads = _mapping(report.get("ads"))
    insights = _mapping(ads.get("insights"))
    account_rows = _rows(insights.get("account"))
    campaigns = _campaigns(report)
    objective_groups: List[Mapping[str, object]] = []
    for group in sorted({str(row["objective_group"]) for row in campaigns}):
        group_rows = [row for row in campaigns if row["objective_group"] == group]
        source_rows = [
            row
            for row in _rows(insights.get("campaign"))
            if str(row.get("campaign_id")) in {str(item["campaign_id"]) for item in group_rows}
        ]
        objective_groups.append(
            {
                "objective_group": group,
                "campaign_count": len(group_rows),
                "totals": _paid_summary(source_rows),
                "campaigns": group_rows,
            }
        )

    organic_analysis = _organic(report)
    matches = _rows(report.get("paid_organic_matches"))
    exact_matched_ids = {
        str(row.get("organic_media_id"))
        for row in matches
        if row.get("status") == "matched" and row.get("organic_media_id")
    }
    period_media_ids = {
        str(_mapping(row.get("identity")).get("media_id"))
        for row in _rows(report.get("content"))
        if _mapping(row.get("identity")).get("media_id")
    }
    collection = _mapping(ads.get("collection"))
    ad_count = len(_rows(ads.get("ads")))
    creative_count = len(_rows(ads.get("creatives")))
    organic_labels = {
        str(row.get("media_id")): str(row.get("label"))
        for row in _rows(organic_analysis.get("items"))
        if row.get("media_id")
    }
    matched_items: List[Mapping[str, object]] = []
    for index, item in enumerate(_rows(report.get("content")), 1):
        paid_rows = _rows(_mapping(item.get("paid")).get("ad_insights"))
        if paid_rows:
            matched_items.append(
                {
                    "label": organic_labels.get(
                        str(_mapping(item.get("identity")).get("media_id")),
                        f"Media #{index:02d}",
                    ),
                    "organic_views": _mapping(item.get("organic")).get("views"),
                    "paid_spend": _value(_sum(paid_rows, "spend")),
                    "paid_impressions": _value(_sum(paid_rows, "impressions")),
                }
            )
    format_rows = {
        str(row.get("format")): row for row in _rows(organic_analysis.get("format_comparison"))
    }
    reels = format_rows.get("Reels", {})
    feed = format_rows.get("Feed/Carousel", {})

    def difference_percent(metric: str, statistic: str) -> Optional[str]:
        reel_value = _decimal(_mapping(reels.get(metric)).get(statistic))
        feed_value = _decimal(_mapping(feed.get(metric)).get(statistic))
        return (
            _value((reel_value - feed_value) / feed_value * 100)
            if reel_value is not None and feed_value
            else None
        )

    account_summary = _paid_summary(account_rows)
    all_clicks = _decimal(account_summary.get("all_clicks"))
    link_clicks = _decimal(_mapping(account_summary.get("link_clicks")).get("value"))
    landing_views = _decimal(_mapping(account_summary.get("landing_page_views")).get("value"))
    warning_values = report.get("warnings")
    return {
        "schema_version": "1.0",
        "period": report.get("report_period"),
        "currency": _mapping(report.get("ad_account")).get("currency"),
        "organic": organic_analysis,
        "paid": {
            "account": _paid_summary(account_rows),
            "objective_groups": objective_groups,
            "action_semantics": (
                "all_clicks is the Ads Insights clicks field; link clicks, landing-page views, "
                "engagements, reactions, video views, and saves remain distinct action types. "
                "Unavailable action types are not zero."
            ),
        },
        "matching": {
            "paid_ads_in_period": collection.get("ads_in_period", ad_count),
            "creatives_in_period": collection.get("creatives_in_period", creative_count),
            "exact_creative_matches": sum(row.get("status") == "matched" for row in matches),
            "unmatched_creatives": sum(row.get("status") == "unmatched" for row in matches),
            "ambiguous_creatives": sum(row.get("status") == "ambiguous" for row in matches),
            "matched_owned_media_items": len(exact_matched_ids & period_media_ids),
            "exact_match_coverage": _value(
                Decimal(sum(row.get("status") == "matched" for row in matches)) / creative_count
            )
            if creative_count
            else None,
            "items": matched_items,
        },
        "comparisons": {
            "reels_vs_feed": {
                "reels_count": reels.get("count"),
                "feed_count": feed.get("count"),
                "mean_views_difference_percent": difference_percent("views", "mean"),
                "median_views_difference_percent": difference_percent("views", "median"),
                "mean_reach_difference_percent": difference_percent("reach", "mean"),
                "mean_interaction_rate_difference_percentage_points": _value(
                    (
                        (
                            _decimal(_mapping(reels.get("interaction_per_reach")).get("mean"))
                            or Decimal("0")
                        )
                        - (
                            _decimal(_mapping(feed.get("interaction_per_reach")).get("mean"))
                            or Decimal("0")
                        )
                    )
                    * 100
                ),
            },
            "paid_recorded_action_ratios": {
                "link_clicks_per_all_clicks": _value(link_clicks / all_clicks)
                if link_clicks is not None and all_clicks
                else None,
                "landing_views_per_link_click": _value(landing_views / link_clicks)
                if landing_views is not None and link_clicks
                else None,
                "semantics": (
                    "Recorded-action ratios compare Meta action counts; they are not guaranteed "
                    "website conversion rates."
                ),
            },
        },
        "warnings": list(warning_values) if isinstance(warning_values, list) else [],
    }
