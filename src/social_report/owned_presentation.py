"""Human presentation formatting and evidence-bound narrative contracts."""

# ruff: noqa: E501

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Dict, List, Mapping, Optional

ACTION_LABELS = {
    "all_clicks": "All clicks",
    "link_click": "Link clicks",
    "landing_page_view": "Landing-page views",
    "post_engagement": "Post engagements",
    "post_reaction": "Reactions",
    "video_view": "Video views",
    "onsite_conversion.post_save": "Saves",
}


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, dict) else {}


def _decimal(value: object) -> Optional[Decimal]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def format_integer(value: object, unavailable: str = "Unavailable") -> str:
    number = _decimal(value)
    return f"{number:,.0f}" if number is not None else unavailable


def format_decimal(value: object, places: int = 2, unavailable: str = "Unavailable") -> str:
    number = _decimal(value)
    return f"{number:,.{places}f}" if number is not None else unavailable


def format_money(value: object, currency: object, *, precise: bool = False) -> str:
    number = _decimal(value)
    if number is None:
        return "Unavailable"
    places = 2 if precise else 0
    suffix = f" {currency}" if currency else ""
    return f"{number:,.{places}f}{suffix}"


def format_percent_ratio(value: object, places: int = 2) -> str:
    number = _decimal(value)
    return f"{number * 100:,.{places}f}%" if number is not None else "Unavailable"


def format_percent_value(value: object, places: int = 2) -> str:
    number = _decimal(value)
    return f"{number:,.{places}f}%" if number is not None else "Unavailable"


def format_seconds_ms(value: object) -> str:
    number = _decimal(value)
    return f"{number / 1000:,.2f} s" if number is not None else "Unavailable"


def format_multiple(value: object) -> str:
    number = _decimal(value)
    return f"{number:,.2f}×" if number is not None else "Unavailable"


def action_label(key: str) -> str:
    return ACTION_LABELS.get(key, key.replace("_", " ").strip().title())


def _resolve_ref(analysis: Mapping[str, object], reference: str) -> object:
    current: object = analysis
    for part in reference.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            raise ValueError(f"Narrative evidence reference does not exist: {reference}")
    return current


def validate_insights(
    narrative: Mapping[str, object], analysis: Mapping[str, object]
) -> Dict[str, List[Dict[str, object]]]:
    result: Dict[str, List[Dict[str, object]]] = {}
    for section in ("executive_summary", "observations", "recommendations"):
        raw_items = narrative.get(section, [])
        if not isinstance(raw_items, list):
            raise ValueError(f"Narrative section must be a list: {section}")
        items: List[Dict[str, object]] = []
        for raw in raw_items:
            if not isinstance(raw, dict) or not isinstance(raw.get("text"), str):
                raise ValueError(f"Narrative item in {section} requires text")
            text = raw["text"].strip()
            if not text or len(text) > 600:
                raise ValueError(f"Narrative text in {section} must contain 1-600 characters")
            ref_key = "basis_refs" if section == "recommendations" else "evidence_refs"
            refs = raw.get(ref_key, [])
            if (
                not isinstance(refs, list)
                or not refs
                or not all(isinstance(ref, str) for ref in refs)
            ):
                raise ValueError(f"Narrative item in {section} requires {ref_key}")
            for ref in refs:
                _resolve_ref(analysis, ref)
            item: Dict[str, object] = {"text": text, ref_key: list(refs)}
            if isinstance(raw.get("title"), str) and raw["title"].strip():
                item["title"] = raw["title"].strip()[:120]
            items.append(item)
        result[section] = items
    return result


