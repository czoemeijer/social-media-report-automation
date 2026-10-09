from __future__ import annotations

import copy
import unittest
from pathlib import Path

import yaml

from scripts.validate_dify_dsl import validate, validate_variable_references


class DifyDslTest(unittest.TestCase):
    def test_workflow_structure(self):
        root = Path(__file__).resolve().parents[1]
        data = validate(root / "deploy" / "dify" / "social-media-report.yml")
        nodes = data["workflow"]["graph"]["nodes"]
        extraction_iteration = next(node for node in nodes if node["id"] == "extract_iteration")
        self.assertFalse(extraction_iteration["data"]["is_parallel"])
        self.assertEqual(extraction_iteration["data"]["parallel_nums"], 1)
        self.assertTrue(
            next(node for node in nodes if node["id"] == "reconstruct")["data"][
                "structured_output_enabled"
            ]
        )
        start = next(node for node in nodes if node["id"] == "start")
        upload = start["data"]["variables"][0]
        self.assertIn("custom", upload["allowed_file_types"])
        self.assertIn(".ZIP", upload["allowed_file_extensions"])

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
        self.assertNotIn("error_strategy", review_iter["data"])
        self.assertFalse(review_iter["data"]["is_parallel"])
        self.assertEqual(review_iter["data"]["parallel_nums"], 1)
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

    def test_semantic_variable_validation_regressions(self):
        root = Path(__file__).resolve().parents[1]
        base_data = yaml.safe_load(
            (root / "deploy" / "dify" / "social-media-report.yml").read_text(encoding="utf-8")
        )

        # 1. Base DSL has zero variable reference errors
        errors = validate_variable_references(base_data)
        self.assertEqual(errors, [])

        # 2. Nonexistent tool output produces error
        data = copy.deepcopy(base_data)
        nodes = data["workflow"]["graph"]["nodes"]
        end_node = next(n for n in nodes if n["id"] == "end")
        end_node["data"]["outputs"][0]["value_selector"] = ["audit", "nonexistent_field"]
        errors = validate_variable_references(data)
        self.assertTrue(any("nonexistent_field" in e for e in errors))

        # 3. Wrong nested structured-output path produces error
        data = copy.deepcopy(base_data)
        nodes = data["workflow"]["graph"]["nodes"]
        iter_node = next(n for n in nodes if n["id"] == "extract_iteration")
        iter_node["data"]["iterator_selector"] = ["reconstruct", "structured_output", "nonexistent_key"]
        errors = validate_variable_references(data)
        self.assertTrue(any("nonexistent_key" in e for e in errors))

        # 4. Invalid End selector (nonexistent source node)
        data = copy.deepcopy(base_data)
        nodes = data["workflow"]["graph"]["nodes"]
        end_node = next(n for n in nodes if n["id"] == "end")
        end_node["data"]["outputs"][0]["value_selector"] = ["ghost_node", "output"]
        errors = validate_variable_references(data)
        self.assertTrue(any("ghost_node" in e for e in errors))

        # 5. Invalid code selector
        data = copy.deepcopy(base_data)
        nodes = data["workflow"]["graph"]["nodes"]
        val_node = next(n for n in nodes if n["id"] == "validate")
        val_node["data"]["tool_parameters"]["extraction_json"]["value"] = [
            "join_extractions",
            "fake_code_output",
        ]
        errors = validate_variable_references(data)
        self.assertTrue(any("fake_code_output" in e for e in errors))

        # 6. Standard tool outputs (files, text, json) are valid
        data = copy.deepcopy(base_data)
        nodes = data["workflow"]["graph"]["nodes"]
        end_node = next(n for n in nodes if n["id"] == "end")
        end_node["data"]["outputs"][0]["value_selector"] = ["audit", "files"]
        end_node["data"]["outputs"][1]["value_selector"] = ["audit", "text"]
        end_node["data"]["outputs"][2]["value_selector"] = ["audit", "json"]
        errors = validate_variable_references(data)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
