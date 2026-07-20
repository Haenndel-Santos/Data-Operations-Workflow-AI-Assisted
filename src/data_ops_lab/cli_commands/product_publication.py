from __future__ import annotations

import argparse
from pathlib import Path


def register_product_publication_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register Product materialization, canonical promotion, and repair commands."""

    product_materialization = subparsers.add_parser(
        "product-materialization-preview",
        help="Build a read-only Product preview from applied reconciliation state, or report blockers.",
    )
    product_materialization.add_argument(
        "--data-dir",
        type=Path,
        default=Path("originaldatabase"),
        help="Directory containing read-only Product.xlsx and Product_ref.nr.xlsx sources.",
    )
    product_materialization.add_argument(
        "--workbook",
        type=Path,
        required=True,
        help="Validated Product final review workbook used by the applied state.",
    )
    product_materialization.add_argument(
        "--state",
        type=Path,
        default=Path("config/data_model/product_reconciliation_state.yml"),
        help="Applied Product reconciliation state.",
    )
    product_materialization.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e5_product_materialization"),
        help="New or byte-identical output directory for local preview artifacts.",
    )

    product_canonical_promotion = subparsers.add_parser(
        "product-canonical-promotion-plan",
        help="Validate Step 3E.5 artifacts and build a dry-run canonical Product promotion plan.",
    )
    product_canonical_promotion.add_argument(
        "--materialization",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e5_product_materialization"),
        help="Directory containing the complete Step 3E.5 materialization package.",
    )
    product_canonical_promotion.add_argument(
        "--state",
        type=Path,
        default=Path("config/data_model/product_reconciliation_state.yml"),
        help="Applied Product reconciliation state bound to the materialization package.",
    )
    product_canonical_promotion.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e6_product_canonical_promotion"),
        help="New or byte-identical output directory for the dry-run promotion plan.",
    )

    product_refnr_missing_notes_fix = subparsers.add_parser(
        "product-refnr-missing-notes-fix",
        help="Generate auxiliary spreadsheet for Product final review rows missing final_human_notes.",
    )
    product_refnr_missing_notes_fix.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e_human_approval_spreadsheet"),
        help="Directory containing Product final review validation files and receiving fix outputs.",
    )
    product_refnr_missing_notes_fix.add_argument(
        "--workbook",
        type=Path,
        default=None,
        help="Optional path to product_refnr_final_review_required.xlsx. The workbook is read only.",
    )
    product_refnr_missing_notes_fix.add_argument(
        "--validation-report",
        type=Path,
        default=None,
        help="Optional path to product_refnr_final_review_validation_report.md.",
    )
    product_refnr_missing_notes_fix.add_argument(
        "--validation-summary",
        type=Path,
        default=None,
        help="Optional path to product_refnr_final_review_validation_summary.csv.",
    )
