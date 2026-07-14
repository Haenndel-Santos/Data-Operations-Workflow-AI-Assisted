from __future__ import annotations

import csv
import io
import re
import uuid
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from openpyxl import load_workbook

from .product_reference_audit import PD_PATTERN, clean_value, product_dataframe
from .product_refnr_application import (
    build_state,
    application_rows,
    decision_digest,
    read_existing_state,
)
from .product_refnr_final_review_validation import consolidated_rows, validate_final_rows
from .product_refnr_reconciliation import (
    detect_columns,
    locate_product_refnr_file,
    read_product_refnr,
    reconcile,
)
from .source_onboarding import ensure_dir, file_sha256


PREVIEW_NAME = "product_materialization_preview.csv"
LINEAGE_NAME = "product_materialization_lineage.csv"
EXCLUSIONS_NAME = "product_materialization_exclusions.csv"
BLOCKERS_NAME = "product_materialization_blockers.csv"
MANIFEST_NAME = "product_materialization_manifest.yml"
REPORT_NAME = "product_materialization_report.md"
OUTPUT_NAMES = {
    PREVIEW_NAME,
    LINEAGE_NAME,
    EXCLUSIONS_NAME,
    BLOCKERS_NAME,
    MANIFEST_NAME,
    REPORT_NAME,
}

SOURCE_IDENTIFIER = re.compile(r"^(original|refnr)_row_(\d+)$")
SUPPORTED_RETAIN_ACTION = "apply_corrected_product_ref_nr"
EXCLUDE_ACTION = "exclude_from_target_product_model"
ID_SCHEME = "uuid5-url-v1-state-and-source-snapshot"


@dataclass(frozen=True)
class ProductMaterializationResult:
    output_dir: Path
    status: str
    report_path: Path
    manifest_path: Path
    blockers_path: Path
    preview_path: Path | None
    lineage_path: Path | None
    exclusions_path: Path | None
    original_rows: int
    product_refnr_rows: int
    target_rows: int
    excluded_identifiers: int
    blocker_count: int
    outputs_changed: bool


def csv_content(rows: list[dict[str, Any]], columns: list[str]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows({column: row.get(column, "") for column in columns} for row in rows)
    return buffer.getvalue()


def source_identifier_parts(identifier: str) -> tuple[str, int] | None:
    match = SOURCE_IDENTIFIER.fullmatch(identifier)
    if not match:
        return None
    return match.group(1), int(match.group(2))


def technical_product_id(
    decision_digest_value: str,
    product_hash: str,
    product_refnr_hash: str,
    source_type: str,
    source_row_number: int,
) -> str:
    identity = "/".join(
        [
            "data-ops-lab",
            "product",
            "v1",
            decision_digest_value,
            product_hash,
            product_refnr_hash,
            source_type,
            str(source_row_number),
        ]
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, identity))


def load_applied_decisions(workbook_path: Path, state_path: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]], dict[str, Any]]:
    if not workbook_path.exists():
        raise FileNotFoundError(f"Validated Product review workbook not found: {workbook_path}")
    if not state_path.exists():
        raise FileNotFoundError(f"Applied Product reconciliation state not found: {state_path}")

    workbook = load_workbook(workbook_path, data_only=True, read_only=True)
    try:
        review_rows = consolidated_rows(workbook)
    finally:
        workbook.close()

    validation = validate_final_rows(review_rows)
    if not validation["ready_for_apply"]:
        raise ValueError("Product review workbook no longer passes final validation.")
    plan_rows = application_rows(review_rows)
    digest = decision_digest(plan_rows)
    expected_state = build_state(workbook_path, plan_rows, digest)
    applied_state = read_existing_state(state_path)
    if applied_state != expected_state:
        raise ValueError("Applied Product state does not exactly match the supplied validated workbook.")
    return review_rows, plan_rows, applied_state


