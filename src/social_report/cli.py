"""Operator CLI for the canonical core and read-only Meta source adapter."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

from .budget import decimal_to_string, load_budget, reconcile_budget
from .owned_reporting import export_owned_csv, export_owned_json, export_owned_markdown
from .sources.meta.ads import collect_ads
from .sources.meta.auth import MetaConfig, load_env_file
from .sources.meta.client import MetaAPIError, MetaClient
from .sources.meta.discovery import AssetResolutionError, discover_assets, resolve_assets
from .sources.meta.instagram import collect_instagram, resolve_creative_media_references
from .sources.meta.mapper import build_owned_media_report
from .sources.meta.matching import match_paid_to_organic
from .sources.meta.tokens import debug_token, exchange_user_token


def _config() -> MetaConfig:
    load_env_file(Path(".env.local"))
    return MetaConfig.from_env()


def _json(payload: object) -> str:
    return json.dumps(decimal_to_string(payload), ensure_ascii=False, indent=2, sort_keys=True)


def _emit(payload: object, *, as_json: bool) -> None:
    if as_json:
        print(_json(payload))
        return
    if isinstance(payload, dict) and isinstance(payload.get("checks"), list):
        for check in payload["checks"]:
            if isinstance(check, dict):
                status = str(check.get("status", "UNKNOWN"))
                name = check.get("name", "check")
                detail = check.get("detail", "")
                print(f"{status:11} {name}: {detail}")
        return
    print(_json(payload))


def _override_selectors(config: MetaConfig, args: argparse.Namespace) -> MetaConfig:
    values = dict(config.__dict__)
    for attribute, argument in (
        ("page_id", "page_id"),
        ("ig_user_id", "ig_user_id"),
        ("ad_account_id", "ad_account_id"),
    ):
        value = getattr(args, argument, None)
        if value:
            values[attribute] = value
    return MetaConfig(**values)


def _resolved(
    client: MetaClient,
    config: MetaConfig,
    *,
    resolve_page: bool = True,
    resolve_ad_account: bool = True,
) -> Mapping[str, Optional[str]]:
    return resolve_assets(
        discover_assets(client),
        config,
        resolve_page=resolve_page,
        resolve_ad_account=resolve_ad_account,
    )


def doctor(client: MetaClient, config: MetaConfig) -> Mapping[str, object]:
    checks: List[Dict[str, str]] = []

    def add(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    add("configuration", "PASS", f"{config.graph_version}; {config.auth_mode}")
    try:
        identity = client.get("me", {"fields": "id"})
        add(
            "graph_api",
            "PASS",
            "reachable and token accepted" if identity.get("id") else "reachable",
        )
    except MetaAPIError as exc:
        add("graph_api", "FAIL", f"request rejected (status {exc.status}, code {exc.code})")
        return {"overall": "FAIL", "checks": checks, "configuration": config.safe_summary()}
    if config.app_id and config.app_secret:
        try:
            token = debug_token(config, transport=client.transport)
            validity = "valid" if token.get("is_valid") else "invalid"
            add("token_debug", "PASS" if token.get("is_valid") else "FAIL", validity)
        except MetaAPIError as exc:
            add("token_debug", "WARNING", f"unavailable (code {exc.code})")
    else:
        add("token_debug", "UNAVAILABLE", "configure app id/secret for expiry and scope debug")
    try:
        assets = discover_assets(client)
        add("asset_discovery", "PASS", "authorized assets listed")
        selected = resolve_assets(assets, config)
    except AssetResolutionError as exc:
        add("asset_resolution", "WARNING", str(exc))
        selected = {"page_id": None, "ig_user_id": None, "ad_account_id": None}
    instagram_result: Optional[Mapping[str, object]] = None
    ig_id = selected.get("ig_user_id")
    if ig_id:
        try:
            instagram_result = collect_instagram(client, ig_id, limit=5, max_items=5)
            media = instagram_result.get("media", [])
            media_rows_for_count = media if isinstance(media, list) else []
            add("instagram_profile", "PASS", "profile readable")
            add(
                "instagram_media",
                "PASS",
                f"{len(media) if isinstance(media, list) else 0} recent item(s) read",
            )
            insight_count = sum(
                bool(isinstance(item, dict) and item.get("insights"))
                for item in media_rows_for_count
            )
            add(
                "organic_insights",
                "PASS" if insight_count else "UNAVAILABLE",
                f"{insight_count} item(s) checked",
            )
        except MetaAPIError as exc:
            add("instagram", "FAIL", f"read failed (code {exc.code})")
    else:
        add("instagram", "UNAVAILABLE", "no unambiguous linked account selected")
    ad_id = selected.get("ad_account_id")
    if ad_id:
        try:
            ads = collect_ads(client, ad_id)
            add("ads_insights", "PASS", "account/campaign/adset/ad levels readable")
            if ig_id and instagram_result is not None:
                media_value = instagram_result.get("media", [])
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
                matches = match_paid_to_organic(creative_rows, media_rows)
                matched = sum(row["status"] == "matched" for row in matches)
                add(
                    "paid_organic_matching",
                    "PASS" if matched else "UNAVAILABLE",
                    f"{matched} exact match(es)",
                )
        except MetaAPIError as exc:
            add("ads_insights", "FAIL", f"read failed (code {exc.code})")
    else:
        add("ads_insights", "UNAVAILABLE", "no unambiguous Ad Account selected")
    overall = (
        "FAIL"
        if any(row["status"] == "FAIL" for row in checks)
        else "WARNING"
        if any(row["status"] == "WARNING" for row in checks)
        else "PASS"
    )
    return {"overall": overall, "checks": checks, "configuration": config.safe_summary()}


def _enrich_ad_actuals(ads: Mapping[str, object]) -> List[Mapping[str, object]]:
    raw_ads = ads.get("ads", [])
    ad_rows = [row for row in raw_ads if isinstance(row, dict)] if isinstance(raw_ads, list) else []
    ads_by_id = {str(row.get("id")): row for row in ad_rows if row.get("id")}
    raw_insights = ads.get("insights", {})
    ad_insights = raw_insights.get("ad", []) if isinstance(raw_insights, dict) else []
    result: List[Mapping[str, object]] = []
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


def _write_report(payload: Mapping[str, object], output: Optional[str], output_format: str) -> None:
    exporters = {
        "json": export_owned_json,
        "csv": export_owned_csv,
        "markdown": export_owned_markdown,
    }
    data = exporters[output_format](payload)
    if output:
        Path(output).write_bytes(data)
    else:
        sys.stdout.buffer.write(data + (b"\n" if not data.endswith(b"\n") else b""))


def _add_selectors(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--page-id")
    parser.add_argument("--ig-user-id")
    parser.add_argument("--ad-account-id")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="social-report")
    root = parser.add_subparsers(dest="root", required=True)
    meta = root.add_parser("meta", help="Read authorized Meta owned-media data")
    commands = meta.add_subparsers(dest="command", required=True)
    doctor_parser = commands.add_parser("doctor")
    doctor_parser.add_argument("--json", action="store_true")
    discover_parser = commands.add_parser("discover")
    discover_parser.add_argument("--json", action="store_true")
    for name in ("pull", "pull-instagram", "pull-ads"):
        command = commands.add_parser(name)
        command.add_argument("--from", dest="date_from")
        command.add_argument("--to", dest="date_to")
        command.add_argument("--output")
        command.add_argument("--format", choices=("json", "csv", "markdown"), default="json")
        command.add_argument("--budget")
        command.add_argument(
            "--breakdowns", help="Optional comma-separated Marketing API breakdowns"
        )
        _add_selectors(command)
    exchange = commands.add_parser("exchange-user-token")
    exchange.add_argument("--save-to", required=True)
    return parser


def run_meta(args: argparse.Namespace) -> int:
    config = _override_selectors(_config(), args)
    client = MetaClient(config)
    if args.command == "doctor":
        result = doctor(client, config)
        _emit(result, as_json=args.json)
        return 1 if result.get("overall") == "FAIL" else 0
    if args.command == "discover":
        _emit(discover_assets(client), as_json=args.json)
        return 0
    if args.command == "exchange-user-token":
        _emit(exchange_user_token(config, save_to=Path(args.save_to)), as_json=True)
        return 0
    selected = _resolved(
        client,
        config,
        resolve_page=args.command in {"pull", "pull-instagram"},
        resolve_ad_account=args.command in {"pull", "pull-ads"},
    )
    instagram: Mapping[str, object] = {"profile": None, "media": []}
    ads: Mapping[str, object] = {"account": None, "insights": {}, "creatives": []}
    if args.command in {"pull", "pull-instagram"}:
        ig_id = selected.get("ig_user_id")
        if not ig_id:
            raise AssetResolutionError("No Instagram Professional account is selected")
        instagram = collect_instagram(client, ig_id, date_from=args.date_from, date_to=args.date_to)
    if args.command in {"pull", "pull-ads"}:
        ad_id = selected.get("ad_account_id")
        if not ad_id:
            raise AssetResolutionError("No Ad Account is selected")
        ads = collect_ads(
            client,
            ad_id,
            date_from=args.date_from,
            date_to=args.date_to,
            breakdowns=args.breakdowns,
        )
    if args.command == "pull":
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
            client,
            selected["ig_user_id"] or "",
            media_rows,
            creative_rows,
        )
    report = build_owned_media_report(
        instagram=instagram, ads=ads, api_version=config.graph_version
    )
    if args.budget:
        report["budget_reconciliation"] = reconcile_budget(
            load_budget(Path(args.budget)), _enrich_ad_actuals(ads), aggregation_level="ad"
        )
    _write_report(report, args.output, args.format)
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.root == "meta":
            return run_meta(args)
    except (MetaAPIError, AssetResolutionError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
