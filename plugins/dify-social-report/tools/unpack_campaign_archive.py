from __future__ import annotations

from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from dify_plugin.file.file import File
from tools._common import add_core_to_path, compact_json

add_core_to_path()

from social_report.intake import (  # noqa: E402
    InputFile,
    prepare_campaign_input,
    unpack_campaign_archive,
)


class UnpackCampaignArchiveTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        uploaded = tool_parameters.get("files")
        if not isinstance(uploaded, list) or not uploaded:
            raise ValueError("files must contain at least one Dify file")
        manifest_entries = []
        archive_roots = []
        ignored_entries = []
        for index, file in enumerate(uploaded, start=1):
            if not isinstance(file, File):
                raise ValueError(f"files[{index - 1}] is not a Dify file")
            source = InputFile(
                source_id=f"prepared-{index:03d}",
                filename=file.filename or f"prepared-{index:03d}",
                content=file.blob,
                declared_mime_type=file.mime_type,
            )
            prepared = prepare_campaign_input([source])[0]
            if prepared.mime_type == "application/zip":
                unpacked = unpack_campaign_archive(source)
                archive_roots.append(unpacked.root)
                ignored_entries.extend(unpacked.ignored_entries)
                for entry in unpacked.files:
                    manifest_entries.append(entry.manifest_entry())
                    yield self.create_blob_message(
                        entry.content,
                        meta={
                            "filename": entry.transport_name,
                            "mime_type": entry.mime_type,
                        },
                    )
                del unpacked
            else:
                manifest_entries.append(prepared.manifest_entry())
                yield self.create_blob_message(
                    prepared.content,
                    meta={
                        "filename": prepared.transport_name,
                        "mime_type": prepared.mime_type,
                    },
                )
                del prepared
        manifest = {
            "root": archive_roots[0] if len(archive_roots) == 1 else None,
            "archive_roots": archive_roots,
            "entries": manifest_entries,
            "ignored_entries": ignored_entries,
        }
        yield self.create_json_message(manifest)
        yield self.create_variable_message("manifest", manifest)
        yield self.create_variable_message("manifest_json", compact_json(manifest))
