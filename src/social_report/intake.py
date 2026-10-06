"""Bounded file intake and in-memory ZIP handling for Dify and CLI callers."""

from __future__ import annotations

import io
import posixpath
import re
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence

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
    transport_name: str

    def manifest_entry(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "relative_path": self.relative_path,
            "filename": self.filename,
            "transport_name": self.transport_name,
            "mime_type": self.mime_type,
            "sha256": self.sha256,
            "size": self.size,
            "perceptual_hash": self.perceptual_hash,
        }


def clean_path(path_str: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", path_str.replace("\\", "/"))


def file_matches_target(filename: str, target: str) -> bool:
    """Return True if filename matches target by exact path or transport name."""
    norm_filename = (filename or "").replace("\\", "/")
    if not norm_filename:
        return False
    if norm_filename == target:
        return True
    if "__" in norm_filename and norm_filename.startswith("sr_"):
        _, _, embedded = norm_filename.partition("__")
        clean_tgt = clean_path(target)
        if embedded in (target, clean_tgt):
            return True
        if "/" in target and (
            embedded.endswith(f"_{clean_tgt}") or embedded.endswith(f"/{target}")
        ):
            return True
    return False


def extract_file_basename(filename: str) -> str:
    norm_filename = (filename or "").replace("\\", "/")
    if "__" in norm_filename and norm_filename.startswith("sr_"):
        _, _, embedded = norm_filename.partition("__")
        return PurePosixPath(embedded.replace("_", "/")).name
    return PurePosixPath(norm_filename).name


def match_asset_files(
    files: Sequence[Any],
    source_files: Sequence[str],
    *,
    get_filename: Callable[[Any], str] = lambda f: getattr(f, "filename", str(f)) or "",
) -> list[Any]:
    """Strictly resolve asset source files against available file objects.

    Hierarchy:
    1. Exact relative_path or transport_name match.
    2. Provably unambiguous basename fallback.
    Raises ValueError on ambiguous basename match.
    """
    matched_files: list[Any] = []
    matched_filenames: set[str] = set()

    for req_raw in source_files:
        req = str(req_raw).replace("\\", "/").strip()
        if not req:
            continue

        # 1. Exact path or transport match
        exact_matches = [f for f in files if file_matches_target(get_filename(f), req)]
        if exact_matches:
            for f in exact_matches:
                fname = get_filename(f)
                if fname not in matched_filenames:
                    matched_files.append(f)
                    matched_filenames.add(fname)
            continue

        # 2. Provably unambiguous basename fallback
        req_base = PurePosixPath(req).name
        candidate_basename_matches = [
            f for f in files if extract_file_basename(get_filename(f)) == req_base
        ]
        if len(candidate_basename_matches) > 1:
            names = [get_filename(f) for f in candidate_basename_matches]
            raise ValueError(
                f"ambiguous file reference {req!r} matches multiple files {names}. "
                "Use exact relative_path or stable identifier."
            )
        if len(candidate_basename_matches) == 1:
            f = candidate_basename_matches[0]
            fname = get_filename(f)
            if fname not in matched_filenames:
                matched_files.append(f)
                matched_filenames.add(fname)
            continue

    return matched_files


def make_transport_name(filename: str, relative_path: Optional[str], sha256_val: str) -> str:
    prefix = sha256_val[:12]
    target = relative_path if relative_path else filename
    clean_target = clean_path(target)
    return f"sr_{prefix}__{clean_target}"


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
    """Detect MIME type strictly from byte magic signatures.

    Returns application/octet-stream for unknown signatures. Never guesses from filenames.
    """
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
    return "application/octet-stream"


def validate_image_decoder(content: bytes, expected_mime: str) -> None:
    """Verify that candidate image bytes decode cleanly and match expected format."""
    try:
        from PIL import Image
    except ImportError:
        return
    try:
        with Image.open(io.BytesIO(content)) as img:
            img.verify()
            fmt = (img.format or "").upper()
            mime_map = {
                "PNG": "image/png",
                "JPEG": "image/jpeg",
                "GIF": "image/gif",
                "WEBP": "image/webp",
            }
            actual_mime = mime_map.get(fmt)
            if actual_mime != expected_mime:
                raise ValueError(
                    f"decoded format {fmt} does not match detected MIME {expected_mime}"
                )
    except Exception as exc:
        raise ValueError(f"corrupt, truncated, or unreadable image data: {exc}") from exc


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
    if detected in SUPPORTED_IMAGE_MIMES:
        validate_image_decoder(source.content, detected)
    declared = source.declared_mime_type
    if declared and declared not in {detected, "application/octet-stream"}:
        image_alias = declared in SUPPORTED_IMAGE_MIMES and detected in SUPPORTED_IMAGE_MIMES
        zip_alias = declared in ZIP_MIMES and detected == "application/zip"
        if not (image_alias or zip_alias):
            raise ValueError(
                f"{filename!r} declared MIME {declared!r} does not match detected {detected!r}"
            )
    if detected not in SUPPORTED_IMAGE_MIMES:
        raise ValueError(f"unsupported file type for {filename!r}: {detected}")
    sha = sha256_bytes(source.content)
    transport_name = make_transport_name(filename, source.relative_path, sha)
    return PreparedFile(
        source_id=source.source_id,
        filename=filename,
        content=source.content,
        mime_type=detected,
        sha256=sha,
        size=size,
        relative_path=source.relative_path,
        perceptual_hash=difference_hash(source.content)
        if detected in SUPPORTED_IMAGE_MIMES
        else None,
        transport_name=transport_name,
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
    max_total_size: int = 100 * 1024 * 1024,
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