def decision_groups(
    review_rows: list[dict[str, Any]],
    plan_rows: list[dict[str, str]],
) -> tuple[dict[str, list[dict[str, str]]], list[dict[str, str]]]:
    review_by_id = {clean_value(row.get("review_id", "")): row for row in review_rows}
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    blockers = []
    for plan in plan_rows:
        review = review_by_id.get(plan["review_id"], {})
        original_identifier = clean_value(review.get("product_original_identifier", ""))
        refnr_identifier = clean_value(review.get("product_refnr_identifier", ""))
        identifiers = [value for value in (original_identifier, refnr_identifier) if value]
        if len(identifiers) != 1:
            blockers.append(
                {
                    "issue_ids": plan["issue_id"],
                    "source_identifier": ";".join(identifiers),
                    "blocker_type": "invalid_source_identifier_count",
                    "explanation": "Each applied decision must identify exactly one original or Product_ref.nr source row.",
                }
            )
            continue
        groups[identifiers[0]].append(plan)
    return groups, blockers


def group_issue_ids(groups: dict[str, list[dict[str, str]]], identifier: str) -> str:
    return ";".join(sorted({row["issue_id"] for row in groups.get(identifier, [])}))


def group_actions(groups: dict[str, list[dict[str, str]]], identifier: str) -> set[str]:
    return {row["action"] for row in groups.get(identifier, [])}


def add_blocker(
    blockers: list[dict[str, str]],
    blocker_type: str,
    explanation: str,
    *,
    source_identifier: str = "",
    issue_ids: str = "",
) -> None:
    blockers.append(
        {
            "issue_ids": issue_ids,
            "source_identifier": source_identifier,
            "blocker_type": blocker_type,
            "explanation": explanation,
        }
    )


def source_attributes(row: Any, columns: list[str]) -> dict[str, str]:
    return {column: clean_value(row.get(column, "")) for column in columns}


def exact_common_source_match(original_row: Any, refnr_row: Any, common_columns: list[str]) -> bool:
    return all(
        clean_value(original_row.get(column, "")).casefold()
        == clean_value(refnr_row.get(column, "")).casefold()
        for column in common_columns
    )


def build_product_row(
    attributes: dict[str, str],
    product_ref_nr: str,
    product_id: str,
    business_columns: list[str],
) -> dict[str, str]:
    return {
        "product_id": product_id,
        "product_ref_nr": product_ref_nr,
        "pd_ref_nr": product_ref_nr if PD_PATTERN.match(product_ref_nr) else "",
        **{column: attributes.get(column, "") for column in business_columns},
    }


