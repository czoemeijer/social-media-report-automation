"""Self-contained, print-first HTML renderer for owned-media analytics."""

# ruff: noqa: E501

from __future__ import annotations

import html
from decimal import Decimal, InvalidOperation
from typing import Callable, List, Mapping, Optional, Sequence, Tuple

from .owned_presentation import (
    format_decimal,
    format_integer,
    format_money,
    format_multiple,
    format_percent_ratio,
    format_percent_value,
    format_seconds_ms,
)

TRANSLATIONS = {
    "en": {
        "title": "Owned media performance report",
        "summary": "Executive summary",
        "organic": "Organic performance",
        "formats": "Content format and Reels",
        "paid": "Paid delivery and actions",
        "campaigns": "Campaign performance by objective",
        "matching": "Paid and organic linkage",
        "observations": "Key observations",
        "recommendations": "Recommended next steps",
        "method": "Methodology and limitations",
        "definitions": "What these metrics mean",
        "unavailable": "Unavailable",
    },
    "cs": {
        "title": "Přehled výkonnosti vlastních médií",
        "summary": "Souhrn",
        "organic": "Organický výkon",
        "formats": "Formáty obsahu a Reels",
        "paid": "Placené doručení a akce",
        "campaigns": "Výkon kampaní podle cíle",
        "matching": "Propojení placeného a organického obsahu",
        "observations": "Klíčová zjištění",
        "recommendations": "Doporučené další kroky",
        "method": "Metodika a omezení",
        "definitions": "Význam metrik",
        "unavailable": "Nedostupné",
    },
    "zh": {
        "title": "自有媒体效果报告",
        "summary": "执行摘要",
        "organic": "自然内容表现",
        "formats": "内容形式与 Reels",
        "paid": "付费投放与动作",
        "campaigns": "按目标分析广告系列",
        "matching": "付费与自然内容关联",
        "observations": "关键观察",
        "recommendations": "建议的下一步",
        "method": "方法与限制",
        "definitions": "指标说明",
        "unavailable": "不可用",
    },
}


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


def _text(value: object, unavailable: str = "Unavailable") -> str:
    return html.escape(str(value)) if value is not None and value != "" else unavailable


def _metric_value(container: Mapping[str, object], key: str) -> object:
    metric = container.get(key)
    return metric.get("value") if isinstance(metric, dict) else None


def _human_campaign_name(value: object) -> str:
    text = " ".join(str(value or "").replace("_", " ").split())
    for prefix in ("INV - Boost - ", "Boost - "):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    return text[:82].rstrip() or "Unnamed campaign"


def _bar_chart(
    title: str,
    series: Sequence[Tuple[str, object]],
    *,
    chart_id: str,
    formatter: Callable[[object], str] = format_integer,
    color: str = "#1b5fbf",
) -> str:
    known = [(label, value) for label, raw in series if (value := _decimal(raw)) is not None]
    if not known:
        body = '<p class="empty">No available values for this chart.</p>'
    else:
        maximum = max(value for _, value in known) or Decimal("1")
        height = max(74, 22 + len(known) * 27)
        rows = []
        for index, (label, value) in enumerate(known):
            width = max(1, int(value / maximum * Decimal("56")))
            y = 15 + index * 27
            rows.append(
                f'<text x="1" y="{y + 12}" class="label">{html.escape(str(label)[:38])}</text><rect x="39%" y="{y}" width="{width}%" height="15" rx="2" fill="{color}" /><text x="98%" y="{y + 12}" text-anchor="end" class="value">{html.escape(formatter(value))}</text>'
            )
        body = (
            f'<svg viewBox="0 0 700 {height}" role="img" aria-label="{html.escape(title)}">'
            + "".join(rows)
            + "</svg>"
        )
    return f'<figure class="chart" data-chart="{html.escape(chart_id)}"><figcaption>{html.escape(title)}</figcaption>{body}</figure>'


def _kpis(items: Sequence[Tuple[str, str, str]]) -> str:
    return (
        '<div class="kpis">'
        + "".join(
            f'<div class="kpi"><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong><small>{html.escape(note)}</small></div>'
            for label, value, note in items
        )
        + "</div>"
    )


