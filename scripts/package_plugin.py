#!/usr/bin/env python3
"""Build the Dify plugin with the canonical core staged into its package."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_SOURCE = ROOT / "plugins" / "dify-social-report"
CORE_SOURCE = ROOT / "src" / "social_report"


def find_dify_cli() -> str:
    for candidate in ("dify", "dify-plugin", "/tmp/dify-plugin"):
        resolved = shutil.which(candidate) if not candidate.startswith("/") else candidate
        if resolved and Path(resolved).exists():
            return str(resolved)
    return "dify"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "dist" / "dify-social-report-0.1.0.difypkg",
    )
    parser.add_argument(
        "--cli",
        default=None,
        help="Path to the official Dify CLI binary.",
    )
    args = parser.parse_args()
    cli_bin = args.cli or find_dify_cli()
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="dify-social-report-") as temp_dir:
        staged = Path(temp_dir) / "dify-social-report"
        shutil.copytree(PLUGIN_SOURCE, staged)
        shutil.copytree(CORE_SOURCE, staged / "social_report")
        subprocess.run(
            [
                cli_bin,
                "plugin",
                "package",
                str(staged),
                "--output_path",
                str(args.output),
            ],
            check=True,
        )
    print(args.output)


if __name__ == "__main__":
    main()
