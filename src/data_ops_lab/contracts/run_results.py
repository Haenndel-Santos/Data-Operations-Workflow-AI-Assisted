"""Additive projection for shared module run-result metadata."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


RUN_RESULT_ENVELOPE_FIELDS = (
    "output_dir",
    "status",
    "blocker_count",
    "outputs_changed",
)


@runtime_checkable
class RunResultLike(Protocol):
    """Structural contract implemented by compatible existing result classes."""

    @property
    def output_dir(self) -> Path: ...

    @property
    def status(self) -> str: ...

    @property
    def blocker_count(self) -> int: ...

    @property
    def outputs_changed(self) -> bool: ...


@dataclass(frozen=True)
class RunResultEnvelope:
    """Common orchestration metadata without module-specific interpretation."""

    output_dir: Path
    status: str
    blocker_count: int
    outputs_changed: bool


def project_run_result(result: RunResultLike) -> RunResultEnvelope:
    """Copy only proven-equivalent fields without normalizing their values."""

    return RunResultEnvelope(
        output_dir=result.output_dir,
        status=result.status,
        blocker_count=result.blocker_count,
        outputs_changed=result.outputs_changed,
    )