def normalize_blockers(blockers: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized = []
    seen = set()
    for blocker in blockers:
        key = (
            blocker.get("issue_ids", ""),
            blocker.get("source_identifier", ""),
            blocker["blocker_type"],
            blocker["explanation"],
        )
        if key in seen:
            continue
        seen.add(key)
        normalized.append(
            {
                "blocker_id": f"BLOCKER_{len(normalized) + 1:03d}",
                "issue_ids": key[0],
                "source_identifier": key[1],
                "blocker_type": key[2],
                "explanation": key[3],
            }
        )
    return normalized


def build_materialization(
    original_df: Any,
    refnr_df: Any,
    review_rows: list[dict[str, Any]],
    plan_rows: list[dict[str, str]],
    applied_state: dict[str, Any],
    product_hash: str,
    product_refnr_hash: str,
) -> dict[str, Any]:
    groups, blockers = decision_groups(review_rows, plan_rows)
    excluded = {
        identifier
        for identifier in groups
        if EXCLUDE_ACTION in group_actions(groups, identifier)
    }
    represented_identifiers: set[str] = set()
    exclusions = []
    invalid_identifiers: set[str] = set()

    for identifier in sorted(groups):
        parts = source_identifier_parts(identifier)
        if parts is None:
            invalid_identifiers.add(identifier)
            add_blocker(
                blockers,
                "invalid_source_identifier",
                "The source identifier does not match original_row_N or refnr_row_N.",
                source_identifier=identifier,
                issue_ids=group_issue_ids(groups, identifier),
            )
            continue
        source_type, source_row = parts
        source_row_count = len(original_df) if source_type == "original" else len(refnr_df)
        if source_row < 2 or source_row > source_row_count + 1:
            invalid_identifiers.add(identifier)
            add_blocker(
                blockers,
                "source_identifier_out_of_range",
                "The reviewed source row is outside the current source-file range.",
                source_identifier=identifier,
                issue_ids=group_issue_ids(groups, identifier),
            )

    for identifier in sorted(excluded):
        if identifier in invalid_identifiers:
            continue
        parts = source_identifier_parts(identifier)
        assert parts is not None
        source_type, source_row = parts
        exclusions.append(
            {
                "source_identifier": identifier,
                "source_type": source_type,
                "source_row_number": source_row,
                "issue_ids": group_issue_ids(groups, identifier),
                "reason": EXCLUDE_ACTION,
            }
        )

    for identifier in sorted(set(groups) - excluded - invalid_identifiers):
        actions = group_actions(groups, identifier)
        if actions != {SUPPORTED_RETAIN_ACTION}:
            add_blocker(
                blockers,
                "unsupported_materialization_action",
                "Materialization v1 only supports corrected-reference retention or target-model exclusion.",
                source_identifier=identifier,
                issue_ids=group_issue_ids(groups, identifier),
            )

    reconciliation = reconcile(original_df, refnr_df)
    matched_by_original = {
        int(row["original_source_row_number"]): row
        for row in reconciliation["matched_products"]
    }
    refnr_columns = detect_columns(refnr_df)
    ref_column = refnr_columns["product_ref_nr"]
    if not ref_column:
        add_blocker(
            blockers,
            "missing_product_ref_nr_column",
            "Product_ref.nr source does not expose a corrected reference column.",
        )

    business_columns = list(original_df.columns)
    common_columns = [column for column in business_columns if column in refnr_df.columns]
    digest = applied_state["source"]["decision_digest"]
    products = []
    lineage = []
    consumed_refnr_rows: set[int] = set()

    for original_index, original_row in original_df.iterrows():
        original_source_row = int(original_index) + 2
        original_identifier = f"original_row_{original_source_row}"
        if original_identifier in excluded:
            continue

        corrected_ref = ""
        refnr_source_row: int | None = None
        action = "matched_authoritative_correction"
        issue_ids = group_issue_ids(groups, original_identifier)
        matched = matched_by_original.get(original_source_row)
        if matched:
            corrected_ref = clean_value(matched.get("corrected_ref_nr", ""))
            refnr_source_row = int(matched["refnr_source_row_number"])
            refnr_identifier = f"refnr_row_{refnr_source_row}"
            if refnr_identifier in excluded:
                add_blocker(
                    blockers,
                    "retained_product_uses_rejected_reference_row",
                    "A retained original Product row resolves through an explicitly rejected Product_ref.nr row.",
                    source_identifier=original_identifier,
                    issue_ids=issue_ids,
                )
                continue
        elif SUPPORTED_RETAIN_ACTION in group_actions(groups, original_identifier):
            action = "approved_same_row_conflict_resolution"
            refnr_source_row = original_source_row
            refnr_identifier = f"refnr_row_{refnr_source_row}"
            if refnr_identifier in excluded:
                add_blocker(
                    blockers,
                    "approved_conflict_reference_rejected",
                    "The same-row authoritative record required by the approved conflict is rejected.",
                    source_identifier=original_identifier,
                    issue_ids=issue_ids,
                )
                continue
            refnr_index = refnr_source_row - 2
            if refnr_index not in refnr_df.index:
                add_blocker(
                    blockers,
                    "approved_conflict_reference_row_missing",
                    "The approved same-row Product_ref.nr evidence is outside the current source range.",
                    source_identifier=original_identifier,
                    issue_ids=issue_ids,
                )
                continue
            refnr_row = refnr_df.loc[refnr_index]
            if not exact_common_source_match(original_row, refnr_row, common_columns):
                add_blocker(
                    blockers,
                    "approved_conflict_alignment_changed",
                    "Original Product and same-row Product_ref.nr attributes no longer match exactly.",
                    source_identifier=original_identifier,
                    issue_ids=issue_ids,
                )
                continue
            corrected_ref = clean_value(refnr_row.get(ref_column, "")) if ref_column else ""
            represented_identifiers.add(refnr_identifier)
            issue_ids = ";".join(
                value
                for value in (issue_ids, group_issue_ids(groups, refnr_identifier))
                if value
            )
        else:
            add_blocker(
                blockers,
                "retained_original_product_unresolved",
                "A retained original Product row has no authoritative match or applicable approved exception.",
                source_identifier=original_identifier,
                issue_ids=issue_ids,
            )
            continue

        if not corrected_ref:
            add_blocker(
                blockers,
                "approved_corrected_reference_missing",
                "A retained Product row has no corrected product_ref_nr in the authoritative source.",
                source_identifier=original_identifier,
                issue_ids=issue_ids,
            )
            continue

        consumed_refnr_rows.add(refnr_source_row)
        represented_identifiers.add(original_identifier)
        attributes = source_attributes(original_row, business_columns)
        product_id = technical_product_id(
            digest,
            product_hash,
            product_refnr_hash,
            "original",
            original_source_row,
        )
        products.append(build_product_row(attributes, corrected_ref, product_id, business_columns))
        lineage.append(
            {
                "product_id": product_id,
                "source_type": "original_product",
                "original_source_row_number": original_source_row,
                "product_refnr_source_row_number": refnr_source_row,
                "materialization_action": action,
                "decision_issue_ids": issue_ids,
            }
        )

    for unmatched in reconciliation["unmatched_product_refnr"]:
        refnr_source_row = int(unmatched["refnr_source_row_number"])
        refnr_identifier = f"refnr_row_{refnr_source_row}"
        if refnr_identifier in excluded or refnr_source_row in consumed_refnr_rows:
            continue
        issue_ids = group_issue_ids(groups, refnr_identifier)
        if SUPPORTED_RETAIN_ACTION not in group_actions(groups, refnr_identifier):
            add_blocker(
                blockers,
                "unmatched_product_refnr_without_supported_decision",
                "An unmatched Product_ref.nr row is neither rejected nor approved for corrected-reference use.",
                source_identifier=refnr_identifier,
                issue_ids=issue_ids,
            )
            continue
        refnr_index = refnr_source_row - 2
        if refnr_index not in refnr_df.index:
            add_blocker(
                blockers,
                "approved_product_refnr_row_missing",
                "The approved Product_ref.nr row is outside the current source range.",
                source_identifier=refnr_identifier,
                issue_ids=issue_ids,
            )
            continue
        refnr_row = refnr_df.loc[refnr_index]
        filled_fields = [column for column in refnr_df.columns if clean_value(refnr_row.get(column, ""))]
        corrected_ref = clean_value(refnr_row.get(ref_column, "")) if ref_column else ""
        if not filled_fields:
            add_blocker(
                blockers,
                "approved_authoritative_row_empty",
                "The approved Product_ref.nr source row is completely empty and cannot define a Product.",
                source_identifier=refnr_identifier,
                issue_ids=issue_ids,
            )
            continue
        if not corrected_ref:
            add_blocker(
                blockers,
                "approved_corrected_reference_missing",
                "The approved Product_ref.nr source row has no corrected product_ref_nr.",
                source_identifier=refnr_identifier,
                issue_ids=issue_ids,
            )
            continue

        represented_identifiers.add(refnr_identifier)
        attributes = source_attributes(refnr_row, business_columns)
        product_id = technical_product_id(
            digest,
            product_hash,
            product_refnr_hash,
            "refnr",
            refnr_source_row,
        )
        products.append(build_product_row(attributes, corrected_ref, product_id, business_columns))
        lineage.append(
            {
                "product_id": product_id,
                "source_type": "product_refnr_only",
                "original_source_row_number": "",
                "product_refnr_source_row_number": refnr_source_row,
                "materialization_action": "approved_product_refnr_only",
                "decision_issue_ids": issue_ids,
            }
        )

    for identifier in sorted(set(groups) - excluded - represented_identifiers):
        if any(
            blocker.get("source_identifier") == identifier
            for blocker in blockers
        ):
            continue
        add_blocker(
            blockers,
            "approved_decision_not_materialized",
            "An approved decision did not map to a retained Product or consumed authoritative source row.",
            source_identifier=identifier,
            issue_ids=group_issue_ids(groups, identifier),
        )

    normalized_blockers = normalize_blockers(blockers)
    product_ids = [row["product_id"] for row in products]
    if len(product_ids) != len(set(product_ids)):
        add_blocker(
            normalized_blockers,
            "duplicate_generated_product_id",
            "Generated Product technical identifiers are not unique.",
        )
        normalized_blockers = normalize_blockers(normalized_blockers)

    return {
        "products": products,
        "lineage": lineage,
        "exclusions": exclusions,
        "blockers": normalized_blockers,
        "business_columns": business_columns,
        "reconciliation_counts": {
            key: len(value)
            for key, value in reconciliation.items()
        },
    }


def duplicate_occurrences(rows: list[dict[str, Any]], column: str) -> int:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        value = clean_value(row.get(column, "")).casefold()
        if value:
            counts[value] += 1
    return sum(count - 1 for count in counts.values() if count > 1)


def render_report(manifest: dict[str, Any], blockers: list[dict[str, str]]) -> str:
    counts = manifest["counts"]
    lines = [
        "# Product Materialization Report",
        "",
        f"- Status: `{manifest['status']}`",
        f"- Decision digest: `{manifest['inputs']['decision_digest']}`",
        f"- Original Product rows: {counts['original_rows']}",
        f"- Product_ref.nr rows: {counts['product_refnr_rows']}",
        f"- Candidate target rows: {counts['candidate_target_rows']}",
        f"- Logical exclusion identifiers: {counts['excluded_identifiers']}",
        f"- Blockers: {counts['blockers']}",
        "",
        "## Validation",
        "",
        f"- Generated product IDs unique: {str(manifest['validation']['product_ids_unique']).lower()}",
        f"- Empty corrected Product references: {manifest['validation']['empty_product_ref_nr']}",
        f"- Duplicate corrected Product references: {manifest['validation']['duplicate_product_ref_nr_occurrences']}",
        f"- Empty part_nr_sku values: {manifest['validation']['empty_part_nr_sku']}",
        "",
        "## Blockers",
        "",
    ]
    if blockers:
        lines.extend(
            f"- `{row['blocker_id']}` `{row['blocker_type']}`: source=`{row['source_identifier'] or 'not_available'}`, issues=`{row['issue_ids'] or 'not_available'}`"
            for row in blockers
        )
        lines.extend(
            [
                "",
                "No Product preview was generated. Human clarification or corrected source evidence is required.",
            ]
        )
    else:
        lines.append("- No materialization blockers found.")
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "- Original Product sources and the approved review workbook were read only.",
            "- Applied reconciliation state was validated and not modified.",
            "- No approved key or relationship file was modified.",
            "- No database, import, migration, synchronization, or external system was used.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_outputs(output_dir: Path, contents: dict[str, str]) -> bool:
    existing_contract_files = {
        path.name: path
        for path in output_dir.iterdir()
        if path.is_file() and path.name in OUTPUT_NAMES
    } if output_dir.exists() else {}
    expected_names = set(contents)
    if existing_contract_files:
        exact = set(existing_contract_files) == expected_names and all(
            existing_contract_files[name].read_text(encoding="utf-8") == contents[name]
            for name in expected_names
        )
        if exact:
            return False
        raise ValueError(
            f"Different Product materialization outputs already exist in {output_dir}. "
            "Use a new output directory; existing generated evidence was not overwritten."
        )
    ensure_dir(output_dir)
    for name, content in contents.items():
        (output_dir / name).write_text(content, encoding="utf-8", newline="")
    return True


def run_product_materialization(
    data_dir: Path,
    workbook_path: Path,
    state_path: Path,
    output_dir: Path,
) -> ProductMaterializationResult:
    review_rows, plan_rows, applied_state = load_applied_decisions(workbook_path, state_path)
    product_path = data_dir / "Product.xlsx"
    if not product_path.exists():
        raise FileNotFoundError(f"Original Product source not found: {product_path}")
    refnr_path = locate_product_refnr_file(data_dir, data_dir)
    original_df = product_dataframe(data_dir)
    refnr_df, _ = read_product_refnr(refnr_path)
    product_hash = file_sha256(product_path)
    product_refnr_hash = file_sha256(refnr_path)

    materialization = build_materialization(
        original_df,
        refnr_df,
        review_rows,
        plan_rows,
        applied_state,
        product_hash,
        product_refnr_hash,
    )
    products = materialization["products"]
    lineage = materialization["lineage"]
    exclusions = materialization["exclusions"]
    blockers = materialization["blockers"]
    status = "blocked" if blockers else "ready_for_local_preview"
    product_ids = [row["product_id"] for row in products]
    empty_refs = sum(not clean_value(row.get("product_ref_nr", "")) for row in products)
    empty_part_numbers = sum(not clean_value(row.get("part_nr_sku", "")) for row in products)
    manifest = {
        "version": 1,
        "status": status,
        "inputs": {
            "product_sha256": product_hash,
            "product_refnr_sha256": product_refnr_hash,
            "review_workbook_sha256": file_sha256(workbook_path),
            "decision_digest": applied_state["source"]["decision_digest"],
        },
        "contract": {
            "product_id": ID_SCHEME,
            "business_reference": "part_nr_sku",
            "corrected_reference": "product_ref_nr",
            "optional_serial_reference": "pd_ref_nr",
            "exclusion_precedence": True,
            "preview_only": True,
        },
        "counts": {
            "original_rows": len(original_df),
            "product_refnr_rows": len(refnr_df),
            "review_decisions": len(plan_rows),
            "candidate_target_rows": len(products),
            "excluded_identifiers": len(exclusions),
            "blockers": len(blockers),
        },
        "validation": {
            "product_ids_unique": len(product_ids) == len(set(product_ids)),
            "empty_product_ref_nr": empty_refs,
            "duplicate_product_ref_nr_occurrences": duplicate_occurrences(products, "product_ref_nr"),
            "empty_part_nr_sku": empty_part_numbers,
        },
        "reconciliation_counts": materialization["reconciliation_counts"],
        "blockers": blockers,
    }

    contents = {
        BLOCKERS_NAME: csv_content(
            blockers,
            ["blocker_id", "issue_ids", "source_identifier", "blocker_type", "explanation"],
        ),
        MANIFEST_NAME: yaml.safe_dump(manifest, sort_keys=False, allow_unicode=False),
        REPORT_NAME: render_report(manifest, blockers),
    }
    preview_path = None
    lineage_path = None
    exclusions_path = None
    if not blockers:
        preview_columns = ["product_id", "product_ref_nr", "pd_ref_nr", *materialization["business_columns"]]
        contents[PREVIEW_NAME] = csv_content(products, preview_columns)
        contents[LINEAGE_NAME] = csv_content(
            lineage,
            [
                "product_id",
                "source_type",
                "original_source_row_number",
                "product_refnr_source_row_number",
                "materialization_action",
                "decision_issue_ids",
            ],
        )
        contents[EXCLUSIONS_NAME] = csv_content(
            exclusions,
            ["source_identifier", "source_type", "source_row_number", "issue_ids", "reason"],
        )
        preview_path = output_dir / PREVIEW_NAME
        lineage_path = output_dir / LINEAGE_NAME
        exclusions_path = output_dir / EXCLUSIONS_NAME

    outputs_changed = write_outputs(output_dir, contents)
    return ProductMaterializationResult(
        output_dir=output_dir,
        status=status,
        report_path=output_dir / REPORT_NAME,
        manifest_path=output_dir / MANIFEST_NAME,
        blockers_path=output_dir / BLOCKERS_NAME,
        preview_path=preview_path,
        lineage_path=lineage_path,
        exclusions_path=exclusions_path,
        original_rows=len(original_df),
        product_refnr_rows=len(refnr_df),
        target_rows=len(products) if not blockers else 0,
        excluded_identifiers=len(exclusions),
        blocker_count=len(blockers),
        outputs_changed=outputs_changed,
    )
