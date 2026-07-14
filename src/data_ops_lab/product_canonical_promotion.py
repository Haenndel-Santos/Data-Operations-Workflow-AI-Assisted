from __future__ import annotations

import csv
import io
import uuid
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .product_materialization import (
    BLOCKERS_NAME as MATERIALIZATION_BLOCKERS_NAME,
    EXCLUSIONS_NAME as MATERIALIZATION_EXCLUSIONS_NAME,
    LINEAGE_NAME as MATERIALIZATION_LINEAGE_NAME,
    MANIFEST_NAME as MATERIALIZATION_MANIFEST_NAME,
    PREVIEW_NAME as MATERIALIZATION_PREVIEW_NAME,
    REPORT_NAME as MATERIALIZATION_REPORT_NAME,
)
from .product_reference_audit import PD_PATTERN, clean_value
from .source_onboarding import ensure_dir, file_sha256


PLAN_NAME = "product_canonical_promotion_plan.yml"
BLOCKERS_NAME = "product_canonical_promotion_blockers.csv"
REPORT_NAME = "product_canonical_promotion_report.md"
OUTPUT_NAMES = {PLAN_NAME, BLOCKERS_NAME, REPORT_NAME}
MATERIALIZATION_NAMES = (
    MATERIALIZATION_PREVIEW_NAME,
    MATERIALIZATION_LINEAGE_NAME,
    MATERIALIZATION_EXCLUSIONS_NAME,
    MATERIALIZATION_BLOCKERS_NAME,
    MATERIALIZATION_MANIFEST_NAME,
    MATERIALIZATION_REPORT_NAME,
)
REQUIRED_PREVIEW_COLUMNS = ("product_id", "product_ref_nr", "pd_ref_nr", "part_nr_sku")
EXPECTED_MODEL_CONTRACT = {
    "table": "product",
    "primary_key": "product_id",
    "primary_key_strategy": "generated_technical",
    "business_reference": "part_nr_sku",
    "corrected_reference": "product_ref_nr",
    "optional_serial_reference": "pd_ref_nr",
    "rejected_action": "exclude_from_target_product_model",
}


@dataclass(frozen=True)
class ProductCanonicalPromotionResult:
    output_dir: Path
    status: str
    plan_path: Path
    blockers_path: Path
    report_path: Path
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


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def add_blocker(
    blockers: list[dict[str, str]],
    blocker_type: str,
    explanation: str,
    *,
    artifact: str = "",
) -> None:
    blockers.append(
        {
            "blocker_id": f"BLOCKER_{len(blockers) + 1:03d}",
            "blocker_type": blocker_type,
            "artifact": artifact,
            "explanation": explanation,
        }
    )


def read_yaml_mapping(
    path: Path,
    blockers: list[dict[str, str]],
    artifact: str,
) -> dict[str, Any]:
    if not path.is_file():
        add_blocker(
            blockers,
            "required_artifact_missing",
            "A required Step 3E.6 input artifact is missing.",
            artifact=artifact,
        )
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        add_blocker(
            blockers,
            "invalid_yaml",
            "The input artifact is not valid YAML.",
            artifact=artifact,
        )
        return {}
    if not isinstance(payload, dict):
        add_blocker(
            blockers,
            "invalid_yaml_mapping",
            "The input artifact must contain a YAML mapping.",
            artifact=artifact,
        )
        return {}
    return payload


def duplicate_occurrences(values: list[str]) -> int:
    counts = Counter(value.casefold() for value in values if value)
    return sum(count - 1 for count in counts.values() if count > 1)


def valid_uuid5(value: str) -> bool:
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        return False
    return parsed.version == 5 and str(parsed) == value.lower()


def integer_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def compare_manifest_count(
    blockers: list[dict[str, str]],
    manifest: dict[str, Any],
    key: str,
    actual: int,
) -> None:
    counts = manifest.get("counts")
    expected = integer_value(counts.get(key)) if isinstance(counts, dict) else None
    if expected != actual:
        add_blocker(
            blockers,
            "manifest_count_mismatch",
            f"Manifest count {key} does not match the current materialization artifact.",
            artifact=MATERIALIZATION_MANIFEST_NAME,
        )


def lineage_source_identifiers(rows: list[dict[str, str]]) -> set[str]:
    identifiers = set()
    for row in rows:
        original_row = clean_value(row.get("original_source_row_number", ""))
        refnr_row = clean_value(row.get("product_refnr_source_row_number", ""))
        if original_row:
            identifiers.add(f"original_row_{original_row}")
        if refnr_row:
            identifiers.add(f"refnr_row_{refnr_row}")
    return identifiers


