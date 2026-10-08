"""Deterministic exports for owned-media and budget reports."""

from __future__ import annotations

import csv
import io
import json
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from .budget import decimal_to_string
from .reporting import sanitize_csv_cell


def export_owned_json(payload: Mapping[str, object]) -> bytes:
    return json.dumps(
        decimal_to_string(dict(payload)), ensure_ascii=False, indent=2, sort_keys=True
    ).encode("utf-8")


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


def _sum_metric(rows: Sequence[Mapping[str, object]], key: str) -> Optional[Decimal]:
    values = [_decimal(row.get(key)) for row in rows]
    present = [value for value in values if value is not None]
    return sum(present, Decimal("0")) if present else None


def _paid_rollup(rows: Sequence[Mapping[str, object]]) -> Dict[str, object]:
    spend = _sum_metric(rows, "spend")
    impressions = _sum_metric(rows, "impressions")
    clicks = _sum_metric(rows, "clicks")
    reach = _decimal(rows[0].get("reach")) if len(rows) == 1 else None
    return {
        "row_count": len(rows),
        "spend": spend,
        "impressions": impressions,
        "reach": reach,
        "clicks": clicks,
        "ctr": (clicks / impressions * 100) if clicks is not None and impressions else None,
        "cpc": (spend / clicks) if spend is not None and clicks else None,
        "cpm": (spend / impressions * 1000) if spend is not None and impressions else None,
        "frequency": _decimal(rows[0].get("frequency")) if len(rows) == 1 else None,
        "reach_note": "single row" if len(rows) == 1 else "non-additive across rows",
    }


def _content_rows(payload: Mapping[str, object]) -> List[Mapping[str, object]]:
    return sorted(
        _rows(payload.get("content")),
        key=lambda row: (
            str(_mapping(row.get("identity")).get("timestamp") or ""),
            str(_mapping(row.get("identity")).get("media_id") or ""),
        ),
    )


def _media_labels(content: Sequence[Mapping[str, object]]) -> Mapping[str, str]:
    width = max(2, len(str(len(content))))
    return {
        str(_mapping(item.get("identity")).get("media_id") or "unknown"): (
            f"Media #{index:0{width}d}"
        )
        for index, item in enumerate(content, 1)
    }


def _display_date(value: object) -> object:
    text = str(value or "")
    return text[:10] if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-" else value


