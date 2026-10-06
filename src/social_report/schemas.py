"""Canonical schema definitions used by runtime validation and JSON artifacts."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

SCOPES = ["organic", "paid", "mixed_or_unknown", "unknown"]
PRECISIONS = ["exact", "approximate", "missing", "unreadable"]
REVIEW_STATUSES = ["verified", "verified_with_warning", "needs_review", "rejected"]
RELATIONSHIPS = [
    "exact_duplicate",
    "near_duplicate",
    "same_asset_scroll_slice",
    "same_asset_other_tab",
    "same_story_later_snapshot",
    "different_story_same_series",
    "repost",
    "different_asset",
    "unknown",
]

MEASUREMENT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "required": ["value", "precision"],
    "additionalProperties": False,
    "properties": {
        "value": {"type": ["number", "null"], "minimum": 0},
        "precision": {"type": "string", "enum": PRECISIONS},
        "confidence": {"type": ["number", "null"], "minimum": 0, "maximum": 1},
        "source_file": {"type": ["string", "null"]},
        "evidence_text": {"type": ["string", "null"]},
        "extraction_method": {"type": "string", "enum": ["vision", "manual", "ocr"]},
    },
}

INPUT_MANIFEST_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://social-report.local/schemas/input_manifest.schema.json",
    "title": "Campaign input manifest",
    "type": "object",
    "required": ["files", "manifest"],
    "additionalProperties": False,
    "properties": {
        "files": {"type": "array", "items": {"type": "string"}},
        "manifest": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["source_id", "filename", "mime_type", "sha256", "size"],
                "properties": {
                    "source_id": {"type": "string"},
                    "relative_path": {"type": ["string", "null"]},
                    "filename": {"type": "string"},
                    "transport_name": {"type": "string"},
                    "mime_type": {"type": "string"},
                    "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
                    "size": {"type": "integer", "minimum": 1},
                    "perceptual_hash": {"type": ["string", "null"]},
                },
            },
        },
    },
}

CAMPAIGN_RECONSTRUCTION_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://social-report.local/schemas/campaign_reconstruction.schema.json",
    "title": "Global campaign reconstruction",
    "type": "object",
    "required": ["campaign", "client", "assets"],
    "properties": {
        "campaign": {"$ref": "#/$defs/inference"},
        "client": {"$ref": "#/$defs/inference"},
        "assets": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["asset_group_id", "source_files", "relationships"],
                "properties": {
                    "asset_group_id": {"type": "string"},
                    "creator": {"type": ["string", "null"]},
                    "platform": {
                        "type": "string",
                        "enum": ["instagram", "facebook", "meta", "unknown"],
                    },
                    "content_format": {
                        "type": "string",
                        "enum": ["post", "reel", "story", "ad", "unknown"],
                    },
                    "source_files": {"type": "array", "items": {"type": "string"}, "minItems": 1},
                    "relationships": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["file", "role"],
                            "properties": {
                                "file": {"type": "string"},
                                "role": {"type": "string"},
                                "relationship": {"type": "string", "enum": RELATIONSHIPS},
                            },
                        },
                    },
                    "warnings": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
    "$defs": {
        "inference": {
            "type": "object",
            "required": ["name", "confidence", "evidence"],
            "properties": {
                "name": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "evidence": {"type": "array", "items": {"type": "string"}},
            },
        }
    },
}

EXTRACTED_ASSET_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://social-report.local/schemas/extracted_asset.schema.json",
    "title": "Vision-extracted social asset",
    "type": "object",
    "required": [
        "asset_group_id",
        "platform",
        "content_format",
        "scope",
        "metrics",
        "review_status",
    ],
    "properties": {
        "asset_group_id": {"type": "string"},
        "creator": {"type": ["string", "null"]},
        "platform": {"type": "string", "enum": ["instagram", "facebook", "meta", "unknown"]},
        "content_format": {"type": "string", "enum": ["post", "reel", "story", "ad", "unknown"]},
        "scope": {"type": "string", "enum": SCOPES},
        "metrics": {
            "type": "object",
            "additionalProperties": deepcopy(MEASUREMENT_SCHEMA),
        },
        "has_ad_disclaimer": {"type": "boolean"},
        "source_files": {"type": "array", "items": {"type": "string"}},
        "review_status": {"type": "string", "enum": REVIEW_STATUSES},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
}

AUDIT_RESULT_SCHEMA: Dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://social-report.local/schemas/audit_result.schema.json",
    "title": "Deterministic campaign audit",
    "type": "object",
    "required": ["items", "campaign_summary", "review_status"],
    "properties": {
        "items": {"type": "array", "items": {"type": "object"}},
        "campaign_summary": {"type": "object"},
        "review_status": {"type": "string", "enum": REVIEW_STATUSES},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
}

SCHEMAS = {
    "input_manifest.schema.json": INPUT_MANIFEST_SCHEMA,
    "campaign_reconstruction.schema.json": CAMPAIGN_RECONSTRUCTION_SCHEMA,
    "extracted_asset.schema.json": EXTRACTED_ASSET_SCHEMA,
    "audit_result.schema.json": AUDIT_RESULT_SCHEMA,
}
