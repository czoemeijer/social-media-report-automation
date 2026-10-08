"""Deterministic Meta Paid-to-Organic identity matching."""

from __future__ import annotations

import urllib.parse
from typing import Any, Dict, Iterable, List, Mapping, Optional


def normalize_permalink(value: object) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return None
    parsed = urllib.parse.urlsplit(value.strip())
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    if not host or not path:
        return None
    return urllib.parse.urlunsplit(("https", host, path, "", ""))


def _matches(
    creative: Mapping[str, Any], organic_media: Iterable[Mapping[str, Any]]
) -> tuple[str, List[Mapping[str, Any]]]:
    source_id = creative.get("source_instagram_media_id")
    if source_id:
        exact = [item for item in organic_media if str(item.get("id", "")) == str(source_id)]
        if exact:
            return "source_instagram_media_id", exact
    creative_permalink = normalize_permalink(creative.get("instagram_permalink_url"))
    if creative_permalink:
        exact = [
            item
            for item in organic_media
            if normalize_permalink(item.get("permalink")) == creative_permalink
        ]
        if exact:
            return "instagram_permalink", exact
    effective_id = creative.get("effective_instagram_media_id")
    if effective_id:
        exact = [item for item in organic_media if str(item.get("id", "")) == str(effective_id)]
        if exact:
            return "effective_instagram_media_id", exact
    return "none", []


def match_paid_to_organic(
    creatives: Iterable[Mapping[str, Any]], organic_media: Iterable[Mapping[str, Any]]
) -> List[Dict[str, object]]:
    media = list(organic_media)
    results: List[Dict[str, object]] = []
    for creative in creatives:
        method, matches = _matches(creative, media)
        status = "matched" if len(matches) == 1 else "ambiguous" if matches else "unmatched"
        results.append(
            {
                "creative_id": creative.get("id"),
                "status": status,
                "match_method": method,
                "organic_media_id": matches[0].get("id") if len(matches) == 1 else None,
                "candidate_media_ids": [item.get("id") for item in matches],
                "confidence": "exact" if matches else None,
            }
        )
    return results
