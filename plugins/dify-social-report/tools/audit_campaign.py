from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from tools._common import add_core_to_path, compact_json, object_from_json

add_core_to_path()

from social_report.metrics import audit_campaign  # noqa: E402


class AuditCampaignTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        payload = object_from_json(tool_parameters.get("campaign_json"), "campaign_json")
        result = audit_campaign(payload)
        yield self.create_json_message(result)
        yield self.create_variable_message("audit", result)
        yield self.create_variable_message("audit_json", compact_json(result))
