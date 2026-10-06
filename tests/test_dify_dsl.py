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


if __name__ == "__main__":
    unittest.main()
