from __future__ import annotations

import argparse
from pathlib import Path


def register_erp_modeling_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register Step 3 ERP modeling and human-review commands."""

    onboard = subparsers.add_parser(
        "source-onboard",
        help="Run Step 3 source onboarding and candidate modeling.",
    )
    onboard.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Directory containing raw CSV/XLSX files.",
    )
    onboard.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3_modeling"),
        help="Directory for Step 3 generated outputs.",
    )
    onboard.add_argument(
        "--config",
        type=Path,
        default=Path("config/data_model"),
        help="Directory for data-model review files.",
    )

    review = subparsers.add_parser(
        "human-review",
        help="Run Step 3B human review preparation.",
    )
    review.add_argument(
        "--step3-dir",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3_modeling"),
        help="Directory containing Step 3 candidate CSVs.",
    )
    review.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3b_human_review"),
        help="Directory for Step 3B human review outputs.",
    )
    review.add_argument(
        "--config",
        type=Path,
        default=Path("config/data_model"),
        help="Directory for data-model review files.",
    )

    apply_approvals = subparsers.add_parser(
        "apply-approvals",
        help="Validate a human approval template. This command does not modify approved files yet.",
    )
    apply_approvals.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Human approval template YAML.",
    )

    serial_rules = subparsers.add_parser(
        "serial-rules",
        help="Run Step 3C serial reference rule mapping.",
    )
    serial_rules.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to originaldatabase/Serials.xlsx.",
    )
    serial_rules.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Directory containing raw source exports to validate. Defaults to the input file parent.",
    )
    serial_rules.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3c_serial_reference_rules"),
        help="Directory for Step 3C generated outputs.",
    )
    serial_rules.add_argument(
        "--config",
        type=Path,
        default=Path("config/data_model"),
        help="Directory for generated serial rule configs.",
    )
    serial_rules.add_argument(
        "--step3-dir",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3_modeling"),
        help="Directory containing Step 3 key candidates.",
    )

    serial_review = subparsers.add_parser(
        "serial-aware-review",
        help="Run Step 3D serial-aware approval preparation.",
    )
    serial_review.add_argument(
        "--step3-dir",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3_modeling"),
        help="Directory containing Step 3 candidate CSVs.",
    )
    serial_review.add_argument(
        "--step3c-dir",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3c_serial_reference_rules"),
        help="Directory containing Step 3C serial validation outputs.",
    )
    serial_review.add_argument(
        "--config",
        type=Path,
        default=Path("config/data_model"),
        help="Directory containing semantic ref mapping and approval templates.",
    )
    serial_review.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3d_serial_aware_review"),
        help="Directory for Step 3D generated outputs.",
    )
    serial_review.add_argument(
        "--data-dir",
        type=Path,
        default=Path("originaldatabase"),
        help="Directory containing raw source exports for conflict metadata only.",
    )

    approval_sheet = subparsers.add_parser(
        "approval-spreadsheet",
        help="Run Step 3E human approval spreadsheet generation.",
    )
    approval_sheet.add_argument(
        "--step3d-dir",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3d_serial_aware_review"),
        help="Directory containing Step 3D serial-aware review outputs.",
    )
    approval_sheet.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e_human_approval_spreadsheet"),
        help="Directory for Step 3E spreadsheet outputs.",
    )
    approval_sheet.add_argument(
        "--config",
        type=Path,
        default=Path("config/data_model"),
        help="Data model config directory. Approved files are not modified.",
    )

    canonical_model = subparsers.add_parser(
        "canonical-model",
        help="Run Step 3E.1 canonical model alignment and Product reference validation.",
    )
    canonical_model.add_argument(
        "--data-dir",
        type=Path,
        default=Path("originaldatabase"),
        help="Directory containing raw source exports. Files are read only.",
    )
    canonical_model.add_argument(
        "--config",
        type=Path,
        default=Path("config/data_model"),
        help="Directory for canonical model config outputs. Approved files are not modified.",
    )
    canonical_model.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e_human_approval_spreadsheet"),
        help="Directory for Step 3E.1 generated review reports.",
    )
