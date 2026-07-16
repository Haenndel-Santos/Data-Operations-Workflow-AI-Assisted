from __future__ import annotations

import os
import shutil
import tempfile
import time
from collections.abc import Callable, Sequence
from pathlib import Path


DEFAULT_DIRECTORY_PUBLISH_RETRY_DELAYS_SECONDS = (0.1, 0.25, 0.5, 1.0, 2.0)
DEFAULT_FILE_PUBLISH_RETRY_DELAYS_SECONDS = (0.05, 0.1, 0.25, 0.5, 1.0)


class AtomicPublishTargetAppearedError(RuntimeError):
    def __init__(self, target: Path) -> None:
        super().__init__(f"Atomic publication target appeared: {target}")
        self.target = target


def publish_new_directory(
    staging_dir: Path,
    output_dir: Path,
    *,
    retry_delays: Sequence[float] = DEFAULT_DIRECTORY_PUBLISH_RETRY_DELAYS_SECONDS,
    sleep_fn: Callable[[float], None] = time.sleep,
    replace_fn: Callable[[Path, Path], object] | None = None,
) -> None:
    """Publish one new directory and fail closed if its target appears."""
    try:
        for attempt in range(len(retry_delays) + 1):
            try:
                if replace_fn is None:
                    staging_dir.replace(output_dir)
                else:
                    replace_fn(staging_dir, output_dir)
                break
            except PermissionError as error:
                if output_dir.exists():
                    raise AtomicPublishTargetAppearedError(output_dir) from error
                if attempt >= len(retry_delays):
                    raise
                sleep_fn(retry_delays[attempt])
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)


def atomic_write_text(
    path: Path,
    content: str,
    *,
    retry_delays: Sequence[float] = DEFAULT_FILE_PUBLISH_RETRY_DELAYS_SECONDS,
    sleep_fn: Callable[[float], None] = time.sleep,
    replace_fn: Callable[[object, object], object] = os.replace,
) -> None:
    """Replace one text file atomically while cleaning its temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(content)
        for attempt in range(len(retry_delays) + 1):
            try:
                replace_fn(temporary, path)
                break
            except PermissionError:
                if attempt >= len(retry_delays):
                    raise
                sleep_fn(retry_delays[attempt])
    finally:
        if temporary.exists():
            temporary.unlink()
