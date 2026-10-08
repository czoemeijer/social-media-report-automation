#!/usr/bin/env python3
"""Thin Agent Skill wrapper over the canonical owned-media CLI."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from social_report.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["meta", *sys.argv[1:]]))
