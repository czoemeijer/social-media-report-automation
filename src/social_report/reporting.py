"""Deterministic machine-readable exports."""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Mapping


def sanitize_csv_cell(value: Any) -> Any:
    """Neutralize spreadsheet formula injection characters at serialization boundary."""
    if not isinstance(value, str):
        return value
    stripped = value.lstrip()
    if (
        value.startswith(("\t", "\r", "\n"))
        or (stripped and stripped[0] in ("=", "+", "-", "@"))
    ):
        return f"'{value}"
    return value


def export_json(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def export_csv(payload: Mapping[str, Any]) -> bytes:
    output = io.StringIO()
    fieldnames = [
        "asset_group_id",
        "creator",
        "platform",
        "content_format",
        "scope",
        "views",
        "reach",
        "likes",
        "comments",
        "shares",
        "saves",
        "known_engagement_actions",
        "calculated_er_by_reach",
        "er_lower_bound_by_reach",
        "review_status",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    raw_items = payload.get("items") or payload.get("assets") or []
    for item in raw_items:
        if isinstance(item, Mapping):
            safe_item = {k: sanitize_csv_cell(v) for k, v in item.items()}
            writer.writerow(safe_item)
    return output.getvalue().encode("utf-8-sig")


def export_markdown(payload: Mapping[str, Any]) -> bytes:
    summary = payload.get("campaign_summary", {})
    status = str(payload.get("review_status", "unknown"))
    lines = ["# Campaign audit", "", f"Status: {status}", ""]
    if status in {"needs_review", "rejected"}:
        lines.extend(
            [
                "> [!WARNING]",
                (
                    f"> Review status is **{status.upper()}**. This report contains unverified, "
                    "low-confidence, or rejected assets that require operator review "
                    "before sharing."
                ),
                "",
            ]
        )
    for scope, bucket in summary.get("scope_buckets", {}).items():
        if not bucket.get("asset_count"):
            continue
        lines.extend(
            [
                f"## {scope}",
                "",
                f"- Assets: {bucket.get('asset_count')}",
                f"- Views: {bucket.get('total_views')}",
                f"- Sum of content reach: {bucket.get('sum_of_content_reach')}",
                f"- Complete ER by reach: {bucket.get('weighted_calculated_er_by_reach')}",
                f"- ER lower bound: {bucket.get('weighted_er_lower_bound_by_reach')}",
                "",
            ]
        )
    warnings = payload.get("warnings", [])
    if warnings:
        lines.extend(["## Warnings", ""] + [f"- {warning}" for warning in warnings])
    return "\n".join(lines).encode("utf-8")
