from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .hashing import file_sha256


def existing_file_sha256_bindings(
    paths: Mapping[str, Path],
) -> dict[str, str]:
    """Hash existing files in input order and omit missing or non-file paths."""
    return {
        name: file_sha256(path)
        for name, path in paths.items()
        if path.is_file()
    }
