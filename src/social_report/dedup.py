"""Exact and lightweight perceptual duplicate helpers."""

from __future__ import annotations

import hashlib
import io
from typing import Optional


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def difference_hash(content: bytes) -> Optional[str]:
    """Return a 64-bit difference hash when Pillow can decode the image."""

    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None
    try:
        with Image.open(io.BytesIO(content)) as image:
            gray = ImageOps.grayscale(image).resize((9, 8))
            pixels = list(
                gray.get_flattened_data()
                if hasattr(gray, "get_flattened_data")
                else gray.getdata()
            )
    except Exception:
        return None
    bits = 0
    for row in range(8):
        for column in range(8):
            left = pixels[row * 9 + column]
            right = pixels[row * 9 + column + 1]
            bits = (bits << 1) | int(left > right)
    return f"{bits:016x}"


def hamming_distance(first: str, second: str) -> int:
    if len(first) != len(second):
        raise ValueError("perceptual hashes must have equal length")
    return bin(int(first, 16) ^ int(second, 16)).count("1")


def classify_hash_relationship(
    first_sha256: str,
    second_sha256: str,
    first_perceptual: Optional[str] = None,
    second_perceptual: Optional[str] = None,
    near_threshold: int = 8,
) -> str:
    if first_sha256 == second_sha256:
        return "exact_duplicate"
    if (
        first_perceptual
        and second_perceptual
        and hamming_distance(first_perceptual, second_perceptual) <= near_threshold
    ):
        return "near_duplicate"
    return "unknown"
