#!/usr/bin/env python3
"""Score one structured workflow prediction against synthetic ground truth."""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from social_report.metrics import audit_campaign  # noqa: E402

DEFAULT_TRUTH = ROOT / "evals" / "fixtures" / "synthetic_campaign_001" / "ground_truth.json"


def _by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(item.get("asset_group_id")): item for item in items}


def _ratio(matches: int, total: int) -> float | None:
    return round(matches / total, 4) if total else None


def _pairwise_groups(assets: list[dict[str, Any]]) -> dict[tuple[str, str], bool]:
    file_to_group = {
        str(filename): str(asset.get("asset_group_id"))
        for asset in assets
        for filename in asset.get("source_files", [])
    }
    return {
        tuple(sorted((first, second))): file_to_group[first] == file_to_group[second]
        for first, second in itertools.combinations(sorted(file_to_group), 2)
    }


def evaluate(prediction: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    expected_assets = _by_id(truth["assets"])
    predicted_assets = _by_id(prediction.get("assets", []))
    fields_total = fields_match = exact_total = exact_match = null_total = null_match = 0
    scope_total = scope_match = story_total = story_match = 0
    for asset_id, expected in expected_assets.items():
        predicted = predicted_assets.get(asset_id, {})
        scope_total += 1
        scope_match += int(predicted.get("scope") == expected.get("scope"))
        if expected.get("story_id") is not None:
            story_total += 1
            story_match += int(predicted.get("story_id") == expected.get("story_id"))
        predicted_metrics = predicted.get("metrics", {})
        for name, expected_metric in expected.get("metrics", {}).items():
            actual = predicted_metrics.get(name, {})
            fields_total += 1
            fields_match += int(
                actual.get("value") == expected_metric.get("value")
                and actual.get("precision") == expected_metric.get("precision")
            )
            if expected_metric.get("precision") == "exact":
                exact_total += 1
                exact_match += int(actual.get("value") == expected_metric.get("value"))
            if expected_metric.get("value") in {None, 0}:
                null_total += 1
                null_match += int(actual.get("value") == expected_metric.get("value"))

    expected_groups = _pairwise_groups(truth["reconstruction"]["assets"])
    actual_groups = _pairwise_groups(prediction.get("reconstruction", {}).get("assets", []))
    true_positive = sum(
        actual_groups.get(pair) is True and same for pair, same in expected_groups.items()
    )
    false_positive = sum(
        actual_groups.get(pair) is True and not same for pair, same in expected_groups.items()
    )
    false_negative = sum(
        actual_groups.get(pair) is not True and same for pair, same in expected_groups.items()
    )
    precision = (
        true_positive / (true_positive + false_positive) if true_positive + false_positive else 0
    )
    recall = (
        true_positive / (true_positive + false_negative) if true_positive + false_negative else 0
    )
    grouping_f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0

    numerical_consistency = 1.0
    try:
        audit_campaign({"assets": prediction.get("assets", [])})
    except (TypeError, ValueError):
        numerical_consistency = 0.0
    return {
        "case_id": truth["case_id"],
        "field_extraction_accuracy": _ratio(fields_match, fields_total),
        "exact_number_fidelity": _ratio(exact_match, exact_total),
        "null_vs_zero_accuracy": _ratio(null_match, null_total),
        "scope_classification_accuracy": _ratio(scope_match, scope_total),
        "asset_grouping_pairwise_f1": round(grouping_f1, 4),
        "story_grouping_accuracy": _ratio(story_match, story_total),
        "final_numerical_consistency": numerical_consistency,
        "counts": {"expected_assets": len(expected_assets), "scored_metric_fields": fields_total},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("prediction", type=Path)
    parser.add_argument("--truth", type=Path, default=DEFAULT_TRUTH)
    args = parser.parse_args()
    prediction = json.loads(args.prediction.read_text(encoding="utf-8"))
    truth = json.loads(args.truth.read_text(encoding="utf-8"))
    print(json.dumps(evaluate(prediction, truth), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
