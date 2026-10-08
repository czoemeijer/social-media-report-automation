"""Read-only Meta Marketing API collection and normalization."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from .client import MetaAPIError, MetaClient
from .instagram import validate_date_range
from .models import action_mapping, decimal_or_none, number_or_none, provenance, utc_now

INSIGHT_FIELDS = (
    "impressions",
    "reach",
    "clicks",
    "spend",
    "ctr",
    "cpc",
    "cpm",
    "frequency",
    "actions",
    "cost_per_action_type",
    "date_start",
    "date_stop",
)

IDENTITY_FIELDS = {
    "account": ("account_id", "account_name"),
    "campaign": ("account_id", "campaign_id", "campaign_name"),
    "adset": ("account_id", "campaign_id", "adset_id", "adset_name"),
    "ad": ("account_id", "campaign_id", "adset_id", "ad_id", "ad_name"),
}

CAMPAIGN_FIELDS = "id,name,status,effective_status,objective"
ADSET_FIELDS = "id,name,campaign_id,status,effective_status"
CREATIVE_FIELDS = (
    "id,name,effective_object_story_id,instagram_user_id,"
    "effective_instagram_media_id,instagram_permalink_url,"
    "source_instagram_media_id,source_facebook_post_id"
)
AD_FIELDS = f"id,name,campaign_id,adset_id,status,effective_status,creative{{{CREATIVE_FIELDS}}}"


def normalize_ad_account_id(ad_account_id: str) -> str:
    return ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"


def get_ad_account(client: MetaClient, ad_account_id: str) -> Mapping[str, Any]:
    return client.get(
        normalize_ad_account_id(ad_account_id),
        {"fields": "id,name,account_status,currency,timezone_name"},
    )


def _list_edge(
    client: MetaClient, ad_account_id: str, edge: str, fields: str
) -> List[Mapping[str, Any]]:
    account = normalize_ad_account_id(ad_account_id)
    return list(client.paginate(f"{account}/{edge}", {"fields": fields, "limit": 100}))


def list_campaigns(client: MetaClient, ad_account_id: str) -> List[Mapping[str, Any]]:
    return _list_edge(client, ad_account_id, "campaigns", CAMPAIGN_FIELDS)


def list_adsets(client: MetaClient, ad_account_id: str) -> List[Mapping[str, Any]]:
    return _list_edge(
        client,
        ad_account_id,
        "adsets",
        ADSET_FIELDS,
    )


def list_ads(client: MetaClient, ad_account_id: str) -> List[Mapping[str, Any]]:
    return _list_edge(client, ad_account_id, "ads", AD_FIELDS)


def _insight_ids(rows: object, field: str) -> List[str]:
    if not isinstance(rows, list):
        return []
    return sorted(
        {str(row[field]) for row in rows if isinstance(row, dict) and row.get(field) is not None}
    )


def _adsets_from_insights(rows: object) -> List[Mapping[str, Any]]:
    if not isinstance(rows, list):
        return []
    result: List[Mapping[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("adset_id") is None:
            continue
        result.append(
            {
                key: value
                for key, value in {
                    "id": str(row["adset_id"]),
                    "name": row.get("adset_name"),
                    "campaign_id": row.get("campaign_id"),
                }.items()
                if value is not None
            }
        )
    return result


def _read_objects_by_ids(
    client: MetaClient, object_ids: List[str], fields: str, *, batch_size: int = 50
) -> List[Mapping[str, Any]]:
    """Read only objects proven active in the report period, using Graph multi-ID GETs."""

    result: List[Mapping[str, Any]] = []
    for offset in range(0, len(object_ids), batch_size):
        batch = object_ids[offset : offset + batch_size]
        try:
            payload = client.get("", {"ids": ",".join(batch), "fields": fields})
            result.extend(
                payload[item_id] for item_id in batch if isinstance(payload.get(item_id), dict)
            )
        except MetaAPIError as exc:
            if exc.code != 100:
                raise
            for item_id in batch:
                payload = client.get(item_id, {"fields": fields})
                if isinstance(payload, dict):
                    result.append(payload)
    return result


def _normalize_insight(
    row: Mapping[str, Any], *, level: str, client: MetaClient
) -> Dict[str, object]:
    result: Dict[str, object] = dict(row)
    for field in ("impressions", "reach", "clicks"):
        result[field] = number_or_none(row.get(field))
    for field in ("spend", "ctr", "cpc", "cpm", "frequency"):
        value = decimal_or_none(row.get(field))
        result[field] = str(value) if value is not None else None
    result["actions_normalized"] = dict(action_mapping(row.get("actions")))
    result["cost_per_action_normalized"] = dict(action_mapping(row.get("cost_per_action_type")))
    object_id = row.get(f"{level}_id") or row.get("account_id")
    retrieved_at = utc_now()
    result["provenance"] = [
        provenance(
            platform="meta",
            object_type=level,
            object_id=str(object_id) if object_id else None,
            metric_name=field,
            api_version=client.config.graph_version,
            scope="paid",
            retrieved_at=retrieved_at,
        )
        for field in INSIGHT_FIELDS
        if row.get(field) is not None
    ]
    result["scope"] = "paid"
    return result


def get_insights(
    client: MetaClient,
    ad_account_id: str,
    *,
    level: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    breakdowns: Optional[str] = None,
) -> List[Dict[str, object]]:
    if level not in {"account", "campaign", "adset", "ad"}:
        raise ValueError("Insights level must be account, campaign, adset, or ad")
    validate_date_range(date_from, date_to)
    params: Dict[str, object] = {
        "fields": ",".join((*IDENTITY_FIELDS[level], *INSIGHT_FIELDS)),
        "level": level,
        "limit": 100,
    }
    if date_from or date_to:
        time_range: Dict[str, str] = {}
        if date_from:
            time_range["since"] = date_from
        if date_to:
            time_range["until"] = date_to
        params["time_range"] = time_range
    if breakdowns:
        params["breakdowns"] = breakdowns
    path = f"{normalize_ad_account_id(ad_account_id)}/insights"
    return [
        _normalize_insight(row, level=level, client=client) for row in client.paginate(path, params)
    ]


def collect_ads(
    client: MetaClient,
    ad_account_id: str,
    *,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    breakdowns: Optional[str] = None,
) -> Dict[str, object]:
    insights = {
        level: get_insights(
            client,
            ad_account_id,
            level=level,
            date_from=date_from,
            date_to=date_to,
            breakdowns=breakdowns,
        )
        for level in ("account", "campaign", "adset", "ad")
    }
    campaign_ids = _insight_ids(insights["campaign"], "campaign_id")
    adset_ids = _insight_ids(insights["adset"], "adset_id")
    ad_ids = _insight_ids(insights["ad"], "ad_id")
    campaigns = _read_objects_by_ids(client, campaign_ids, CAMPAIGN_FIELDS)
    ads = _read_objects_by_ids(client, ad_ids, AD_FIELDS)
    adsets = _adsets_from_insights(insights["adset"])
    creatives = [item["creative"] for item in ads if isinstance(item.get("creative"), dict)]
    return {
        "account": get_ad_account(client, ad_account_id),
        "campaigns": campaigns,
        "adsets": adsets,
        "ads": ads,
        "creatives": creatives,
        "insights": insights,
        "collection": {
            "scope": "report_period",
            "campaigns_in_period": len(campaign_ids),
            "adsets_in_period": len(adset_ids),
            "ads_in_period": len(ad_ids),
            "creatives_in_period": len(creatives),
        },
        "api_version": client.config.graph_version,
    }
