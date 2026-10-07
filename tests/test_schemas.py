from __future__ import annotations

import json
import unittest
from pathlib import Path

from social_report.schemas import SCHEMAS


class SchemaArtifactTest(unittest.TestCase):
    def test_committed_schemas_match_runtime_definitions(self):
        root = Path(__file__).resolve().parents[1]
        for filename, expected in SCHEMAS.items():
            actual = json.loads((root / "schemas" / filename).read_text(encoding="utf-8"))
            self.assertEqual(actual, expected, filename)


if __name__ == "__main__":
    unittest.main()
