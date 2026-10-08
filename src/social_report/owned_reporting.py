"""Deterministic exports for owned-media and budget reports."""

from __future__ import annotations

import csv
import io
import json
from decimal import Decimal
from typing import Any, Mapping

from .budget import decimal_to_string
from .reporting import sanitize_csv_cell


def export_owned_json(payload: Mapping[str, object]) -> bytes:
    return json.dumps(
        decimal_to_string(dict(payload)), ensure_ascii=False, indent=2, sort_keys=True
    ).encode("utf-8")


def export_owned_csv(payload: Mapping[str, object]) -> bytes:
    output = io.StringIO()
    fields = [
        "platform",
        "media_id",
        "permalink",
        "timestamp",
        "media_type",
        "media_product_type",
        "views",
        "reach",
        "likes",
        "comments",
        "saved",
        "shares",
        "platform_reported_total_interactions",
        "avg_watch_time_ms",
        "total_watch_time_ms",
        "paid_match_status",
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    content = payload.get("content", [])
    for item in content if isinstance(content, list) else []:
        if not isinstance(item, dict):
            continue
        identity = item.get("identity", {})
        organic = item.get("organic", {})
        paid_match = item.get("paid_match", {})
        row = {
            **(identity if isinstance(identity, dict) else {}),
            **(organic if isinstance(organic, dict) else {}),
            "paid_match_status": paid_match.get("status") if isinstance(paid_match, dict) else None,
        }
        writer.writerow({key: sanitize_csv_cell(row.get(key)) for key in fields})
    return output.getvalue().encode("utf-8-sig")


def export_owned_markdown(payload: Mapping[str, object]) -> bytes:
    content = payload.get("content", [])
    matches = payload.get("paid_organic_matches", [])
    matched_count = (
        sum(bool(isinstance(row, dict) and row.get("status") == "matched") for row in matches)
        if isinstance(matches, list)
        else 0
    )
    lines = [
        "# Owned media report",
        "",
        f"- API version: {payload.get('api_version', 'unknown')}",
        f"- Instagram content items: {len(content) if isinstance(content, list) else 0}",
        f"- Paid creative matches: {matched_count}",
        "",
        "> Organic reach and paid reach are separate, non-additive audience domains.",
        "",
    ]
    budget = payload.get("budget_reconciliation")
    if isinstance(budget, dict):
        summary = budget.get("summary", {})
        if isinstance(summary, dict):
            lines.extend(
                [
                    "## Budget reconciliation",
                    "",
                    f"- Planned spend: {_display_money(summary.get('planned_spend'))}",
                    f"- Actual spend: {_display_money(summary.get('actual_spend'))}",
                    f"- Variance: {_display_money(summary.get('variance'))}",
                    f"- Matched: {summary.get('matched', 0)}",
                    f"- Ambiguous: {summary.get('ambiguous', 0)}",
                    f"- Needs review: {summary.get('needs_review', 0)}",
                    "",
                ]
            )
    return "\n".join(lines).encode("utf-8")


def _display_money(value: Any) -> str:
    return format(value, "f") if isinstance(value, Decimal) else str(value)
