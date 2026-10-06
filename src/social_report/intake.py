"""Bounded file intake and in-memory ZIP handling for Dify and CLI callers."""

from __future__ import annotations

import io
import mimetypes
import posixpath
import re
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .dedup import difference_hash, sha256_bytes

SUPPORTED_IMAGE_MIMES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
ZIP_MIMES = {"application/zip", "application/x-zip-compressed"}
ARCHIVE_SUFFIXES = {".zip", ".tar", ".gz", ".tgz", ".7z", ".rar"}


@dataclass(frozen=True)
class InputFile:
    source_id: str
    filename: str
    content: bytes
    declared_mime_type: Optional[str] = None
    relative_path: Optional[str] = None


@dataclass(frozen=True)
class PreparedFile:
    source_id: str
    filename: str
    content: bytes
    mime_type: str
    sha256: str
    size: int
    relative_path: Optional[str]
    perceptual_hash: Optional[str]

    def manifest_entry(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "relative_path": self.relative_path,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "sha256": self.sha256,
            "size": self.size,
            "perceptual_hash": self.perceptual_hash,
        }


@dataclass(frozen=True)
class ArchiveResult:
    root: Optional[str]
    files: Sequence[PreparedFile]
    ignored_entries: Sequence[str]

    def manifest(self) -> Dict[str, Any]:
        return {
            "root": self.root,
            "entries": [file.manifest_entry() for file in self.files],
            "ignored_entries": list(self.ignored_entries),
        }


def detect_mime(content: bytes, filename: str = "") -> str:
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content[:6] in {b"GIF87a", b"GIF89a"}:
        return "image/gif"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if content.startswith(b"PK\x03\x04") or content.startswith(b"PK\x05\x06"):
        return "application/zip"
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


def _safe_direct_filename(filename: str) -> str:
    if not filename or "\x00" in filename:
        raise ValueError("file has an empty or unsafe filename")
    normalized = filename.replace("\\", "/")
    if normalized.startswith("/") or "/" in normalized or re.match(r"^[A-Za-z]:", normalized):
        raise ValueError(f"direct upload filename must not contain a path: {filename!r}")
    return normalized


def _prepare_one(source: InputFile, max_file_size: int) -> PreparedFile:
    filename = (
        _safe_direct_filename(source.filename) if source.relative_path is None else source.filename
    )
    size = len(source.content)
    if size == 0:
        raise ValueError(f"{filename!r} is empty")
    if size > max_file_size:
        raise ValueError(f"{filename!r} exceeds the {max_file_size}-byte file limit")
    detected = detect_mime(source.content, filename)
    declared = source.declared_mime_type
    if declared and declared not in {detected, "application/octet-stream"}:
        aliases_match = declared in ZIP_MIMES and detected == "application/zip"
        if not aliases_match:
            raise ValueError(
                f"{filename!r} declared MIME {declared!r} does not match detected {detected!r}"
            )
    if detected not in SUPPORTED_IMAGE_MIMES | {"application/zip"}:
        raise ValueError(f"unsupported file type for {filename!r}: {detected}")
    return PreparedFile(
        source_id=source.source_id,
        filename=filename,
        content=source.content,
        mime_type=detected,
        sha256=sha256_bytes(source.content),
        size=size,
        relative_path=source.relative_path,
        perceptual_hash=difference_hash(source.content)
        if detected in SUPPORTED_IMAGE_MIMES
        else None,
    )


def prepare_campaign_input(
    files: Iterable[InputFile],
    *,
    max_files: int = 100,
    max_file_size: int = 25 * 1024 * 1024,
) -> List[PreparedFile]:
    sources = list(files)
    if not sources:
        raise ValueError("at least one screenshot or ZIP is required")
    if len(sources) > max_files:
        raise ValueError(f"input contains {len(sources)} files; limit is {max_files}")
    return [_prepare_one(source, max_file_size) for source in sources]


def _safe_zip_path(raw_name: str) -> PurePosixPath:
    normalized = raw_name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or "\x00" in normalized
        or normalized.startswith("/")
        or path.is_absolute()
        or ".." in path.parts
        or any(re.match(r"^[A-Za-z]:", part) for part in path.parts)
    ):
        raise ValueError(f"unsafe ZIP entry path: {raw_name!r}")
    return path


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    return ((info.external_attr >> 16) & 0o170000) == 0o120000


def _common_root(paths: Sequence[PurePosixPath]) -> Optional[str]:
    if not paths:
        return None
    first_parts = {path.parts[0] for path in paths if len(path.parts) > 1}
    return next(iter(first_parts)) if len(first_parts) == 1 else None


def unpack_campaign_archive(
    archive: InputFile,
    *,
    max_files: int = 100,
    max_file_size: int = 25 * 1024 * 1024,
    max_total_size: int = 500 * 1024 * 1024,
    max_compression_ratio: int = 100,
) -> ArchiveResult:
    if detect_mime(archive.content, archive.filename) != "application/zip":
        raise ValueError("archive must be a ZIP file")
    extracted: List[PreparedFile] = []
    ignored: List[str] = []
    paths: List[PurePosixPath] = []
    total_uncompressed = 0

    try:
        container = zipfile.ZipFile(io.BytesIO(archive.content))
    except zipfile.BadZipFile as exc:
        raise ValueError("invalid ZIP archive") from exc

    with container:
        entries = [info for info in container.infolist() if not info.is_dir()]
        if len(entries) > max_files:
            raise ValueError(f"ZIP contains {len(entries)} files; limit is {max_files}")
        for info in entries:
            path = _safe_zip_path(info.filename)
            if _is_symlink(info):
                raise ValueError(f"ZIP symlink entries are not allowed: {info.filename!r}")
            if info.flag_bits & 0x1:
                raise ValueError(f"encrypted ZIP entries are not supported: {info.filename!r}")
            if PurePosixPath(path.name).suffix.lower() in ARCHIVE_SUFFIXES:
                raise ValueError(f"nested archives are not allowed: {info.filename!r}")
            if info.file_size > max_file_size:
                raise ValueError(f"ZIP entry exceeds per-file limit: {info.filename!r}")
            total_uncompressed += info.file_size
            if total_uncompressed > max_total_size:
                raise ValueError("ZIP exceeds total uncompressed size limit")
            if info.compress_size == 0 and info.file_size > 0:
                raise ValueError(f"suspicious zero-size compressed entry: {info.filename!r}")
            if info.compress_size and info.file_size / info.compress_size > max_compression_ratio:
                raise ValueError(f"ZIP entry exceeds compression-ratio limit: {info.filename!r}")

            path_text = posixpath.normpath(str(path))
            if path.name in {".DS_Store", "Thumbs.db"} or "__MACOSX" in path.parts:
                ignored.append(path_text)
                continue
            content = container.read(info)
            mime_type = detect_mime(content, path.name)
            if mime_type not in SUPPORTED_IMAGE_MIMES:
                ignored.append(path_text)
                continue
            source = InputFile(
                source_id=f"{archive.source_id}:{path_text}",
                filename=path.name,
                content=content,
                declared_mime_type=mime_type,
                relative_path=path_text,
            )
            extracted.append(_prepare_one(source, max_file_size))
            paths.append(path)
    if not extracted:
        raise ValueError("ZIP contains no supported images")
    return ArchiveResult(root=_common_root(paths), files=extracted, ignored_entries=ignored)
