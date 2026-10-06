from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.file.file import File
from tools._common import add_core_to_path, compact_json

add_core_to_path()

from social_report.intake import InputFile, unpack_campaign_archive  # noqa: E402


class UnpackCampaignArchiveTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        archive = tool_parameters.get("archive")
        if not isinstance(archive, File):
            raise ValueError("archive must be a Dify file")
        result = unpack_campaign_archive(
            InputFile(
                source_id="archive-001",
                filename=archive.filename or "campaign.zip",
                content=archive.blob,
                declared_mime_type=archive.mime_type,
            )
        )
        manifest = result.manifest()
        yield self.create_json_message(manifest)
        yield self.create_variable_message("manifest_json", compact_json(manifest))
        for file in result.files:
            yield self.create_blob_message(
                file.content,
                meta={"filename": file.relative_path or file.filename, "mime_type": file.mime_type},
            )
