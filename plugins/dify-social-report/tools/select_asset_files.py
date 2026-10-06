from __future__ import annotations

from collections.abc import Generator
from pathlib import PurePosixPath
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.file.file import File


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
        requested = {str(name).replace("\\", "/") for name in source_files}
        requested_basenames = {PurePosixPath(name).name for name in requested}
        matches = []
        for file in files:
            filename = (file.filename or "").replace("\\", "/")
            if filename in requested or PurePosixPath(filename).name in requested_basenames:
                matches.append(file)
        if not matches:
            asset_id = asset.get("asset_group_id", "unknown")
            raise ValueError(f"no uploaded files matched reconstructed asset {asset_id!r}")
        yield self.create_variable_message("selected_count", len(matches))
        for file in matches:
            yield self.create_blob_message(
                file.blob,
                meta={
                    "filename": file.filename or "campaign-image",
                    "mime_type": file.mime_type or "application/octet-stream",
                },
            )