def build_promotion_plan(
    materialization_dir: Path,
    state_path: Path,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    blockers: list[dict[str, str]] = []
    artifact_paths = {name: materialization_dir / name for name in MATERIALIZATION_NAMES}
    for name, path in artifact_paths.items():
        if not path.is_file() and name != MATERIALIZATION_MANIFEST_NAME:
            add_blocker(
                blockers,
                "required_artifact_missing",
                "The complete Step 3E.5 materialization package is required.",
                artifact=name,
            )

    state = read_yaml_mapping(state_path, blockers, state_path.name)
    manifest = read_yaml_mapping(
        artifact_paths[MATERIALIZATION_MANIFEST_NAME],
        blockers,
        MATERIALIZATION_MANIFEST_NAME,
    )

    state_source = state.get("source", {}) if isinstance(state.get("source"), dict) else {}
    state_contract = (
        state.get("model_contract", {}) if isinstance(state.get("model_contract"), dict) else {}
    )
    manifest_inputs = (
        manifest.get("inputs", {}) if isinstance(manifest.get("inputs"), dict) else {}
    )
    manifest_contract = (
        manifest.get("contract", {}) if isinstance(manifest.get("contract"), dict) else {}
    )
    decision_digest = clean_value(state_source.get("decision_digest", ""))

    if state.get("status") != "applied":
        add_blocker(
            blockers,
            "product_state_not_applied",
            "Product reconciliation state must be applied before canonical promotion review.",
            artifact=state_path.name,
        )
    for key, expected in EXPECTED_MODEL_CONTRACT.items():
        if state_contract.get(key) != expected:
            add_blocker(
                blockers,
                "product_model_contract_mismatch",
                f"Applied Product model contract field {key} does not match Step 3E.6.",
                artifact=state_path.name,
            )
    if manifest.get("status") != "ready_for_local_preview":
        add_blocker(
            blockers,
            "materialization_not_ready",
            "Step 3E.5 must be ready_for_local_preview before canonical promotion review.",
            artifact=MATERIALIZATION_MANIFEST_NAME,
        )
    if manifest_contract.get("preview_only") is not True:
        add_blocker(
            blockers,
            "materialization_contract_mismatch",
            "Step 3E.5 manifest must identify the input as preview-only materialization evidence.",
            artifact=MATERIALIZATION_MANIFEST_NAME,
        )
    if not decision_digest or clean_value(manifest_inputs.get("decision_digest", "")) != decision_digest:
        add_blocker(
            blockers,
            "decision_digest_mismatch",
            "Applied Product state and materialization manifest do not share the same decision digest.",
            artifact=MATERIALIZATION_MANIFEST_NAME,
        )
    if clean_value(state_source.get("workbook_sha256", "")) != clean_value(
        manifest_inputs.get("review_workbook_sha256", "")
    ):
        add_blocker(
            blockers,
            "review_workbook_hash_mismatch",
            "Applied Product state and materialization manifest do not identify the same review workbook.",
            artifact=MATERIALIZATION_MANIFEST_NAME,
        )

    preview_headers: list[str] = []
    preview: list[dict[str, str]] = []
    lineage: list[dict[str, str]] = []
    exclusions: list[dict[str, str]] = []
    materialization_blockers: list[dict[str, str]] = []
    csv_inputs = (
        (MATERIALIZATION_PREVIEW_NAME, "preview"),
        (MATERIALIZATION_LINEAGE_NAME, "lineage"),
        (MATERIALIZATION_EXCLUSIONS_NAME, "exclusions"),
        (MATERIALIZATION_BLOCKERS_NAME, "blockers"),
    )
    loaded: dict[str, tuple[list[str], list[dict[str, str]]]] = {}
    for name, label in csv_inputs:
        path = artifact_paths[name]
        if not path.is_file():
            continue
        try:
            loaded[label] = read_csv(path)
        except (csv.Error, OSError, UnicodeError):
            add_blocker(
                blockers,
                "invalid_csv",
                "The materialization artifact is not valid UTF-8 CSV.",
                artifact=name,
            )
    preview_headers, preview = loaded.get("preview", ([], []))
    _, lineage = loaded.get("lineage", ([], []))
    _, exclusions = loaded.get("exclusions", ([], []))
    _, materialization_blockers = loaded.get("blockers", ([], []))

    if len(preview_headers) != len(set(preview_headers)):
        add_blocker(
            blockers,
            "duplicate_preview_columns",
            "Product preview contains duplicate column names.",
            artifact=MATERIALIZATION_PREVIEW_NAME,
        )
    for column in REQUIRED_PREVIEW_COLUMNS:
        if column not in preview_headers:
            add_blocker(
                blockers,
                "required_preview_column_missing",
                f"Canonical Product column {column} is missing from the preview.",
                artifact=MATERIALIZATION_PREVIEW_NAME,
            )
    if materialization_blockers:
        add_blocker(
            blockers,
            "materialization_blockers_present",
            "Step 3E.5 blocker evidence is not empty.",
            artifact=MATERIALIZATION_BLOCKERS_NAME,
        )

    product_ids = [clean_value(row.get("product_id", "")) for row in preview]
    product_refs = [clean_value(row.get("product_ref_nr", "")) for row in preview]
    part_numbers = [clean_value(row.get("part_nr_sku", "")) for row in preview]
    lineage_ids = [clean_value(row.get("product_id", "")) for row in lineage]
    exclusion_ids = [clean_value(row.get("source_identifier", "")) for row in exclusions]
    empty_product_ids = sum(not value for value in product_ids)
    duplicate_product_ids = duplicate_occurrences(product_ids)
    invalid_product_ids = sum(bool(value) and not valid_uuid5(value) for value in product_ids)
    empty_product_refs = sum(not value for value in product_refs)
    duplicate_product_refs = duplicate_occurrences(product_refs)
    empty_part_numbers = sum(not value for value in part_numbers)

    checks = (
        (empty_product_ids, "empty_product_id", "Canonical Product technical IDs must be filled."),
        (duplicate_product_ids, "duplicate_product_id", "Canonical Product technical IDs must be unique."),
        (invalid_product_ids, "invalid_product_id", "Canonical Product technical IDs must be normalized UUID5 values."),
        (empty_product_refs, "empty_product_ref_nr", "Canonical corrected Product references must be filled."),
        (duplicate_product_refs, "duplicate_product_ref_nr", "Canonical corrected Product references must be unique."),
    )
    for count, blocker_type, explanation in checks:
        if count:
            add_blocker(
                blockers,
                blocker_type,
                explanation,
                artifact=MATERIALIZATION_PREVIEW_NAME,
            )

    if len(lineage) != len(preview) or Counter(lineage_ids) != Counter(product_ids):
        add_blocker(
            blockers,
            "lineage_product_mismatch",
            "Product lineage must contain exactly one row for every preview product_id.",
            artifact=MATERIALIZATION_LINEAGE_NAME,
        )
    if any(not value for value in exclusion_ids) or len(exclusion_ids) != len(set(exclusion_ids)):
        add_blocker(
            blockers,
            "invalid_exclusion_identifiers",
            "Exclusion identifiers must be filled and unique.",
            artifact=MATERIALIZATION_EXCLUSIONS_NAME,
        )
    if set(exclusion_ids) & lineage_source_identifiers(lineage):
        add_blocker(
            blockers,
            "excluded_identifier_in_lineage",
            "An explicitly excluded source identifier is represented in Product lineage.",
            artifact=MATERIALIZATION_LINEAGE_NAME,
        )

    invalid_pd_refs = 0
    for row in preview:
        product_ref = clean_value(row.get("product_ref_nr", ""))
        pd_ref = clean_value(row.get("pd_ref_nr", ""))
        expected_pd_ref = product_ref if PD_PATTERN.match(product_ref) else ""
        if pd_ref != expected_pd_ref:
            invalid_pd_refs += 1
    if invalid_pd_refs:
        add_blocker(
            blockers,
            "optional_pd_reference_mismatch",
            "pd_ref_nr must equal a PD-formatted product_ref_nr or remain empty.",
            artifact=MATERIALIZATION_PREVIEW_NAME,
        )

    compare_manifest_count(blockers, manifest, "candidate_target_rows", len(preview))
    compare_manifest_count(blockers, manifest, "excluded_identifiers", len(exclusions))
    compare_manifest_count(blockers, manifest, "blockers", len(materialization_blockers))
    manifest_validation = (
        manifest.get("validation", {}) if isinstance(manifest.get("validation"), dict) else {}
    )
    validation_pairs = {
        "product_ids_unique": empty_product_ids == 0 and duplicate_product_ids == 0,
        "empty_product_ref_nr": empty_product_refs,
        "duplicate_product_ref_nr_occurrences": duplicate_product_refs,
        "empty_part_nr_sku": empty_part_numbers,
    }
    for key, actual in validation_pairs.items():
        if manifest_validation.get(key) != actual:
            add_blocker(
                blockers,
                "manifest_validation_mismatch",
                f"Manifest validation {key} does not match the current Product preview.",
                artifact=MATERIALIZATION_MANIFEST_NAME,
            )

    status = "blocked" if blockers else "ready_for_canonical_state_review"
    artifact_hashes = {
        name: file_sha256(path)
        for name, path in artifact_paths.items()
        if path.is_file()
    }
    plan = {
        "version": 1,
        "status": status,
        "source": {
            "decision_digest": decision_digest,
            "applied_state_sha256": file_sha256(state_path) if state_path.is_file() else "",
            "materialization_artifact_sha256": artifact_hashes,
        },
        "target_contract": {
            **EXPECTED_MODEL_CONTRACT,
            "canonical_state": "proposed_local_product_snapshot",
            "core_columns": [
                {"name": "product_id", "role": "technical_primary_key", "nullable": False},
                {"name": "product_ref_nr", "role": "corrected_reference", "nullable": False},
                {"name": "pd_ref_nr", "role": "optional_serial_reference", "nullable": True},
                {"name": "part_nr_sku", "role": "business_reference", "nullable": True},
            ],
            "additional_columns": [
                column for column in preview_headers if column not in REQUIRED_PREVIEW_COLUMNS
            ],
        },
        "counts": {
            "target_rows": len(preview),
            "excluded_identifiers": len(exclusions),
            "columns": len(preview_headers),
            "empty_part_nr_sku": empty_part_numbers,
            "blockers": len(blockers),
        },
        "validation": {
            "product_ids_filled_unique_uuid5": empty_product_ids == 0
            and duplicate_product_ids == 0
            and invalid_product_ids == 0,
            "product_ref_nr_filled_unique": empty_product_refs == 0
            and duplicate_product_refs == 0,
            "lineage_complete": len(lineage) == len(preview)
            and Counter(lineage_ids) == Counter(product_ids),
            "exclusions_absent_from_lineage": not (
                set(exclusion_ids) & lineage_source_identifiers(lineage)
            ),
            "optional_pd_reference_valid": invalid_pd_refs == 0,
        },
        "approval": {
            "canonical_state_applied": False,
            "database_operation_authorized": False,
            "requires_explicit_apply_contract": True,
        },
        "blockers": blockers,
    }
    return plan, blockers


def render_report(plan: dict[str, Any]) -> str:
    counts = plan["counts"]
    lines = [
        "# Product Canonical Promotion Plan Report",
        "",
        f"- Status: `{plan['status']}`",
        f"- Decision digest: `{plan['source']['decision_digest']}`",
        f"- Candidate canonical Product rows: {counts['target_rows']}",
        f"- Excluded identifiers: {counts['excluded_identifiers']}",
        f"- Columns: {counts['columns']}",
        f"- Empty optional business references: {counts['empty_part_nr_sku']}",
        f"- Blockers: {counts['blockers']}",
        "",
        "## Validation",
        "",
    ]
    lines.extend(
        f"- {key}: {str(value).lower()}" for key, value in plan["validation"].items()
    )
    lines.extend(["", "## Blockers", ""])
    if plan["blockers"]:
        lines.extend(
            f"- `{row['blocker_id']}` `{row['blocker_type']}`: artifact=`{row['artifact'] or 'not_available'}`"
            for row in plan["blockers"]
        )
    else:
        lines.append("- No canonical promotion blockers found.")
    lines.extend(
        [
            "",
            "## Approval Boundary",
            "",
            "- This is a dry-run promotion plan, not applied canonical state.",
            "- Product row values remain only in ignored local materialization artifacts.",
            "- `canonical_tables.yml`, approved keys, approved relationships, and raw sources were not modified.",
            "- No database, import, migration, synchronization, or external system was used.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_outputs(output_dir: Path, contents: dict[str, str]) -> bool:
    existing = {
        path.name: path
        for path in output_dir.iterdir()
        if path.is_file() and path.name in OUTPUT_NAMES
    } if output_dir.exists() else {}
    if existing:
        exact = set(existing) == set(contents) and all(
            existing[name].read_text(encoding="utf-8") == content
            for name, content in contents.items()
        )
        if exact:
            return False
        raise ValueError(
            f"Different Product canonical promotion outputs already exist in {output_dir}. "
            "Use a new output directory; existing generated evidence was not overwritten."
        )
    ensure_dir(output_dir)
    for name, content in contents.items():
        (output_dir / name).write_text(content, encoding="utf-8", newline="")
    return True


def run_product_canonical_promotion(
    materialization_dir: Path,
    state_path: Path,
    output_dir: Path,
) -> ProductCanonicalPromotionResult:
    plan, blockers = build_promotion_plan(materialization_dir, state_path)
    contents = {
        PLAN_NAME: yaml.safe_dump(plan, sort_keys=False, allow_unicode=False),
        BLOCKERS_NAME: csv_content(
            blockers,
            ["blocker_id", "blocker_type", "artifact", "explanation"],
        ),
        REPORT_NAME: render_report(plan),
    }
    outputs_changed = write_outputs(output_dir, contents)
    return ProductCanonicalPromotionResult(
        output_dir=output_dir,
        status=plan["status"],
        plan_path=output_dir / PLAN_NAME,
        blockers_path=output_dir / BLOCKERS_NAME,
        report_path=output_dir / REPORT_NAME,
        target_rows=plan["counts"]["target_rows"],
        excluded_identifiers=plan["counts"]["excluded_identifiers"],
        blocker_count=len(blockers),
        outputs_changed=outputs_changed,
    )
