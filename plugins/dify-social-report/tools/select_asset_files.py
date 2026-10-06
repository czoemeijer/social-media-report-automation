from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.file.file import File
from tools._common import add_core_to_path

add_core_to_path()

from social_report.intake import match_asset_files  # noqa: E402


class SelectAssetFilesTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        files = tool_parameters.get("files")
        asset = tool_parameters.get("asset")
        if not isinstance(files, list) or not all(isinstance(file, File) for file in files):
            raise ValueError("files must be a Dify file list")
        if not isinstance(asset, dict):
            raise ValueError("asset must be a reconstructed asset object")
        source_files = asset.get("source_files")
        if not isinstance(source_files, list) or not source_files:
            raise ValueError("asset.source_files must be a non-empty list")

        matched_files = match_asset_files(
            files,
            source_files,
            get_filename=lambda f: f.filename or "",
        )

        if not matched_files:
            asset_id = asset.get("asset_group_id", "unknown")
            raise ValueError(f"no uploaded files matched reconstructed asset {asset_id!r}")

        yield self.create_variable_message("selected_count", len(matched_files))
        for file in matched_files:
            yield self.create_blob_message(
                file.blob,
                meta={
                    "filename": file.filename or "campaign-image",
                    "mime_type": file.mime_type or "application/octet-stream",
                },
            )
