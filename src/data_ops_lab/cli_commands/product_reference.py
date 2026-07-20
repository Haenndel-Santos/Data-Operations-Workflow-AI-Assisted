from __future__ import annotations

import argparse
from pathlib import Path


def register_product_reference_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register Product reference audit, review, validation, and apply commands."""

    product_audit = subparsers.add_parser(
        "product-reference-audit",
        help="Run focused Product part_nr_sku duplicate and empty-reference audit.",
    )
    product_audit.add_argument(
        "--data-dir",
        type=Path,
        default=Path("originaldatabase"),
        help="Directory containing Product.xlsx. Files are read only.",
    )
    product_audit.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e_human_approval_spreadsheet"),
        help="Directory for Product duplicate audit report.",
    )

    product_review_sheet = subparsers.add_parser(
        "product-reference-review-spreadsheet",
        help="Generate an internal Product reference human review workbook with raw part_nr_sku values.",
    )
    product_review_sheet.add_argument(
        "--data-dir",
        type=Path,
        default=Path("originaldatabase"),
        help="Directory containing Product.xlsx. Files are read only.",
    )
    product_review_sheet.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e_human_approval_spreadsheet"),
        help="Directory for Product human review workbook.",
    )

    product_final_decision = subparsers.add_parser(
        "product-reference-final-decision",
        help="Consolidate completed Product human review workbook decisions into a final Markdown report.",
    )
    product_final_decision.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e_human_approval_spreadsheet"),
        help="Directory containing Product human review workbook and final report output.",
    )
    product_final_decision.add_argument(
        "--workbook",
        type=Path,
        default=None,
        help="Optional path to product_reference_human_review.xlsx. The workbook is read only.",
    )

    product_refnr_reconciliation = subparsers.add_parser(
        "product-refnr-reconciliation",
        help="Reconcile Product.xlsx against Product_ref.nr correction/enrichment source.",
    )
    product_refnr_reconciliation.add_argument(
        "--db-dir",
        type=Path,
        default=Path("db"),
        help="Directory expected to contain Product_ref.nr. Falls back to originaldatabase when needed.",
    )
    product_refnr_reconciliation.add_argument(
        "--data-dir",
        type=Path,
        default=Path("originaldatabase"),
        help="Directory containing Product.xlsx and fallback Product_ref.nr location.",
    )
    product_refnr_reconciliation.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e_human_approval_spreadsheet"),
        help="Directory for Product ref.nr reconciliation outputs.",
    )

    product_refnr_human_review = subparsers.add_parser(
        "product-refnr-human-review",
        help="Generate Product ref.nr reconciliation exception shortlist for human review.",
    )
    product_refnr_human_review.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e_human_approval_spreadsheet"),
        help="Directory containing reconciliation workbook and receiving shortlist outputs.",
    )
    product_refnr_human_review.add_argument(
        "--workbook",
        type=Path,
        default=None,
        help="Optional path to product_refnr_reconciliation_review.xlsx. The workbook is read only.",
    )

    product_refnr_decision_validation = subparsers.add_parser(
        "validate-product-refnr-decisions",
        help="Validate completed Product ref.nr human review decisions without applying them.",
    )
    product_refnr_decision_validation.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e_human_approval_spreadsheet"),
        help="Directory containing Product ref.nr human review shortlist and validation outputs.",
    )
    product_refnr_decision_validation.add_argument(
        "--workbook",
        type=Path,
        default=None,
        help="Optional path to product_refnr_human_review_shortlist.xlsx. The workbook is read only.",
    )

    product_refnr_final_review = subparsers.add_parser(
        "product-refnr-final-review-spreadsheet",
        help="Generate Product final review spreadsheet containing only blocking Product RefNr issues.",
    )
    product_refnr_final_review.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e_human_approval_spreadsheet"),
        help="Directory containing Product ref.nr shortlist and receiving final review spreadsheet outputs.",
    )
    product_refnr_final_review.add_argument(
        "--workbook",
        type=Path,
        default=None,
        help="Optional path to product_refnr_human_review_shortlist.xlsx. The workbook is read only.",
    )

    product_refnr_final_review_validation = subparsers.add_parser(
        "validate-product-refnr-final-review",
        help="Validate completed Product final review decisions without applying them.",
    )
    product_refnr_final_review_validation.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e_human_approval_spreadsheet"),
        help="Directory containing Product final review workbook and validation outputs.",
    )
    product_refnr_final_review_validation.add_argument(
        "--workbook",
        type=Path,
        default=None,
        help="Optional path to product_refnr_final_review_required.xlsx. The workbook is read only.",
    )

    product_refnr_application = subparsers.add_parser(
        "apply-product-refnr-decisions",
        help="Build or explicitly apply the validated Product reconciliation decision state.",
    )
    product_refnr_application.add_argument(
        "--workbook",
        type=Path,
        required=True,
        help="Validated Product final review workbook. The workbook is read only and revalidated.",
    )
    product_refnr_application.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/step3e4_product_application"),
        help="Directory for the application plan and audit report.",
    )
    product_refnr_application.add_argument(
        "--config",
        type=Path,
        default=Path("config/data_model"),
        help="Data model config directory containing the Product reconciliation state.",
    )
    product_refnr_application.add_argument(
        "--apply",
        action="store_true",
        help="Write product_reconciliation_state.yml. Without this flag, only a dry-run is performed.",
    )
    product_refnr_application.add_argument(
        "--replace-existing",
        action="store_true",
        help="Replace a different existing state after preserving a history copy. Requires --apply.",
    )
