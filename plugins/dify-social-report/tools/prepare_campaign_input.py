from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.file.file import File
from tools._common import add_core_to_path, compact_json

add_core_to_path()

from social_report.intake import InputFile, prepare_campaign_input  # noqa: E402


class PrepareCampaignInputTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        uploaded = tool_parameters.get("files")
        if not isinstance(uploaded, list) or not uploaded:
            raise ValueError("files must contain at least one Dify file")
        sources = []
        for index, file in enumerate(uploaded, start=1):
            if not isinstance(file, File):
                raise ValueError(f"files[{index - 1}] is not a Dify file")
            sources.append(
                InputFile(
                    source_id=f"upload-{index:03d}",
                    filename=file.filename or f"upload-{index:03d}",
                    content=file.blob,
                    declared_mime_type=file.mime_type,
                )
            )
        prepared = prepare_campaign_input(sources)
        manifest = [file.manifest_entry() for file in prepared]
        result = {"files": [file.source_id for file in prepared], "manifest": manifest}
        yield self.create_json_message(result)
        yield self.create_variable_message("manifest", result)
        yield self.create_variable_message("manifest_json", compact_json(result))
        for file in prepared:
            yield self.create_blob_message(
                file.content,
                meta={"filename": file.transport_name, "mime_type": file.mime_type},
            )
