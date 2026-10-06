"""Deterministic machine-readable exports."""

from __future__ import annotations

import csv
import io
import json
from typing import Any, Mapping


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
    writer.writeheader()
    for item in payload.get("items", []):
        if isinstance(item, Mapping):
            writer.writerow(item)
    return output.getvalue().encode("utf-8-sig")


def export_markdown(payload: Mapping[str, Any]) -> bytes:
    summary = payload.get("campaign_summary", {})
    lines = ["# Campaign audit", "", f"Status: {payload.get('review_status', 'unknown')}", ""]
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