def _table(headers: Sequence[str], rows: Sequence[Sequence[object]], unavailable: str) -> str:
    if not rows:
        return f'<p class="empty">{html.escape(unavailable)}</p>'
    head = "".join(f"<th>{html.escape(item)}</th>" for item in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{_text(value, unavailable)}</td>" for value in row) + "</tr>"
        for row in rows
    )
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _narrative_list(items: object, *, titled: bool = False) -> str:
    rows = _rows(items)
    if titled:
        return (
            '<div class="observations">'
            + "".join(
                f"<article><h3>{_text(row.get('title'), 'Observation')}</h3><p>{_text(row.get('text'), '')}</p></article>"
                for row in rows
            )
            + "</div>"
        )
    return (
        '<ul class="narrative">'
        + "".join(f"<li>{_text(row.get('text'), '')}</li>" for row in rows)
        + "</ul>"
    )


def export_owned_html(
    report: Mapping[str, object],
    analysis: Mapping[str, object],
    narrative: Optional[Mapping[str, object]] = None,
    *,
    language: str = "en",
) -> bytes:
    labels = TRANSLATIONS.get(language)
    if labels is None:
        raise ValueError("language must be en, cs, or zh")
    unavailable = labels["unavailable"]
    narrative = narrative or {}
    period = _mapping(analysis.get("period"))
    organic = _mapping(analysis.get("organic"))
    totals = _mapping(organic.get("known_totals"))
    reels = _mapping(organic.get("reels"))
    paid = _mapping(analysis.get("paid"))
    account = _mapping(paid.get("account"))
    matching = _mapping(analysis.get("matching"))
    comparisons = _mapping(analysis.get("comparisons"))
    format_delta = _mapping(comparisons.get("reels_vs_feed"))
    action_ratios = _mapping(comparisons.get("paid_recorded_action_ratios"))
    snapshot = _mapping(analysis.get("snapshot"))
    currency = analysis.get("currency")
    profile = _mapping(report.get("instagram_profile"))
    ad_account = _mapping(report.get("ad_account"))
    format_rows = _rows(organic.get("format_comparison"))
    organic_items = _rows(organic.get("items"))
    objective_rows = _rows(paid.get("objective_groups"))
    matched_items = _rows(matching.get("items"))
    campaigns = [
        campaign for objective in objective_rows for campaign in _rows(objective.get("campaigns"))
    ]
    awareness = sorted(
        [row for row in campaigns if row.get("objective_group") == "awareness"],
        key=lambda row: int(_decimal(row.get("rank_within_objective")) or Decimal("9999")),
    )
    engagement = sorted(
        [row for row in campaigns if row.get("objective_group") == "engagement"],
        key=lambda row: int(_decimal(row.get("rank_within_objective")) or Decimal("9999")),
    )

    organic_chart = _bar_chart(
        "Organic views by content",
        [(str(row.get("label")), row.get("views")) for row in organic_items],
        chart_id="organic-content",
    )
    format_chart = _bar_chart(
        "Mean views per post",
        [(str(row.get("format")), _mapping(row.get("views")).get("mean")) for row in format_rows],
        chart_id="format-comparison",
        color="#d6523b",
    )
    spend_chart = _bar_chart(
        "Spend by objective",
        [
            (str(row.get("objective_group")).title(), _mapping(row.get("totals")).get("spend"))
            for row in objective_rows
        ],
        chart_id="paid-spend-objective",
        formatter=lambda value: format_money(value, currency),
        color="#0b7a75",
    )
    traffic_chart = _bar_chart(
        "Recorded traffic actions",
        [
            ("All clicks", account.get("all_clicks")),
            ("Link clicks", _metric_value(account, "link_clicks")),
            ("Landing-page views", _metric_value(account, "landing_page_views")),
        ],
        chart_id="traffic-actions",
    )
    engagement_chart = _bar_chart(
        "Recorded engagement actions",
        [
            ("Post engagements", _metric_value(account, "post_engagements")),
            ("Reactions", _metric_value(account, "post_reactions")),
            ("Saves", _metric_value(account, "post_saves")),
        ],
        chart_id="engagement-actions",
        color="#6a4bc6",
    )
    awareness_chart = _bar_chart(
        "Awareness campaign CPM",
        [
            (_human_campaign_name(row.get("campaign_name")), row.get("efficiency_value"))
            for row in awareness
        ],
        chart_id="awareness-efficiency",
        formatter=lambda value: format_money(value, currency, precise=True),
        color="#0b7a75",
    )
    engagement_efficiency_chart = _bar_chart(
        "Engagement campaign cost per engagement",
        [
            (_human_campaign_name(row.get("campaign_name")), row.get("efficiency_value"))
            for row in engagement
        ],
        chart_id="engagement-efficiency",
        formatter=lambda value: format_money(value, currency, precise=True),
        color="#6a4bc6",
    )
    matched_chart = _bar_chart(
        "Paid spend on matched owned content",
        [(str(row.get("label")), row.get("paid_spend")) for row in matched_items],
        chart_id="paid-organic-matched",
        formatter=lambda value: format_money(value, currency),
        color="#c2412d",
    )

    best_content = sorted(
        organic_items, key=lambda row: -(_decimal(row.get("views")) or Decimal("0"))
    )[:5]
    content_table = _table(
        ("Content", "Format", "Views", "Reach", "Interactions"),
        [
            (
                row.get("label"),
                row.get("format"),
                format_integer(row.get("views")),
                format_integer(row.get("reach")),
                format_integer(row.get("interactions")),
            )
            for row in best_content
        ],
        unavailable,
    )
    format_table = _table(
        ("Format", "Posts", "Mean views", "Median views", "Mean reach", "Mean interaction rate"),
        [
            (
                row.get("format"),
                format_integer(row.get("count")),
                format_integer(_mapping(row.get("views")).get("mean")),
                format_integer(_mapping(row.get("views")).get("median")),
                format_integer(_mapping(row.get("reach")).get("mean")),
                format_percent_ratio(_mapping(row.get("interaction_per_reach")).get("mean")),
            )
            for row in format_rows
        ],
        unavailable,
    )
    awareness_table = _table(
        ("Rank", "Campaign", "Spend", "Reach", "Impressions", "CPM", "Frequency"),
        [
            (
                row.get("rank_within_objective"),
                _human_campaign_name(row.get("campaign_name")),
                format_money(_mapping(row.get("metrics")).get("spend"), currency),
                format_integer(_mapping(row.get("metrics")).get("reach")),
                format_integer(_mapping(row.get("metrics")).get("impressions")),
                format_money(_mapping(row.get("metrics")).get("cpm"), currency, precise=True),
                format_decimal(_mapping(row.get("metrics")).get("frequency")),
            )
            for row in awareness
        ],
        unavailable,
    )
    engagement_table = _table(
        (
            "Rank",
            "Campaign",
            "Spend",
            "Post engagements",
            "Cost / engagement",
            "Reactions",
            "Video views",
        ),
        [
            (
                row.get("rank_within_objective"),
                _human_campaign_name(row.get("campaign_name")),
                format_money(_mapping(row.get("metrics")).get("spend"), currency),
                format_integer(_metric_value(_mapping(row.get("metrics")), "post_engagements")),
                format_money(row.get("efficiency_value"), currency, precise=True),
                format_integer(_metric_value(_mapping(row.get("metrics")), "post_reactions")),
                format_integer(_metric_value(_mapping(row.get("metrics")), "video_views")),
            )
            for row in engagement
        ],
        unavailable,
    )
    warning_values = analysis.get("warnings")
    warnings = (
        [str(item) for item in warning_values if isinstance(item, str)]
        if isinstance(warning_values, list)
        else []
    )
    warnings.extend([str(organic.get("reach_warning")), str(reels.get("limitations"))])
    warning_list = "".join(f"<li>{html.escape(item)}</li>" for item in warnings if item)

    document = f"""<!doctype html>
<html lang="{html.escape(language)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(labels["title"])}</title>
<style>
@page{{size:A4;margin:14mm 13mm 16mm}}:root{{--ink:#13273e;--muted:#5b6d7d;--paper:#edf3f8;--card:#fff;--line:#c9d6e1;--accent:#1b5fbf;--signal:#d6523b}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:14px/1.48 "Avenir Next","Helvetica Neue",Arial,sans-serif}}main{{max-width:920px;margin:auto;background:var(--card);padding:40px 48px 64px}}header{{border-top:8px solid var(--accent);padding-top:24px;margin-bottom:28px}}h1{{font-size:2.65rem;line-height:1.02;letter-spacing:-.04em;margin:4px 0 18px}}h2{{font-size:1.45rem;line-height:1.2;letter-spacing:-.02em;margin:42px 0 16px;border-bottom:1px solid var(--line);padding-bottom:8px}}h3{{font-size:1rem;margin:0 0 5px}}.kicker,.meta,small{{color:var(--muted)}}.kicker{{font-weight:650}}.meta{{display:grid;grid-template-columns:2fr 1fr;gap:8px 24px;border-top:1px solid var(--line);padding-top:14px}}.meta span:first-child{{color:var(--accent);font-weight:700}}.kpis{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border-top:1px solid var(--line);border-left:1px solid var(--line)}}.kpi{{min-height:88px;padding:13px;border-right:1px solid var(--line);border-bottom:1px solid var(--line)}}.kpi span,.kpi small{{display:block}}.kpi strong{{display:block;font-size:1.35rem;font-variant-numeric:tabular-nums;margin:4px 0}}.summary{{font-size:1.02rem;max-width:78ch}}.summary li,.narrative li{{margin:0 0 8px}}.recommendation{{border-left:4px solid var(--signal);background:#fff5f1;padding:14px 18px;margin:18px 0}}.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.chart{{margin:16px 0;background:#fbfdff;border:1px solid var(--line);padding:14px;break-inside:avoid}}figcaption{{font-weight:700;margin-bottom:8px}}svg{{width:100%;height:auto;overflow:visible}}svg text{{font-size:11px;fill:var(--ink)}}svg .value{{font-variant-numeric:tabular-nums}}.table-wrap{{overflow:hidden;border:1px solid var(--line);margin:12px 0 18px;break-inside:auto}}table{{border-collapse:collapse;width:100%;table-layout:auto}}thead{{display:table-header-group}}th,td{{padding:7px 8px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}}th{{font-size:.75rem;color:var(--muted);background:#f3f7fa}}td{{font-variant-numeric:tabular-nums}}tr{{break-inside:avoid}}.callout{{border-left:4px solid var(--accent);background:#f1f6fc;padding:12px 15px;max-width:78ch}}.observations{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.observations article{{border-top:3px solid var(--accent);padding:12px 0}}.observations p{{margin:0}}.definitions{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}.definitions div{{border-top:1px solid var(--line);padding-top:8px}}.definitions strong,.definitions span{{display:block}}.definitions span{{color:var(--muted);font-size:.88rem}}.section{{break-inside:auto}}.page-section{{break-before:page}}.empty{{color:var(--muted);font-style:italic}}footer{{margin-top:36px;padding-top:12px;border-top:1px solid var(--line);color:var(--muted);font-size:.8rem}}
@media(max-width:720px){{main{{padding:28px 18px}}.kpis{{grid-template-columns:repeat(2,1fr)}}.two-col,.observations,.definitions{{grid-template-columns:1fr}}.meta{{grid-template-columns:1fr}}}}@media print{{body{{background:white;-webkit-print-color-adjust:exact;print-color-adjust:exact}}main{{max-width:none;padding:0}}header{{margin-top:0}}h2{{break-after:avoid}}.chart,.kpi,.callout,.recommendation,.observations article{{break-inside:avoid}}.page-section{{break-before:page}}a{{color:inherit;text-decoration:none}}}}
</style></head><body><main>
<header><div class="kicker">{html.escape(labels["summary"])}</div><h1>{html.escape(labels["title"])}</h1><div class="meta"><span>{_text(period.get("date_from"))} to {_text(period.get("date_to"))}</span><span>{_text(profile.get("username") or profile.get("name"))}</span><span>{_text(ad_account.get("name"))}</span><span>Snapshot: {_text(snapshot.get("captured_at") or report.get("retrieved_at"))}</span></div></header>
<section class="section"><h2>{html.escape(labels["summary"])}</h2><div class="summary">{_narrative_list(narrative.get("executive_summary"))}</div><div class="recommendation"><strong>Priority next step</strong>{_narrative_list(_rows(narrative.get("recommendations"))[:1])}</div>{_kpis((("Organic content", format_integer(organic.get("item_count")), "owned posts"), ("Organic views", format_integer(totals.get("views")), "platform reported"), ("Interactions", format_integer(totals.get("platform_reported_interactions")), "platform reported"), ("Reel watch time", format_seconds_ms(_mapping(reels.get("avg_watch_time_ms")).get("mean")), "mean per Reel"), ("Paid spend", format_money(account.get("spend"), currency, precise=True), "account Insights"), ("Paid reach", format_integer(account.get("reach")), "Meta paid scope"), ("Impressions", format_integer(account.get("impressions")), "ad delivery"), ("Frequency", format_decimal(account.get("frequency")), "impressions / reach")))}</section>
<section class="page-section"><h2>{html.escape(labels["organic"])}</h2>{organic_chart}{content_table}</section>
<section class="section"><h2>{html.escape(labels["formats"])}</h2><p class="callout">Reels had {format_percent_value(format_delta.get("mean_views_difference_percent"))} more mean views per post and {format_percent_value(format_delta.get("mean_reach_difference_percent"))} more mean reach per post than Feed/Carousel in this period. Sample: {format_integer(format_delta.get("reels_count"))} Reels and {format_integer(format_delta.get("feed_count"))} Feed/Carousel posts.</p>{format_table}{format_chart}{_kpis((("Reel mean views", format_integer(_mapping(reels.get("views")).get("mean")), "per post"), ("Reel median views", format_integer(_mapping(reels.get("views")).get("median")), "per post"), ("Reel mean reach", format_integer(_mapping(reels.get("reach")).get("mean")), "per post"), ("Views / reach", format_multiple(_mapping(reels.get("views_per_reach")).get("mean")), "content ratio"), ("Mean watch time", format_seconds_ms(_mapping(reels.get("avg_watch_time_ms")).get("mean")), "platform reported"), ("Mean shares", format_decimal(_mapping(reels.get("shares")).get("mean")), "per Reel")))}</section>
<section class="page-section"><h2>{html.escape(labels["paid"])}</h2>{_kpis((("Spend", format_money(account.get("spend"), currency, precise=True), "account Insights"), ("Reach", format_integer(account.get("reach")), "Meta paid scope"), ("Impressions", format_integer(account.get("impressions")), "ad delivery"), ("Frequency", format_decimal(account.get("frequency")), "impressions / reach"), ("CTR", format_percent_value(account.get("ctr_percent")), "all clicks / impressions"), ("CPM", format_money(account.get("cpm"), currency, precise=True), "per 1,000 impressions"), ("Link clicks", format_integer(_metric_value(account, "link_clicks")), "distinct action"), ("Video views", format_integer(_metric_value(account, "video_views")), "distinct action")))}</section><div class="two-col">{traffic_chart}{engagement_chart}</div><p class="callout">All clicks are not link clicks, and link clicks are not landing-page views. Link clicks were {format_percent_ratio(action_ratios.get("link_clicks_per_all_clicks"))} of all clicks; recorded landing-page views were {format_percent_ratio(action_ratios.get("landing_views_per_link_click"))} of link clicks. These recorded-action ratios do not establish a website conversion rate or a cause for the gap.</p>{spend_chart}
<section class="page-section"><h2>{html.escape(labels["campaigns"])}</h2><h3>Awareness</h3><p>Ranked by CPM within Awareness campaigns only.</p>{awareness_table}{awareness_chart}<h3>Engagement</h3><p>Ranked by cost per recorded post engagement within Engagement campaigns only.</p>{engagement_table}{engagement_efficiency_chart}</section>
<section class="page-section"><h2>{html.escape(labels["matching"])}</h2>{_kpis((("Period creatives", format_integer(matching.get("creatives_in_period")), "paid creative rows"), ("Exact matches", format_integer(matching.get("exact_creative_matches")), "exact identifiers"), ("Match coverage", format_percent_ratio(matching.get("exact_match_coverage")), "period creatives"), ("Unmatched", format_integer(matching.get("unmatched_creatives")), "no fuzzy substitute"), ("Ambiguous", format_integer(matching.get("ambiguous_creatives")), "requires review"), ("Matched owned items", format_integer(matching.get("matched_owned_media_items")), "distinct period content")))}</section>{matched_chart}
<section class="section"><h2>{html.escape(labels["observations"])}</h2>{_narrative_list(narrative.get("observations"), titled=True)}<h2>{html.escape(labels["recommendations"])}</h2>{_narrative_list(narrative.get("recommendations"))}</section>
<section class="section"><h2>{html.escape(labels["definitions"])}</h2><div class="definitions"><div><strong>Reach</strong><span>Unique accounts Meta reports as reached in the relevant paid scope.</span></div><div><strong>Impressions</strong><span>Number of times ads were delivered.</span></div><div><strong>Frequency</strong><span>Average paid impressions per reached account.</span></div><div><strong>CTR</strong><span>Recorded clicks divided by impressions.</span></div><div><strong>CPC / CPM</strong><span>Spend per click / per 1,000 impressions.</span></div><div><strong>Average watch time</strong><span>Platform-reported Reel watch time; it does not establish completion.</span></div></div><h2>{html.escape(labels["method"])}</h2><ul class="narrative">{warning_list}</ul><p>Snapshot status: {_text(snapshot.get("status"))}. Captured at: {_text(snapshot.get("captured_at") or report.get("retrieved_at"))}. Missing values remain unavailable rather than zero.</p></section>
<footer>Deterministic calculations with evidence-bound narrative. No external scripts, fonts, analytics, or network assets.</footer></main></body></html>"""
    return document.encode("utf-8")
