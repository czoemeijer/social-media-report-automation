"""One-fetch owned-media workflow with private snapshot reuse."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Dict, Mapping, Optional, Tuple

from .budget import decimal_to_string, load_budget, reconcile_budget
from .owned_analytics import analyze_owned_media
from .owned_html import export_owned_html
from .owned_pdf import render_pdf
from .owned_presentation import default_insights, validate_insights
from .owned_reporting import export_owned_csv, export_owned_json, export_owned_markdown
from .sources.meta.ads import collect_ads
from .sources.meta.auth import MetaConfig
from .sources.meta.client import MetaAPIError, MetaClient
from .sources.meta.discovery import AssetResolutionError, discover_assets, resolve_assets
from .sources.meta.instagram import collect_instagram, resolve_creative_media_references
from .sources.meta.mapper import build_owned_media_report
from .sources.meta.models import utc_now

SNAPSHOT_SCHEMA_VERSION = "1.0"
SENSITIVE_KEYS = {
    "access_token",
    "app_secret",
    "appsecret_proof",
    "client_secret",
    "fb_exchange_token",
    "input_token",
}


def previous_completed_month(today: Optional[date] = None) -> Tuple[str, str]:
    current = today or datetime.now(timezone.utc).date()
    last_day = current.replace(day=1) - timedelta(days=1)
    first_day = last_day.replace(day=1)
    return first_day.isoformat(), last_day.isoformat()


def resolve_report_period(
    date_from: Optional[str], date_to: Optional[str], *, today: Optional[date] = None
) -> Tuple[str, str]:
    if not date_from and not date_to:
        return previous_completed_month(today)
    if not date_from or not date_to:
        raise ValueError("report requires both --from and --to, or neither for the previous month")
    start = date.fromisoformat(date_from)
    end = date.fromisoformat(date_to)
    if end < start:
        raise ValueError("--to must be on or after --from")
    return start.isoformat(), end.isoformat()


def snapshot_cache_key(
    *, provider: str, api_version: str, period: Mapping[str, object], assets: Mapping[str, object]
) -> str:
    identity = {
        "provider": provider,
        "api_version": api_version,
        "period": dict(period),
        "assets": dict(assets),
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:20]


def _contains_sensitive_key(value: object) -> bool:
    if isinstance(value, dict):
        return any(str(key).lower() in SENSITIVE_KEYS for key in value) or any(
            _contains_sensitive_key(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def make_snapshot(
    report: Mapping[str, object],
    *,
    api_version: str,
    assets: Mapping[str, object],
    created_at: Optional[str] = None,
    max_age_hours: int = 36,
) -> Dict[str, object]:
    if _contains_sensitive_key(report):
        raise ValueError("snapshot payload contains a credential-bearing key")
    period = report.get("report_period")
    if not isinstance(period, dict):
        raise ValueError("report snapshot requires an explicit report_period")
    timestamp = created_at or utc_now()
    return {
        "metadata": {
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "created_at": timestamp,
            "provider": "meta",
            "api_version": api_version,
            "period": period,
            "assets": dict(assets),
            "source_freshness": {
                "status": "live_at_creation",
                "max_age_hours": max_age_hours,
            },
            "cache_key": snapshot_cache_key(
                provider="meta", api_version=api_version, period=period, assets=assets
            ),
        },
        "report": dict(report),
    }


def _parse_timestamp(value: object) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def snapshot_status(
    snapshot: Mapping[str, object],
    *,
    date_from: str,
    date_to: str,
    api_version: str,
    now: Optional[datetime] = None,
) -> Mapping[str, object]:
    metadata = snapshot.get("metadata")
    report = snapshot.get("report")
    if not isinstance(metadata, dict) or not isinstance(report, dict):
        return {"valid": False, "fresh": False, "reason": "invalid envelope"}
    expected_period = {"date_from": date_from, "date_to": date_to}
    if metadata.get("schema_version") != SNAPSHOT_SCHEMA_VERSION:
        return {"valid": False, "fresh": False, "reason": "schema version mismatch"}
    if metadata.get("period") != expected_period:
        return {"valid": False, "fresh": False, "reason": "period mismatch"}
    if metadata.get("api_version") != api_version:
        return {"valid": False, "fresh": False, "reason": "API version mismatch"}
    created_at = _parse_timestamp(metadata.get("created_at"))
    freshness = metadata.get("source_freshness")
    max_age = freshness.get("max_age_hours", 36) if isinstance(freshness, dict) else 36
    current = now or datetime.now(timezone.utc)
    fresh = bool(created_at and current - created_at <= timedelta(hours=int(max_age)))
    return {"valid": True, "fresh": fresh, "reason": "fresh" if fresh else "stale"}


def _snapshot_matches_config(snapshot: Mapping[str, object], config: MetaConfig) -> bool:
    metadata = snapshot.get("metadata")
    assets = metadata.get("assets") if isinstance(metadata, dict) else None
    if not isinstance(assets, dict):
        return False

    def normalized(value: object) -> str:
        return str(value or "").removeprefix("act_")

    configured = {
        "page_id": config.page_id,
        "ig_user_id": config.ig_user_id,
        "ad_account_id": config.ad_account_id,
    }
    return all(
        not expected or normalized(assets.get(key)) == normalized(expected)
        for key, expected in configured.items()
    )


def _read_snapshot(path: Path) -> Mapping[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("snapshot root must be an object")
    return value


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(decimal_to_string(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _enrich_ad_actuals(ads: Mapping[str, object]) -> list[Mapping[str, object]]:
    raw_ads = ads.get("ads", [])
    ad_rows = [row for row in raw_ads if isinstance(row, dict)] if isinstance(raw_ads, list) else []
    ads_by_id = {str(row.get("id")): row for row in ad_rows if row.get("id")}
    insights = ads.get("insights", {})
    ad_insights = insights.get("ad", []) if isinstance(insights, dict) else []
    result: list[Mapping[str, object]] = []
    for insight in ad_insights if isinstance(ad_insights, list) else []:
        if not isinstance(insight, dict):
            continue
        enriched = dict(insight)
        ad = ads_by_id.get(str(insight.get("ad_id")), {})
        creative = ad.get("creative") if isinstance(ad, dict) else None
        if isinstance(creative, dict):
            enriched.update(creative)
        result.append(enriched)
    return result


def acquire_owned_report(
    config: MetaConfig,
    *,
    date_from: str,
    date_to: str,
    budget: Optional[Path] = None,
    client: Optional[MetaClient] = None,
) -> Tuple[Dict[str, object], Mapping[str, object]]:
    api = client or MetaClient(config)
    selected = resolve_assets(discover_assets(api), config, client=api)
    ig_id = selected.get("ig_user_id")
    ad_id = selected.get("ad_account_id")
    if not ig_id or not ad_id:
        raise AssetResolutionError("owned report requires an Instagram account and Ad Account")
    instagram = collect_instagram(api, ig_id, date_from=date_from, date_to=date_to)
    ads = collect_ads(api, ad_id, date_from=date_from, date_to=date_to)
    media_value = instagram.get("media", [])
    creative_value = ads.get("creatives", [])
    media_rows = (
        [row for row in media_value if isinstance(row, dict)]
        if isinstance(media_value, list)
        else []
    )
    creative_rows = (
        [row for row in creative_value if isinstance(row, dict)]
        if isinstance(creative_value, list)
        else []
    )
    instagram = dict(instagram)
    instagram["media"] = resolve_creative_media_references(
        api, str(ig_id), media_rows, creative_rows
    )
    report = build_owned_media_report(
        instagram=instagram,
        ads=ads,
        api_version=config.graph_version,
        date_from=date_from,
        date_to=date_to,
    )
    if budget:
        report["budget_reconciliation"] = reconcile_budget(
            load_budget(budget), _enrich_ad_actuals(ads), aggregation_level="ad"
        )
    assets = {
        "page_id": selected.get("page_id"),
        "ig_user_id": ig_id,
        "ad_account_id": ad_id,
    }
    return report, assets


def render_owned_outputs(
    snapshot: Mapping[str, object],
    output_dir: Path,
    *,
    language: str = "en",
    insights_input: Optional[Path] = None,
) -> Mapping[str, object]:
    report = snapshot.get("report")
    if not isinstance(report, dict):
        raise ValueError("snapshot does not contain a report object")
    output_dir.mkdir(parents=True, exist_ok=True)
    analysis = analyze_owned_media(report)
    metadata = snapshot.get("metadata")
    metadata_map = metadata if isinstance(metadata, dict) else {}
    freshness = metadata_map.get("source_freshness")
    freshness_map = freshness if isinstance(freshness, dict) else {}
    analysis["snapshot"] = {
        "captured_at": metadata_map.get("created_at"),
        "status": freshness_map.get("status"),
        "cache_key": metadata_map.get("cache_key"),
    }
    if insights_input:
        raw_narrative = json.loads(insights_input.read_text(encoding="utf-8"))
        if not isinstance(raw_narrative, dict):
            raise ValueError("insights input must contain a JSON object")
        narrative = validate_insights(raw_narrative, analysis)
    else:
        narrative = default_insights(analysis)
    _write_json(output_dir / "analysis.json", analysis)
    _write_json(output_dir / "insights.json", narrative)
    (output_dir / "report.json").write_bytes(export_owned_json(report) + b"\n")
    (output_dir / "report.csv").write_bytes(export_owned_csv(report))
    (output_dir / "report.md").write_bytes(export_owned_markdown(report))
    (output_dir / "report.html").write_bytes(
        export_owned_html(report, analysis, narrative, language=language)
    )
    pdf = render_pdf(output_dir / "report.html", output_dir / "report.pdf")
    return {"analysis": analysis, "insights": narrative, "pdf": pdf}


def run_owned_workflow(
    config: MetaConfig,
    *,
    output_dir: Path,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    language: str = "en",
    refresh: bool = False,
    offline: bool = False,
    budget: Optional[Path] = None,
    snapshot_input: Optional[Path] = None,
    insights_input: Optional[Path] = None,
    max_age_hours: int = 36,
    now: Optional[datetime] = None,
    acquire: Optional[
        Callable[
            [MetaConfig, str, str, Optional[Path]], Tuple[Dict[str, object], Mapping[str, object]]
        ]
    ] = None,
) -> Mapping[str, object]:
    start, end = resolve_report_period(date_from, date_to, today=now.date() if now else None)
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = output_dir / "snapshot.json"
    candidate_path = snapshot_input or snapshot_path
    candidate = _read_snapshot(candidate_path) if candidate_path.exists() else None
    status = (
        snapshot_status(
            candidate,
            date_from=start,
            date_to=end,
            api_version=config.graph_version,
            now=now,
        )
        if candidate
        else {"valid": False, "fresh": False, "reason": "missing"}
    )
    if candidate and status["valid"] and not _snapshot_matches_config(candidate, config):
        status = {"valid": False, "fresh": False, "reason": "asset identity mismatch"}
    mode = "snapshot"
    may_use_stale = offline or not config.access_token
    snapshot = (
        candidate
        if candidate and status["valid"] and (status["fresh"] or may_use_stale) and not refresh
        else None
    )
    if snapshot is not None and not status["fresh"]:
        mode = "snapshot_stale_offline"
    if snapshot is None:
        if not config.access_token:
            raise ValueError("AUTH_REQUIRED_FOR_FRESH_FETCH")
        try:
            if acquire:
                report, assets = acquire(config, start, end, budget)
            else:
                report, assets = acquire_owned_report(
                    config, date_from=start, date_to=end, budget=budget
                )
            snapshot = make_snapshot(
                report,
                api_version=config.graph_version,
                assets=assets,
                max_age_hours=max_age_hours,
            )
            _write_json(snapshot_path, snapshot)
            mode = "live"
            status = snapshot_status(
                snapshot,
                date_from=start,
                date_to=end,
                api_version=config.graph_version,
                now=now,
            )
        except MetaAPIError as exc:
            if (
                not candidate
                or not status["valid"]
                or not (exc.status == 429 or exc.code in {4, 17, 32, 613})
            ):
                raise
            snapshot = candidate
            mode = "snapshot_rate_limit_fallback"
    if candidate_path != snapshot_path:
        _write_json(snapshot_path, snapshot)
    rendered = render_owned_outputs(
        snapshot,
        output_dir,
        language=language,
        insights_input=insights_input,
    )
    pdf = rendered["pdf"]
    files = [
        "snapshot.json",
        "analysis.json",
        "insights.json",
        "report.json",
        "report.csv",
        "report.md",
        "report.html",
    ]
    if isinstance(pdf, dict) and pdf.get("status") == "PASS":
        files.append("report.pdf")
    return {
        "period": {"date_from": start, "date_to": end},
        "snapshot_mode": mode,
        "snapshot_status": status,
        "output_dir": str(output_dir),
        "files": files,
        "pdf": pdf,
        "analysis": rendered["analysis"],
    }