def default_insights(analysis: Mapping[str, object]) -> Dict[str, List[Dict[str, object]]]:
    organic = _mapping(analysis.get("organic"))
    paid = _mapping(analysis.get("paid"))
    account = _mapping(paid.get("account"))
    comparisons = _mapping(analysis.get("comparisons"))
    format_delta = _mapping(comparisons.get("reels_vs_feed"))
    action_ratios = _mapping(comparisons.get("paid_recorded_action_ratios"))
    matching = _mapping(analysis.get("matching"))
    known_totals = _mapping(organic.get("known_totals"))
    currency = analysis.get("currency")
    reel_count = format_integer(format_delta.get("reels_count"))
    feed_count = format_integer(format_delta.get("feed_count"))
    summary = [
        {
            "text": (
                f"The period included {format_integer(organic.get('item_count'))} owned posts and "
                f"{format_integer(known_totals.get('views'))} "
                "known organic views."
            ),
            "evidence_refs": ["organic.item_count", "organic.known_totals.views"],
        },
        {
            "text": (
                f"Reels recorded {format_percent_value(format_delta.get('mean_views_difference_percent'))} "
                f"more mean views per post than Feed/Carousel in this period ({reel_count} Reels "
                f"versus {feed_count} Feed/Carousel posts)."
            ),
            "evidence_refs": [
                "comparisons.reels_vs_feed.mean_views_difference_percent",
                "comparisons.reels_vs_feed.reels_count",
                "comparisons.reels_vs_feed.feed_count",
            ],
        },
        {
            "text": (
                f"Paid delivery used {format_money(account.get('spend'), currency, precise=True)} "
                f"to record {format_integer(account.get('reach'))} reach at "
                f"{format_decimal(account.get('frequency'))} frequency."
            ),
            "evidence_refs": [
                "paid.account.spend",
                "paid.account.reach",
                "paid.account.frequency",
            ],
        },
        {
            "text": (
                f"Meta recorded {format_integer(account.get('all_clicks'))} all clicks, "
                f"{format_integer(_metric_value(account, 'link_clicks'))} link clicks, and "
                f"{format_integer(_metric_value(account, 'landing_page_views'))} landing-page views. "
                "These are distinct action definitions, not interchangeable conversion stages."
            ),
            "evidence_refs": [
                "paid.account.all_clicks",
                "paid.account.link_clicks.value",
                "paid.account.landing_page_views.value",
            ],
        },
        {
            "text": (
                f"Exact identity matching covered "
                f"{format_percent_ratio(matching.get('exact_match_coverage'))} of period creatives."
            ),
            "evidence_refs": [
                "matching.exact_match_coverage",
                "matching.exact_creative_matches",
                "matching.creatives_in_period",
            ],
        },
    ]
    observations = [
        {
            "title": "Format pattern",
            "text": (
                "Reels had higher mean and median views per post than Feed/Carousel in this period. "
                "The sample is small, so this is a period-specific pattern rather than a universal claim."
            ),
            "evidence_refs": ["comparisons.reels_vs_feed"],
        },
        {
            "title": "Recorded click actions",
            "text": (
                f"Link clicks represented {format_percent_ratio(action_ratios.get('link_clicks_per_all_clicks'))} "
                "of all clicks, while recorded landing-page views represented "
                f"{format_percent_ratio(action_ratios.get('landing_views_per_link_click'))} of link clicks. "
                "The report does not establish why the counts differ."
            ),
            "evidence_refs": ["comparisons.paid_recorded_action_ratios"],
        },
    ]
    recommendations = [
        {
            "text": (
                "Test additional Reels while monitoring the same per-post view, reach, interaction, "
                "and watch-time measures; retain the sample-size caveat."
            ),
            "basis_refs": ["comparisons.reels_vs_feed"],
        },
        {
            "text": (
                "Verify Meta action tracking and landing-page measurement before interpreting the "
                "difference between link clicks and landing-page views."
            ),
            "basis_refs": ["comparisons.paid_recorded_action_ratios"],
        },
        {
            "text": (
                "Review unmatched creatives and preserve exact source identifiers; do not replace "
                "the remaining identity gap with fuzzy matching."
            ),
            "basis_refs": ["matching.unmatched_creatives", "matching.exact_match_coverage"],
        },
    ]
    return validate_insights(
        {
            "executive_summary": summary,
            "observations": observations,
            "recommendations": recommendations,
        },
        analysis,
    )


def _metric_value(account: Mapping[str, object], key: str) -> object:
    value = account.get(key)
    return value.get("value") if isinstance(value, dict) else None
