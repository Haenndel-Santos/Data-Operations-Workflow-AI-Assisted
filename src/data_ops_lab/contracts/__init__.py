"""Shared internal contracts for stable cross-module behavior."""

from .atomic_publish import (
    DEFAULT_DIRECTORY_PUBLISH_RETRY_DELAYS_SECONDS,
    DEFAULT_FILE_PUBLISH_RETRY_DELAYS_SECONDS,
    AtomicPublishTargetAppearedError,
    atomic_write_text,
    publish_new_directory,
)
from .blockers import STANDARD_BLOCKER_FIELDS, StandardBlocker, add_blocker
from .error_taxonomy import (
    ERROR_CLASSIFICATION_REGISTRY,
    ErrorCategory,
    ErrorClassification,
    classify_error,
)
from .hashing import FILE_HASH_CHUNK_SIZE, file_sha256
from .source_bindings import (
    declared_file_sha256_bindings,
    existing_file_sha256_bindings,
)

__all__ = [
    "DEFAULT_DIRECTORY_PUBLISH_RETRY_DELAYS_SECONDS",
    "DEFAULT_FILE_PUBLISH_RETRY_DELAYS_SECONDS",
    "FILE_HASH_CHUNK_SIZE",
    "ERROR_CLASSIFICATION_REGISTRY",
    "STANDARD_BLOCKER_FIELDS",
    "AtomicPublishTargetAppearedError",
    "ErrorCategory",
    "ErrorClassification",
    "StandardBlocker",
    "add_blocker",
    "atomic_write_text",
    "classify_error",
    "declared_file_sha256_bindings",
    "existing_file_sha256_bindings",
    "file_sha256",
    "publish_new_directory",
]
