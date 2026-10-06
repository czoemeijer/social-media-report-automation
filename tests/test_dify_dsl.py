from __future__ import annotations

import unittest
from pathlib import Path

from scripts.validate_dify_dsl import validate


class DifyDslTest(unittest.TestCase):
    def test_workflow_structure(self):
        root = Path(__file__).resolve().parents[1]
        data = validate(root / "deploy" / "dify" / "social-media-report.yml")
        nodes = data["workflow"]["graph"]["nodes"]
        extraction_iteration = next(node for node in nodes if node["id"] == "extract_iteration")
        self.assertTrue(extraction_iteration["data"]["is_parallel"])
        self.assertEqual(extraction_iteration["data"]["parallel_nums"], 4)
        self.assertTrue(
            next(node for node in nodes if node["id"] == "reconstruct")["data"][
                "structured_output_enabled"
            ]
        )

    def test_targeted_second_pass_dsl_structure(self):
        root = Path(__file__).resolve().parents[1]
        data = validate(root / "deploy" / "dify" / "social-media-report.yml")
        nodes = data["workflow"]["graph"]["nodes"]

        # 1. filter_review_assets node exists and takes [validate, validated]
        filter_node = next(node for node in nodes if node["id"] == "filter_review_assets")
        self.assertEqual(filter_node["data"]["type"], "code")
        self.assertEqual(
            filter_node["data"]["variables"][0]["value_selector"],
            ["validate", "validated"],
        )

        # 2. review_iteration node iterates over [filter_review_assets, review_assets]
        review_iter = next(node for node in nodes if node["id"] == "review_iteration")
        self.assertEqual(review_iter["data"]["type"], "iteration")
        self.assertEqual(
            review_iter["data"]["iterator_selector"],
            ["filter_review_assets", "review_assets"],
        )

        # 3. select_review_files inside iteration selects files for [review_iteration, item]
        select_review_files = next(
            node for node in nodes if node["id"] == "select_review_files"
        )
        self.assertEqual(select_review_files["parentId"], "review_iteration")
        self.assertEqual(
            select_review_files["data"]["tool_parameters"]["asset"]["value"],
            ["review_iteration", "item"],
        )

        # 4. second_pass vision selector is strictly [select_review_files, files], NOT [normalize, files]
        second_pass = next(node for node in nodes if node["id"] == "second_pass")
        self.assertEqual(second_pass["parentId"], "review_iteration")
        vision_selector = second_pass["data"]["vision"]["configs"]["variable_selector"]
        self.assertEqual(vision_selector, ["select_review_files", "files"])
        self.assertNotEqual(vision_selector, ["normalize", "files"])

        # 5. merge_reviewed_assets merges original validated campaign with corrected assets
        merge_node = next(node for node in nodes if node["id"] == "merge_reviewed_assets")
        self.assertEqual(merge_node["data"]["type"], "code")
        var_selectors = [v["value_selector"] for v in merge_node["data"]["variables"]]
        self.assertIn(["validate", "validated"], var_selectors)
        self.assertIn(["review_iteration", "output"], var_selectors)

        # 6. second_validate validates merged extraction
        second_val = next(node for node in nodes if node["id"] == "second_validate")
        self.assertEqual(
            second_val["data"]["tool_parameters"]["extraction_json"]["value"],
            ["merge_reviewed_assets", "campaign"],
        )


if __name__ == "__main__":
    unittest.main()
