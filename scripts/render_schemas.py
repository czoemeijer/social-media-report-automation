#!/usr/bin/env python3
"""Render committed JSON Schema artifacts from the canonical Python definitions."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from social_report.schemas import SCHEMAS  # noqa: E402


def main() -> None:
    output_dir = ROOT / "schemas"
    output_dir.mkdir(exist_ok=True)
    for filename, schema in SCHEMAS.items():
        (output_dir / filename).write_text(
            json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
