from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from tools._common import add_core_to_path, compact_json, object_from_json

add_core_to_path()

from social_report.validation import validate_extraction  # noqa: E402


class ValidateExtractionTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        payload = object_from_json(tool_parameters.get("extraction_json"), "extraction_json")
        result = validate_extraction(payload)
        yield self.create_json_message(result)
        yield self.create_variable_message("validated", result)
        yield self.create_variable_message("validated_json", compact_json(result))
