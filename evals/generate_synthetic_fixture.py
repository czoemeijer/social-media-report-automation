#!/usr/bin/env python3
"""Generate privacy-safe screenshot-like PNGs for the synthetic evaluation case."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "generated" / "synthetic_campaign_001"

SCREENS = {
    "alice/reel-overview.png": [
        "Instagram Reel insights",
        "@alice_demo",
        "Autumn Pantry",
        "Views 12,500",
        "Reach 8,200",
    ],
    "alice/reel-interactions.png": [
        "Reel interactions",
        "Likes 640",
        "Comments 22",
        "Shares --",
        "Saves 91",
    ],
    "alice/stories/story-1-top.png": ["Story insights", "@alice_demo", "Views 510", "Reach 470"],
    "alice/stories/story-1-bottom.png": [
        "Story insights",
        "Replies 0",
        "Profile visits 12",
        "Scroll continuation",
    ],
    "alice/stories/story-2-final.png": [
        "Story insights",
        "Second frame",
        "Views 430",
        "Reach 390",
        "24h final",
    ],
    "paid/meta-results.png": [
        "Meta Ads results",
        "Example Foods",
        "Views 1.2k",
        "Reach 1,100",
        "Paid",
    ],
}


def main() -> None:
    for relative_path, lines in SCREENS.items():
        target = OUTPUT / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (720, 1280), "#f6f6f4")
        draw = ImageDraw.Draw(image)
        draw.rectangle((40, 40, 680, 1240), outline="#20252a", width=4)
        for index, line in enumerate(lines):
            draw.text((80, 110 + index * 120), line, fill="#20252a")
        image.save(target)
    print(OUTPUT)


if __name__ == "__main__":
    main()
