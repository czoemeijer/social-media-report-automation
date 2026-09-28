#!/usr/bin/env python3
"""
calculate_metrics.py
Deterministic metrics calculation and audit engine for social-report-audit.

Requirements: Python 3.8+ (standard library only).
"""

import json
import sys
import argparse
from typing import Dict, Any, List, Optional, Tuple


def calculate_single_item(item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculates deterministic secondary metrics for a single content item.
    Enforces organic vs paid boundaries, handles approximate flags,
    and calculates known engagement actions.
    """
    result = dict(item)

    # Extract raw metrics
    likes = item.get("likes")
    comments = item.get("comments")
    shares = item.get("shares")
    saves = item.get("saves")
    reach = item.get("reach")
    views = item.get("views")
    platform_interactions = item.get("platform_reported_interactions")
    scope = item.get("scope", "organic").lower()
    reach_is_approximate = item.get("reach_is_approximate", False)

    # Validation: organic vs paid boundaries
    if scope == "paid":
        result["warnings"] = result.get("warnings", [])
        result["warnings"].append(
            "Paid scope detected: Standard organic ER by Reach is not applicable to paid media."
        )

    # 1. Known engagement actions (Likes + Comments + Shares + Saves)
    known_components = [likes, comments, shares, saves]
    valid_components = [c for c in known_components if c is not None]

    if len(valid_components) == 4:
        known_actions = sum(valid_components)
        result["known_engagement_actions"] = known_actions
    elif len(valid_components) > 0:
        known_actions = sum(valid_components)
        result["known_engagement_actions"] = known_actions
        result["missing_engagement_components"] = [
            name for name, val in [("likes", likes), ("comments", comments), ("shares", shares), ("saves", saves)] if val is None
        ]
    else:
        known_actions = None
        result["known_engagement_actions"] = None

    # 2. Platform interactions discrepancy check
    if platform_interactions is not None and known_actions is not None:
        result["uncategorized_interactions"] = platform_interactions - known_actions
        if platform_interactions != known_actions:
            result["interaction_discrepancy"] = True
        else:
            result["interaction_discrepancy"] = False

    # 3. Calculated ER by Reach
    if reach is not None and reach > 0 and known_actions is not None:
        er = (known_actions / reach) * 100.0
        result["calculated_er_by_reach"] = round(er, 4)
        result["er_is_approximate"] = reach_is_approximate
    else:
        result["calculated_er_by_reach"] = None
        result["er_is_approximate"] = False

    # 4. Save Rate (Saves / Reach)
    if reach is not None and reach > 0 and saves is not None:
        save_rate = (saves / reach) * 100.0
        result["save_rate_pct"] = round(save_rate, 4)
    else:
        result["save_rate_pct"] = None

    # 5. Comment to Like Ratio (Comments / Likes)
    if likes is not None and likes > 0 and comments is not None:
        com_like_ratio = (comments / likes) * 100.0
        result["comment_to_like_ratio_pct"] = round(com_like_ratio, 4)
    else:
        result["comment_to_like_ratio_pct"] = None

    return result


def aggregate_campaign(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregates metrics across multiple content items / creators.
    Labels summed reach explicitly and prevents silent addition of uncategorized interactions.
    """
    total_views = 0
    total_likes = 0
    total_comments = 0
    total_shares = 0
    total_saves = 0
    sum_content_reach = 0
    total_known_actions = 0
    total_platform_interactions = 0

    has_views = False
    has_likes = False
    has_comments = False
    has_shares = False
    has_saves = False
    has_reach = False
    has_platform_interactions = False

    for item in items:
        # Organic only for standard aggregated ER
        if item.get("scope", "organic") == "paid":
            continue

        res = calculate_single_item(item)

        if res.get("views") is not None:
            total_views += res["views"]
            has_views = True
        if res.get("likes") is not None:
            total_likes += res["likes"]
            has_likes = True
        if res.get("comments") is not None:
            total_comments += res["comments"]
            has_comments = True
        if res.get("shares") is not None:
            total_shares += res["shares"]
            has_shares = True
        if res.get("saves") is not None:
            total_saves += res["saves"]
            has_saves = True
        if res.get("reach") is not None:
            sum_content_reach += res["reach"]
            has_reach = True
        if res.get("known_engagement_actions") is not None:
            total_known_actions += res["known_engagement_actions"]
        if res.get("platform_reported_interactions") is not None:
            total_platform_interactions += res["platform_reported_interactions"]
            has_platform_interactions = True

    calculated_er = None
    if has_reach and sum_content_reach > 0 and total_known_actions > 0:
        calculated_er = round((total_known_actions / sum_content_reach) * 100.0, 4)

    save_rate = None
    if has_reach and sum_content_reach > 0 and has_saves:
        save_rate = round((total_saves / sum_content_reach) * 100.0, 4)

    com_like_ratio = None
    if has_likes and total_likes > 0 and has_comments:
        com_like_ratio = round((total_comments / total_likes) * 100.0, 4)

    summary = {
        "total_views": total_views if has_views else None,
        "total_likes": total_likes if has_likes else None,
        "total_comments": total_comments if has_comments else None,
        "total_shares": total_shares if has_shares else None,
        "total_saves": total_saves if has_saves else None,
        "total_known_engagement_actions": total_known_actions,
        "sum_of_content_reach": sum_content_reach if has_reach else None,
        "reach_aggregation_warning": (
            "Sum of content-level Reach contains audience overlap and must not be interpreted as unique campaign Reach."
        ),
        "weighted_calculated_er_by_reach": calculated_er,
        "overall_save_rate_pct": save_rate,
        "overall_comment_to_like_ratio_pct": com_like_ratio,
    }

    if has_platform_interactions:
        summary["total_platform_reported_interactions"] = total_platform_interactions
        summary["total_uncategorized_interactions"] = total_platform_interactions - total_known_actions

    return summary


def main():
    parser = argparse.ArgumentParser(description="Calculate and audit social media metrics.")
    parser.add_argument("input_file", nargs="?", help="Path to JSON file with input items or campaign structure.")
    parser.add_argument("--stdin", action="store_true", help="Read JSON from standard input.")
    args = parser.parse_args()

    raw_input = None
    if args.stdin or not args.input_file:
        if not sys.stdin.isatty():
            raw_input = sys.stdin.read()
        else:
            parser.print_help()
            sys.exit(1)
    else:
        with open(args.input_file, "r", encoding="utf-8") as f:
            raw_input = f.read()

    try:
        data = json.loads(raw_input)
    except Exception as e:
        print(f"Error parsing JSON: {e}", file=sys.stderr)
        sys.exit(1)

    if isinstance(data, list):
        individual = [calculate_single_item(item) for item in data]
        aggregated = aggregate_campaign(data)
        output = {"items": individual, "campaign_summary": aggregated}
    elif isinstance(data, dict):
        if "items" in data:
            individual = [calculate_single_item(item) for item in data["items"]]
            aggregated = aggregate_campaign(data["items"])
            output = {"items": individual, "campaign_summary": aggregated}
        else:
            output = calculate_single_item(data)
    else:
        print("Invalid input JSON structure. Expected dict or list of dicts.", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
