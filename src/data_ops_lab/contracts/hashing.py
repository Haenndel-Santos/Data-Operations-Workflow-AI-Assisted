from __future__ import annotations

import hashlib
from pathlib import Path


FILE_HASH_CHUNK_SIZE = 1024 * 1024


def file_sha256(path: Path) -> str:
    """Return the lowercase SHA-256 digest used by existing file bindings."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(FILE_HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()
