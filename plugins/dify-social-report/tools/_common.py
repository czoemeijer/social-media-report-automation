from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def add_core_to_path() -> None:
    plugin_root = Path(__file__).resolve().parents[1]
    repository_source = Path(__file__).resolve().parents[3] / "src"
    for candidate in (plugin_root, repository_source):
        if (candidate / "social_report").is_dir() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))


def object_from_json(raw: Any, parameter_name: str) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{parameter_name} must be a JSON object")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{parameter_name} is not valid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{parameter_name} must decode to a JSON object")
    return value


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
