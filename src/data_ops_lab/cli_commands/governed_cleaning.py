from __future__ import annotations

import argparse
from pathlib import Path


def register_governed_cleaning_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the opt-in governed cleaning route: propose, authorize, apply.

    The legacy default workflow is untouched; these commands never run unless
    invoked explicitly, and none of them changes a source file.
    """

    propose = subparsers.add_parser(
        "governed-cleaning-propose",
        help="Profile local Parquet and publish governed candidates, configured and automatic steps; changes no value.",
    )
    propose.add_argument("--parquet-dir", type=Path, required=True, help="Directory of source .parquet files.")
    propose.add_argument("--source-manifest", type=Path, default=None, help="Optional manifest listing files with sha256; verified against the actual files, never trusted alone.")
    propose.add_argument("--output", type=Path, default=Path("outputs/governed_cleaning/proposal"), help="New directory for the proposal bundle.")

    authorize = subparsers.add_parser(
        "governed-cleaning-authorize",
        help="Validate the human review and the cleaning policy against a proposal and publish an ordered, hash-bound application plan; changes no value.",
    )
    authorize.add_argument("--proposal", type=Path, required=True, help="Proposal bundle directory from governed-cleaning-propose.")
    authorize.add_argument("--parquet-dir", type=Path, required=True, help="The same source directory; its hash must still match the proposal.")
    authorize.add_argument("--review", type=Path, default=None, help="Completed review file (from review_template.yml). Missing decisions make the authorization incomplete.")
    authorize.add_argument("--policy", type=Path, default=None, help="Dataset-scoped cleaning policy for configured_only operations.")
    authorize.add_argument("--output", type=Path, default=Path("outputs/governed_cleaning/authority"), help="New directory for the authority bundle.")

    apply = subparsers.add_parser(
        "governed-cleaning-apply",
        help="Re-verify every authority and the plan against the current source, then apply in plan order and publish output with lineage atomically.",
    )
    apply.add_argument("--authority", type=Path, required=True, help="Authority bundle directory from governed-cleaning-authorize.")
    apply.add_argument("--parquet-dir", type=Path, required=True, help="The same source directory; its hash must still match the authorization.")
    apply.add_argument("--output", type=Path, default=Path("outputs/governed_cleaning/output"), help="New directory for the applied Parquet, lineage, and manifest.")
