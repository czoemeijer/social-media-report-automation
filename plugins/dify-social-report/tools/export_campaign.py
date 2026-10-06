from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from tools._common import add_core_to_path, object_from_json

add_core_to_path()

from social_report.reporting import export_csv, export_json, export_markdown  # noqa: E402


class ExportCampaignTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        payload = object_from_json(tool_parameters.get("audit_json"), "audit_json")
        output_format = tool_parameters.get("format", "json")
        exporters = {
            "json": (export_json, "campaign-audit.json", "application/json"),
            "csv": (export_csv, "campaign-assets.csv", "text/csv"),
            "markdown": (export_markdown, "campaign-audit.md", "text/markdown"),
        }
        if output_format not in exporters:
            raise ValueError("format must be json, csv, or markdown")
        exporter, filename, mime_type = exporters[output_format]
        yield self.create_blob_message(
            exporter(payload), meta={"filename": filename, "mime_type": mime_type}
        )
