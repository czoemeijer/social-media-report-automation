#!/usr/bin/env python3
"""CLI wrapper for the canonical :mod:`social_report.metrics` core."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from social_report.metrics import aggregate_campaign, calculate_single_item  # noqa: E402

__all__ = ["aggregate_campaign", "calculate_single_item", "main"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate and audit social-media metrics.")
    parser.add_argument("input_file", nargs="?", help="JSON file; reads stdin when omitted.")
    parser.add_argument("--stdin", action="store_true", help="Read JSON from standard input.")
    args = parser.parse_args()

    if args.stdin or not args.input_file:
        if sys.stdin.isatty():
            parser.print_help()
            raise SystemExit(1)
        raw_input = sys.stdin.read()
    else:
        raw_input = Path(args.input_file).read_text(encoding="utf-8")

    try:
        data = json.loads(raw_input)
    except (TypeError, json.JSONDecodeError) as exc:
        print(f"Error parsing JSON: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    output: Dict[str, Any]
    if isinstance(data, list):
        items: List[Dict[str, Any]] = data
        output = {
            "items": [calculate_single_item(item) for item in items],
            "campaign_summary": aggregate_campaign(items),
        }
    elif isinstance(data, dict) and "items" in data:
        items = data["items"]
        output = {
            "items": [calculate_single_item(item) for item in items],
            "campaign_summary": aggregate_campaign(items),
        }
    elif isinstance(data, dict):
        output = calculate_single_item(data)
    else:
        print(
            "Invalid input JSON structure. Expected an object or list of objects.", file=sys.stderr
        )
        raise SystemExit(1)
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
