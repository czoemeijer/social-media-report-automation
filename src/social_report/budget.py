"""Generic CSV/TSV media-plan parsing and deterministic spend reconciliation."""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from .sources.meta.matching import normalize_permalink

DEFAULT_ALIASES: Mapping[str, Sequence[str]] = {
    "publication_date": ("publication date", "publish date", "date", "datum publikace"),
    "valid_until": ("validity", "end date", "valid until", "platnost do"),
    "platform": ("platform", "network", "kanal", "channel"),
    "targeting": ("targeting", "audience", "cileni"),
    "content_name": ("post name", "content name", "title", "task", "prispevek"),
    "task_link": ("task link", "task url", "project link"),
    "campaign": ("campaign", "category", "campaign name", "kampan"),
    "content_id_or_link": (
        "id or link",
        "content id",
        "post id",
        "permalink",
        "url",
        "odkaz",
    ),
    "planned_spend": ("planned boost", "planned spend", "planned budget", "budget"),
    "boost_enabled": ("boost enabled", "boost", "promoted"),
    "actual_spend_plan": ("actual spend", "spent", "real spend"),
    "notes": ("notes", "note", "comment", "poznamka"),
    "ad_id": ("ad id",),
    "adset_id": ("ad set id", "adset id"),
    "campaign_id": ("campaign id",),
    "facebook_post_id": ("facebook post id", "fb post id", "object id"),
}


class BudgetFormatError(ValueError):
    """Raised when a plan file cannot be interpreted safely."""


