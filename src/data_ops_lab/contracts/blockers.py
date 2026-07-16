from __future__ import annotations

from typing import TypedDict


STANDARD_BLOCKER_FIELDS = (
    "blocker_id",
    "blocker_type",
    "field",
    "explanation",
)


class StandardBlocker(TypedDict):
    blocker_id: str
    blocker_type: str
    field: str
    explanation: str


def add_blocker(
    blockers: list[dict[str, str]],
    blocker_type: str,
    explanation: str,
    *,
    field: str = "",
) -> None:
    """Append one version-1 standard blocker without changing legacy output."""
    blockers.append(
        {
            "blocker_id": f"BLOCKER_{len(blockers) + 1:03d}",
            "blocker_type": blocker_type,
            "field": field,
            "explanation": explanation,
        }
    )
