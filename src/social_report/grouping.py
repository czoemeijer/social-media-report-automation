"""Shared vocabulary and validation helpers for model-produced asset grouping."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from .schemas import RELATIONSHIPS


def normalize_relationship(raw: Mapping[str, Any]) -> Dict[str, Any]:
    relationship = raw.get("relationship", "unknown")
    if relationship not in RELATIONSHIPS:
        relationship = "unknown"
    return {
        "file": str(raw.get("file", "")),
        "role": str(raw.get("role", "unknown")),
        "relationship": relationship,
        "confidence": raw.get("confidence"),
        "evidence": list(raw.get("evidence") or []),
    }


def evidence_priority(signal: str) -> int:
    """Express prompt policy: visual platform evidence outranks path hints."""

    priorities = {
        "visual_platform_ui": 100,
        "account_handle": 90,
        "thumbnail": 85,
        "publication_date": 80,
        "caption": 70,
        "campaign_branding": 60,
        "relative_path": 30,
        "filename": 20,
    }
    return priorities.get(signal, 0)