def export_owned_csv(payload: Mapping[str, object]) -> bytes:
    output = io.StringIO()
    fields = [
        "date_from",
        "date_to",
        "platform",
        "media_id",
        "permalink",
        "timestamp",
        "media_type",
        "media_product_type",
        "reference_only",
        "views",
        "reach",
        "likes",
        "comments",
        "saved",
        "shares",
        "platform_reported_total_interactions",
        "avg_watch_time_ms",
        "total_watch_time_ms",
        "paid_ad_count",
        "paid_spend",
        "paid_impressions",
        "paid_reach",
        "paid_clicks",
        "paid_ctr",
        "paid_cpc",
        "paid_cpm",
        "paid_reach_note",
        "paid_match_status",
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    period = _mapping(payload.get("report_period"))
    for item in _content_rows(payload):
        identity = _mapping(item.get("identity"))
        organic = _mapping(item.get("organic"))
        paid = _mapping(item.get("paid"))
        paid_match = _mapping(item.get("paid_match"))
        paid_rows = _rows(paid.get("ad_insights"))
        paid_summary = _paid_rollup(paid_rows)
        row = {
            "date_from": period.get("date_from"),
            "date_to": period.get("date_to"),
            **identity,
            **organic,
            "paid_ad_count": len(paid_rows),
            "paid_spend": paid_summary["spend"],
            "paid_impressions": paid_summary["impressions"],
            "paid_reach": paid_summary["reach"],
            "paid_clicks": paid_summary["clicks"],
            "paid_ctr": paid_summary["ctr"],
            "paid_cpc": paid_summary["cpc"],
            "paid_cpm": paid_summary["cpm"],
            "paid_reach_note": paid_summary["reach_note"] if paid_rows else None,
            "paid_match_status": paid_match.get("status"),
        }
        writer.writerow({key: sanitize_csv_cell(row.get(key)) for key in fields})
    return output.getvalue().encode("utf-8-sig")


def _escape(value: object) -> str:
    if value is None or value == "":
        return "Unavailable"
    return (
        str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ")
    )


def _number(value: object, *, places: int = 0) -> str:
    number = _decimal(value)
    if number is None:
        return "Unavailable"
    if places == 0:
        return f"{number:,.0f}"
    return f"{number:,.{places}f}"


def _money(value: object, currency: object) -> str:
    number = _decimal(value)
    if number is None:
        return "Unavailable"
    suffix = f" {_escape(currency)}" if currency else ""
    return f"{number:,.2f}{suffix}"


def _percent(value: object) -> str:
    return f"{_number(value, places=2)}%" if _decimal(value) is not None else "Unavailable"


def _table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> List[str]:
    if not rows:
        return ["_No data available._", ""]
    result = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    result.extend("| " + " | ".join(_escape(value) for value in row) + " |" for row in rows)
    result.append("")
    return result


def _organic_items(content: Sequence[Mapping[str, object]]) -> List[Mapping[str, object]]:
    return [item for item in content if isinstance(item.get("organic"), dict)]


def _organic_metric_total(
    content: Sequence[Mapping[str, object]], metric: str
) -> Optional[Decimal]:
    return _sum_metric([_mapping(item.get("organic")) for item in content], metric)


def _campaign_rollups(payload: Mapping[str, object]) -> List[Tuple[str, str, Dict[str, object]]]:
    ads = _mapping(payload.get("ads"))
    insights = _mapping(ads.get("insights"))
    campaign_rows = _rows(insights.get("campaign"))
    metadata = {str(row.get("id")): row for row in _rows(ads.get("campaigns")) if row.get("id")}
    grouped: Dict[str, List[Mapping[str, object]]] = {}
    for row in campaign_rows:
        campaign_id = str(row.get("campaign_id") or "unknown")
        grouped.setdefault(campaign_id, []).append(row)
    result: List[Tuple[str, str, Dict[str, object]]] = []
    for campaign_id, rows in grouped.items():
        meta = metadata.get(campaign_id, {})
        name = str(rows[0].get("campaign_name") or meta.get("name") or campaign_id)
        result.append((campaign_id, name, _paid_rollup(rows)))
    return sorted(
        result,
        key=lambda item: (
            -(_decimal(item[2].get("spend")) or Decimal("0")),
            item[0],
        ),
    )


def _top_content(
    content: Sequence[Mapping[str, object]], metric: str
) -> Optional[Tuple[str, Decimal]]:
    candidates: List[Tuple[str, Decimal]] = []
    for item in content:
        value = _decimal(_mapping(item.get("organic")).get(metric))
        if value is not None:
            media_id = str(_mapping(item.get("identity")).get("media_id") or "unknown")
            candidates.append((media_id, value))
    return sorted(candidates, key=lambda item: (-item[1], item[0]))[0] if candidates else None


def _append_budget(lines: List[str], payload: Mapping[str, object], currency: object) -> None:
    budget = _mapping(payload.get("budget_reconciliation"))
    if not budget:
        return
    summary = _mapping(budget.get("summary"))
    lines.extend(
        [
            "## Budget reconciliation",
            "",
            f"- Planned spend: {_money(summary.get('planned_spend'), currency)}",
            f"- Matched actual spend: {_money(summary.get('actual_spend'), currency)}",
            f"- Variance: {_money(summary.get('variance'), currency)}",
            f"- Matched: {_number(summary.get('matched'))}",
            f"- Unmatched: {_number(summary.get('unmatched'))}",
            f"- Ambiguous: {_number(summary.get('ambiguous'))}",
            f"- Needs review: {_number(summary.get('needs_review'))}",
            "",
        ]
    )


def export_owned_markdown(payload: Mapping[str, object]) -> bytes:
    content = _content_rows(payload)
    labels = _media_labels(content)
    organic = _organic_items(content)
    matches = _rows(payload.get("paid_organic_matches"))
    matched_count = sum(row.get("status") == "matched" for row in matches)
    reference_count = sum(
        bool(_mapping(row.get("identity")).get("reference_only")) for row in content
    )
    period = _mapping(payload.get("report_period"))
    profile = _mapping(payload.get("instagram_profile"))
    account = _mapping(payload.get("ad_account"))
    currency = account.get("currency")
    ads = _mapping(payload.get("ads"))
    account_rows = _rows(_mapping(ads.get("insights")).get("account"))
    account_summary = _paid_rollup(account_rows)
    period_text = (
        f"{period.get('date_from')} to {period.get('date_to')}"
        if period.get("date_from") or period.get("date_to")
        else "All available data (no explicit bounds)"
    )

    lines = [
        "# Owned media report",
        "",
        "## Report period",
        "",
        f"- Period: {_escape(period_text)}",
        f"- Retrieved at: {_escape(payload.get('retrieved_at'))}",
        f"- Meta API version: {_escape(payload.get('api_version'))}",
        "",
        "## Account overview",
        "",
        f"- Instagram account: {_escape(profile.get('username') or profile.get('name'))}",
        f"- Instagram followers: {_number(profile.get('followers_count'))}",
        f"- Instagram profile media count: {_number(profile.get('media_count'))}",
        f"- Ad account: {_escape(account.get('name'))}",
        f"- Ad account currency: {_escape(currency)}",
        f"- Ad account timezone: {_escape(account.get('timezone_name'))}",
        "",
        "## Executive KPIs",
        "",
        "### Organic content",
        "",
        f"- Authorized content items: {len(organic)}",
        f"- Known views: {_number(_organic_metric_total(organic, 'views'))}",
        f"- Known likes: {_number(_organic_metric_total(organic, 'likes'))}",
        f"- Known comments: {_number(_organic_metric_total(organic, 'comments'))}",
        f"- Known saves: {_number(_organic_metric_total(organic, 'saved'))}",
        f"- Known shares: {_number(_organic_metric_total(organic, 'shares'))}",
        "- Known platform-reported interactions: "
        f"{_number(_organic_metric_total(organic, 'platform_reported_total_interactions'))}",
        "- Aggregate organic reach: Not reported because content-level reach can overlap.",
        "",
        "### Paid media (account-level Insights only)",
        "",
        f"- Spend: {_money(account_summary.get('spend'), currency)}",
        f"- Impressions: {_number(account_summary.get('impressions'))}",
        f"- Reach: {_number(account_summary.get('reach'))}",
        f"- Clicks: {_number(account_summary.get('clicks'))}",
        f"- CTR: {_percent(account_summary.get('ctr'))}",
        f"- CPC: {_money(account_summary.get('cpc'), currency)}",
        f"- CPM: {_money(account_summary.get('cpm'), currency)}",
        f"- Frequency: {_number(account_summary.get('frequency'), places=2)}",
        "",
        "> Organic reach and paid reach are separate, non-additive audience domains.",
        "",
        "## Organic content",
        "",
    ]
    organic_table: List[Sequence[object]] = []
    for item in organic:
        identity = _mapping(item.get("identity"))
        metrics = _mapping(item.get("organic"))
        organic_table.append(
            (
                _display_date(identity.get("timestamp")),
                identity.get("media_product_type") or identity.get("media_type"),
                labels.get(str(identity.get("media_id"))),
                _number(metrics.get("views")),
                _number(metrics.get("reach")),
                _number(metrics.get("likes")),
                _number(metrics.get("comments")),
                _number(metrics.get("saved")),
                _number(metrics.get("shares")),
                _number(metrics.get("platform_reported_total_interactions")),
            )
        )
    lines.extend(
        _table(
            (
                "Published",
                "Type",
                "Media ID",
                "Views",
                "Reach",
                "Likes",
                "Comments",
                "Saves",
                "Shares",
                "Platform interactions",
            ),
            organic_table,
        )
    )

    lines.extend(["## Reels watch time", ""])
    reel_table: List[Sequence[object]] = []
    for item in organic:
        identity = _mapping(item.get("identity"))
        if str(identity.get("media_product_type") or "").upper() != "REELS":
            continue
        metrics = _mapping(item.get("organic"))
        average = _decimal(metrics.get("avg_watch_time_ms"))
        total = _decimal(metrics.get("total_watch_time_ms"))
        reel_table.append(
            (
                _display_date(identity.get("timestamp")),
                labels.get(str(identity.get("media_id"))),
                _number(average / 1000 if average is not None else None, places=2),
                _number(total / Decimal("3600000") if total is not None else None, places=2),
                _number(metrics.get("views")),
                _number(metrics.get("reach")),
            )
        )
    lines.extend(
        _table(
            ("Published", "Media ID", "Avg watch (s)", "Total watch (h)", "Views", "Reach"),
            reel_table,
        )
    )

    campaigns = _campaign_rollups(payload)
    lines.extend(["## Paid campaigns", ""])
    lines.extend(
        _table(
            ("Campaign", "Spend", "Impressions", "Reach", "Clicks", "CTR", "CPC", "CPM"),
            [
                (
                    name,
                    _money(summary.get("spend"), currency),
                    _number(summary.get("impressions")),
                    _number(summary.get("reach")),
                    _number(summary.get("clicks")),
                    _percent(summary.get("ctr")),
                    _money(summary.get("cpc"), currency),
                    _money(summary.get("cpm"), currency),
                )
                for _, name, summary in campaigns
            ],
        )
    )

    lines.extend(["## Paid-to-organic matched content", ""])
    matched_table: List[Sequence[object]] = []
    for item in content:
        paid_rows = _rows(_mapping(item.get("paid")).get("ad_insights"))
        if not paid_rows:
            continue
        identity = _mapping(item.get("identity"))
        summary = _paid_rollup(paid_rows)
        paid_reach = (
            _number(summary.get("reach"))
            if len(paid_rows) == 1
            else f"Not additive ({len(paid_rows)} ads)"
        )
        matched_table.append(
            (
                labels.get(str(identity.get("media_id"))),
                len(paid_rows),
                _money(summary.get("spend"), currency),
                _number(summary.get("impressions")),
                paid_reach,
                _number(summary.get("clicks")),
                _percent(summary.get("ctr")),
            )
        )
    lines.extend(
        _table(
            ("Media ID", "Ads", "Spend", "Impressions", "Paid reach", "Clicks", "CTR"),
            matched_table,
        )
    )

    lines.extend(["## Top performers", ""])
    for label, metric in (
        ("Most viewed organic item", "views"),
        ("Highest-reach organic item", "reach"),
        ("Most-liked organic item", "likes"),
        ("Most-interacted organic item", "platform_reported_total_interactions"),
    ):
        top = _top_content(organic, metric)
        lines.append(
            f"- {label}: {_escape(labels.get(top[0], top[0]))} ({_number(top[1])})"
            if top
            else f"- {label}: Unavailable"
        )
    if campaigns:
        lines.append(
            f"- Highest-spend campaign: {_escape(campaigns[0][1])} "
            f"({_money(campaigns[0][2].get('spend'), currency)})"
        )
    else:
        lines.append("- Highest-spend campaign: Unavailable")
    lines.append("")

    _append_budget(lines, payload, currency)
    lines.extend(
        [
            "## Audit notes",
            "",
            f"- Content items in report: {len(content)} ({reference_count} reference-only).",
            f"- Exact paid creative matches: {matched_count}.",
            "- Paid headline KPIs come only from account-level Insights for the report period.",
            "- Content and campaign reach are never summed when multiple rows may overlap.",
            "- Platform-reported total interactions remain separate from component sums.",
            "- Human-readable media labels map deterministically to full IDs retained in JSON/CSV.",
        ]
    )
    if len(account_rows) > 1:
        lines.append(
            "- Account Insights returned multiple rows: additive metrics were rolled up, "
            "while reach and frequency are unavailable."
        )
    warnings = payload.get("warnings")
    for warning in warnings if isinstance(warnings, list) else []:
        lines.append(f"- {_escape(warning)}")
    lines.append("")
    return "\n".join(lines).encode("utf-8")
