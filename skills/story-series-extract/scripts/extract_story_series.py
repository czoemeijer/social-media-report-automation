#!/usr/bin/env python3
"""
Story Series Extract Helper Script
Extracts and structures Instagram/Facebook Story sequence metrics into standardized campaign report blocks.
"""

import sys
import json
import argparse
from typing import Dict, Any, List, Optional


def format_czech_float(val: float, decimals: int = 1) -> str:
    """Format float with Czech decimal comma."""
    formatted = f"{val:.{decimals}f}"
    return formatted.replace(".", ",")


def extract_story_series_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts standardized story series summary from raw or structured story sequence input.
    """
    stories: List[Dict[str, Any]] = data.get("stories", [])
    if not stories:
        raise ValueError("Vstupní data neobsahují žádné storky v poli 'stories'.")

    # Views calculation & breakdown
    views_list = [int(s.get("views", 0)) for s in stories]
    total_views = sum(views_list)
    views_breakdown = " + ".join(str(v) for v in views_list)
    views_str = f"{total_views} ({views_breakdown})" if len(views_list) > 1 else str(total_views)

    # Initial Reach
    first_story = stories[0]
    initial_reach = int(first_story.get("reach") or first_story.get("viewers") or 0)
    reach_str = f"{initial_reach} - maximální dosah na začátku série"

    # Profile visits
    profile_visits_list = [int(s.get("profile_visits", 0) or 0) for s in stories]
    total_profile_visits = sum(profile_visits_list)

    # Interactions calculation & breakdown
    interactions_list = [int(s.get("interactions", 0)) for s in stories]
    total_interactions = sum(interactions_list)
    interactions_breakdown = " + ".join(str(i) for i in interactions_list)
    interactions_str = (
        f"{total_interactions} ({interactions_breakdown})"
        if len(interactions_list) > 1
        else str(total_interactions)
    )

    # Drop-off rate (Míra opuštění)
    # Calculated as percentage drop from first story reach/viewers to last story reach/viewers
    last_story = stories[-1]
    last_reach = int(last_story.get("reach") or last_story.get("viewers") or 0)

    if initial_reach > 0 and len(stories) > 1:
        drop_off = ((initial_reach - last_reach) / initial_reach) * 100.0
        drop_off_val = max(0.0, drop_off)
        drop_off_str = f"{format_czech_float(drop_off_val, 1)} %"
    else:
        # Check if direct drop_off_rate was provided in input
        provided_drop_off = data.get("drop_off_rate") or data.get("mira_opusteni")
        if provided_drop_off is not None:
            drop_off_str = str(provided_drop_off).strip()
            if not drop_off_str.endswith("%"):
                drop_off_str += " %"
        else:
            drop_off_str = "0,0 %"

    # Poll / Quiz Result
    poll_result = None
    for s in stories:
        if s.get("poll_result"):
            poll_result = s.get("poll_result")
            break
        if s.get("quiz_result"):
            poll_result = s.get("quiz_result")
            break

    if not poll_result:
        poll_result = data.get("poll_result") or data.get("quiz_result") or "Nerelevantní (série neobsahuje anketu ani kvíz)"

    # Build Markdown block
    markdown_lines = [
        "Souhrnný výkon série",
        f"Zobrazení: {views_str}",
        f"Reach: {reach_str}",
        f"Návštěvy profilu: {total_profile_visits}",
        f"Interakce: {interactions_str}",
        f"Míra opuštění: {drop_off_str}",
        f"Výsledek ankety/kvízu: {poll_result}",
    ]
    markdown_output = "\n".join(markdown_lines)

    return {
        "total_views": total_views,
        "views_breakdown": views_str,
        "initial_reach": initial_reach,
        "reach_str": reach_str,
        "profile_visits": total_profile_visits,
        "total_interactions": total_interactions,
        "interactions_breakdown": interactions_str,
        "drop_off_rate_pct": drop_off_val if initial_reach > 0 and len(stories) > 1 else None,
        "drop_off_rate_str": drop_off_str,
        "poll_result": poll_result,
        "markdown": markdown_output,
    }


def main():
    parser = argparse.ArgumentParser(description="Extract Instagram Story series performance metrics.")
    parser.add_argument("input_file", nargs="?", help="Path to input JSON file. If omitted, reads from stdin.")
    parser.add_argument("--json", action="store_true", help="Output result as JSON instead of plain markdown.")
    args = parser.parse_args()

    if args.input_file:
        with open(args.input_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    else:
        raw_data = json.load(sys.stdin)

    result = extract_story_series_summary(raw_data)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["markdown"])


if __name__ == "__main__":
    main()
