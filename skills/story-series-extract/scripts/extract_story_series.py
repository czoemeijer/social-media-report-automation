#!/usr/bin/env python3
"""CLI wrapper for the canonical Story-series implementation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from social_report.stories import format_czech_float, summarize_story_series  # noqa: E402

__all__ = ["extract_story_series_summary", "format_czech_float", "main"]


def extract_story_series_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    return summarize_story_series(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit an Instagram/Facebook Story series.")
    parser.add_argument("input_file", nargs="?", help="JSON file; reads stdin when omitted.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown.")
    args = parser.parse_args()
    if args.input_file:
        data = json.loads(Path(args.input_file).read_text(encoding="utf-8"))
    else:
        data = json.load(sys.stdin)
    result = extract_story_series_summary(data)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result["markdown"])


if __name__ == "__main__":
    main()