def normalize_header(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", ascii_value.lower()).strip()


def _header_map(
    headers: Iterable[str], aliases: Optional[Mapping[str, Sequence[str]]] = None
) -> Mapping[str, str]:
    configured: Dict[str, Sequence[str]] = dict(DEFAULT_ALIASES)
    if aliases:
        configured.update(aliases)
    lookup = {
        normalize_header(alias): canonical
        for canonical, values in configured.items()
        for alias in (canonical, *values)
    }
    result: Dict[str, str] = {}
    for header in headers:
        canonical = lookup.get(normalize_header(header))
        if canonical and canonical not in result:
            result[canonical] = header
    return result


def parse_money(value: object) -> Optional[Decimal]:
    if value is None:
        return None
    raw = str(value).strip().replace("\u00a0", "").replace(" ", "")
    if not raw:
        return None
    raw = re.sub(r"[^0-9,.-]", "", raw)
    if raw.count(",") and raw.count("."):
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif raw.count(",") == 1:
        raw = raw.replace(",", ".")
    elif raw.count(",") > 1:
        raw = raw.replace(",", "")
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise BudgetFormatError(f"Invalid money value: {value!r}") from exc


def parse_budget_text(
    text: str,
    *,
    delimiter: Optional[str] = None,
    aliases: Optional[Mapping[str, Sequence[str]]] = None,
) -> List[Dict[str, object]]:
    if delimiter is None:
        try:
            delimiter = csv.Sniffer().sniff(text[:4096], delimiters=",\t;").delimiter
        except csv.Error as exc:
            raise BudgetFormatError("Could not detect CSV/TSV delimiter") from exc
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise BudgetFormatError("Budget file has no header row")
    mapping = _header_map(reader.fieldnames, aliases)
    if "planned_spend" not in mapping and "content_id_or_link" not in mapping:
        raise BudgetFormatError("Budget file needs a planned spend or content identifier column")
    rows: List[Dict[str, object]] = []
    for line_number, raw in enumerate(reader, 2):
        if not any(str(value or "").strip() for value in raw.values()):
            continue
        item: Dict[str, object] = {"source_row": line_number}
        for canonical, original in mapping.items():
            value = (raw.get(original) or "").strip()
            item[canonical] = value or None
        item["planned_spend"] = parse_money(item.get("planned_spend"))
        item["actual_spend_plan"] = parse_money(item.get("actual_spend_plan"))
        rows.append(item)
    return rows


def load_budget(
    path: Path, *, aliases: Optional[Mapping[str, Sequence[str]]] = None
) -> List[Dict[str, object]]:
    if path.suffix.lower() not in {".csv", ".tsv"}:
        raise BudgetFormatError("Only CSV and TSV budget files are supported")
    delimiter = "\t" if path.suffix.lower() == ".tsv" else None
    return parse_budget_text(
        path.read_text(encoding="utf-8-sig"), delimiter=delimiter, aliases=aliases
    )


def _actual_key(row: Mapping[str, object], level: str) -> Optional[str]:
    key = row.get(f"{level}_id") or row.get("id")
    return str(key) if key else None


def _candidate_actuals(
    plan: Mapping[str, object], actuals: Sequence[Mapping[str, object]]
) -> tuple[str, List[Mapping[str, object]]]:
    value = plan.get("content_id_or_link")
    permalink = normalize_permalink(value)
    if permalink:
        matches = [
            row
            for row in actuals
            if normalize_permalink(row.get("instagram_permalink_url")) == permalink
            or normalize_permalink(row.get("permalink")) == permalink
        ]
        if matches:
            return "instagram_permalink", matches
    checks = (
        ("facebook_post_id", "facebook_post_id"),
        ("ad_id", "ad_id"),
        ("campaign_id", "campaign_id"),
        ("adset_id", "adset_id"),
    )
    for plan_field, actual_field in checks:
        identifier = plan.get(plan_field)
        if identifier:
            matches = [row for row in actuals if str(row.get(actual_field, "")) == str(identifier)]
            if matches:
                return plan_field, matches
    if value and not permalink:
        for field in (
            "facebook_post_id",
            "ad_id",
            "campaign_id",
            "adset_id",
            "media_id",
        ):
            exact = [row for row in actuals if str(row.get(field, "")) == str(value)]
            if exact:
                return field, exact
    return "none", []


def reconcile_budget(
    plans: Sequence[Mapping[str, object]],
    actuals: Sequence[Mapping[str, object]],
    *,
    aggregation_level: str = "ad",
) -> Dict[str, object]:
    """Match one chosen Insights level and prevent the same actual from being counted twice."""

    if aggregation_level not in {"account", "campaign", "adset", "ad"}:
        raise ValueError("aggregation_level must be account, campaign, adset, or ad")
    used_actuals: set[str] = set()
    reconciled: List[Dict[str, object]] = []
    for plan in plans:
        method, candidates = _candidate_actuals(plan, actuals)
        result: Dict[str, object] = dict(plan)
        if len(candidates) > 1:
            status = "ambiguous"
            selected = None
        elif not candidates:
            status = "needs_review" if plan.get("content_name") else "unmatched"
            selected = None
        else:
            selected = candidates[0]
            key = _actual_key(selected, aggregation_level)
            if not key or key in used_actuals:
                status = "ambiguous"
                selected = None
            else:
                used_actuals.add(key)
                status = "matched"
        api_spend = parse_money(selected.get("spend")) if selected else None
        planned = plan.get("planned_spend")
        planned_money = planned if isinstance(planned, Decimal) else parse_money(planned)
        result.update(
            {
                "reconciliation_status": status,
                "match_method": method,
                "matched_actual_id": _actual_key(selected, aggregation_level) if selected else None,
                "actual_spend_api": api_spend,
                "variance": api_spend - planned_money
                if api_spend is not None and planned_money is not None
                else None,
            }
        )
        reconciled.append(result)
    planned_total = sum(
        (value for item in reconciled if isinstance((value := item.get("planned_spend")), Decimal)),
        Decimal("0"),
    )
    actual_total = sum(
        (
            value
            for item in reconciled
            if isinstance((value := item.get("actual_spend_api")), Decimal)
        ),
        Decimal("0"),
    )
    return {
        "aggregation_level": aggregation_level,
        "items": reconciled,
        "summary": {
            "planned_spend": planned_total,
            "actual_spend": actual_total,
            "variance": actual_total - planned_total,
            "matched": sum(item["reconciliation_status"] == "matched" for item in reconciled),
            "unmatched": sum(item["reconciliation_status"] == "unmatched" for item in reconciled),
            "ambiguous": sum(item["reconciliation_status"] == "ambiguous" for item in reconciled),
            "needs_review": sum(
                item["reconciliation_status"] == "needs_review" for item in reconciled
            ),
        },
    }


def decimal_to_string(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, list):
        return [decimal_to_string(item) for item in value]
    if isinstance(value, dict):
        return {key: decimal_to_string(item) for key, item in value.items()}
    return value
