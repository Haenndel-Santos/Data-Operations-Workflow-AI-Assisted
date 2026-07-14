from __future__ import annotations

import csv
import uuid
from pathlib import Path

import yaml

from data_ops_lab.cli import build_parser
from data_ops_lab.product_canonical_promotion import run_product_canonical_promotion
from data_ops_lab.product_materialization import (
    BLOCKERS_NAME,
    EXCLUSIONS_NAME,
    LINEAGE_NAME,
    MANIFEST_NAME,
    PREVIEW_NAME,
    REPORT_NAME,
)


DIGEST = "d" * 64
WORKBOOK_HASH = "a" * 64


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def write_ready_package(tmp_path: Path) -> tuple[Path, Path, Path]:
    materialization_dir = tmp_path / "materialization"
    output_dir = tmp_path / "promotion"
    state_path = tmp_path / "product_reconciliation_state.yml"
    materialization_dir.mkdir()

    first_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "fixture/product/1"))
    second_id = str(uuid.uuid5(uuid.NAMESPACE_URL, "fixture/product/2"))
    state = {
        "version": 1,
        "status": "applied",
        "source": {"workbook_sha256": WORKBOOK_HASH, "decision_digest": DIGEST},
        "model_contract": {
            "table": "product",
            "primary_key": "product_id",
            "primary_key_strategy": "generated_technical",
            "business_reference": "part_nr_sku",
            "corrected_reference": "product_ref_nr",
            "optional_serial_reference": "pd_ref_nr",
            "rejected_action": "exclude_from_target_product_model",
        },
        "counts": {"total": 2, "approved": 1, "rejected": 1},
        "decisions": [],
    }
    state_path.write_text(yaml.safe_dump(state, sort_keys=False), encoding="utf-8")
    manifest = {
        "version": 1,
        "status": "ready_for_local_preview",
        "inputs": {
            "product_sha256": "b" * 64,
            "product_refnr_sha256": "c" * 64,
            "review_workbook_sha256": WORKBOOK_HASH,
            "decision_digest": DIGEST,
        },
        "contract": {
            "product_id": "uuid5-url-v1-state-and-source-snapshot",
            "business_reference": "part_nr_sku",
            "corrected_reference": "product_ref_nr",
            "optional_serial_reference": "pd_ref_nr",
            "exclusion_precedence": True,
            "preview_only": True,
        },
        "counts": {
            "original_rows": 2,
            "product_refnr_rows": 3,
            "review_decisions": 2,
            "candidate_target_rows": 2,
            "excluded_identifiers": 1,
            "blockers": 0,
        },
        "validation": {
            "product_ids_unique": True,
            "empty_product_ref_nr": 0,
            "duplicate_product_ref_nr_occurrences": 0,
            "empty_part_nr_sku": 1,
        },
        "reconciliation_counts": {},
        "blockers": [],
    }
    (materialization_dir / MANIFEST_NAME).write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    write_csv(
        materialization_dir / PREVIEW_NAME,
        ["product_id", "product_ref_nr", "pd_ref_nr", "part_nr_sku", "name"],
        [
            {
                "product_id": first_id,
                "product_ref_nr": "PD2600001",
                "pd_ref_nr": "PD2600001",
                "part_nr_sku": "PRIVATE-SKU-ALPHA",
                "name": "Private Alpha",
            },
            {
                "product_id": second_id,
                "product_ref_nr": "LOCAL-REF-2",
                "pd_ref_nr": "",
                "part_nr_sku": "",
                "name": "Private Beta",
            },
        ],
    )
    write_csv(
        materialization_dir / LINEAGE_NAME,
        [
            "product_id",
            "source_type",
            "original_source_row_number",
            "product_refnr_source_row_number",
            "materialization_action",
            "decision_issue_ids",
        ],
        [
            {
                "product_id": first_id,
                "source_type": "original_product",
                "original_source_row_number": "2",
                "product_refnr_source_row_number": "2",
                "materialization_action": "matched_authoritative_correction",
                "decision_issue_ids": "",
            },
            {
                "product_id": second_id,
                "source_type": "product_refnr_only",
                "original_source_row_number": "",
                "product_refnr_source_row_number": "3",
                "materialization_action": "approved_product_refnr_only",
                "decision_issue_ids": "UNMATCHED_REFNR_001",
            },
        ],
    )
    write_csv(
        materialization_dir / EXCLUSIONS_NAME,
        ["source_identifier", "source_type", "source_row_number", "issue_ids", "reason"],
        [
            {
                "source_identifier": "original_row_9",
                "source_type": "original",
                "source_row_number": "9",
                "issue_ids": "UNMATCHED_ORIGINAL_001",
                "reason": "exclude_from_target_product_model",
            }
        ],
    )
    write_csv(
        materialization_dir / BLOCKERS_NAME,
        ["blocker_id", "issue_ids", "source_identifier", "blocker_type", "explanation"],
        [],
    )
    (materialization_dir / REPORT_NAME).write_text(
        "# Product Materialization Report\n", encoding="utf-8"
    )
    return materialization_dir, state_path, output_dir


def test_product_canonical_promotion_ready_private_and_idempotent(tmp_path: Path) -> None:
    materialization_dir, state_path, output_dir = write_ready_package(tmp_path)
    protected = {
        path: path.read_bytes()
        for path in [state_path, *materialization_dir.iterdir()]
        if path.is_file()
    }

    first = run_product_canonical_promotion(materialization_dir, state_path, output_dir)
    first_outputs = {path.name: path.read_bytes() for path in output_dir.iterdir()}
    second = run_product_canonical_promotion(materialization_dir, state_path, output_dir)

    assert first.status == "ready_for_canonical_state_review"
    assert first.target_rows == 2
    assert first.excluded_identifiers == 1
    assert first.blocker_count == 0
    assert first.outputs_changed is True
    assert second.outputs_changed is False
    assert first_outputs == {path.name: path.read_bytes() for path in output_dir.iterdir()}
    assert all(path.read_bytes() == content for path, content in protected.items())

    plan_text = first.plan_path.read_text(encoding="utf-8")
    plan = yaml.safe_load(plan_text)
    assert plan["approval"]["canonical_state_applied"] is False
    assert plan["approval"]["requires_explicit_apply_contract"] is True
    assert plan["validation"]["lineage_complete"] is True
    assert "PRIVATE-SKU-ALPHA" not in plan_text
    assert "Private Alpha" not in plan_text


def test_product_canonical_promotion_blocks_digest_and_exclusion_drift(tmp_path: Path) -> None:
    materialization_dir, state_path, output_dir = write_ready_package(tmp_path)
    state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    state["source"]["decision_digest"] = "e" * 64
    state_path.write_text(yaml.safe_dump(state, sort_keys=False), encoding="utf-8")
    lineage_path = materialization_dir / LINEAGE_NAME
    with lineage_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["original_source_row_number"] = "9"
    write_csv(lineage_path, list(rows[0]), rows)

    result = run_product_canonical_promotion(materialization_dir, state_path, output_dir)
    with result.blockers_path.open(newline="", encoding="utf-8") as handle:
        blockers = list(csv.DictReader(handle))
    blocker_types = {row["blocker_type"] for row in blockers}

    assert result.status == "blocked"
    assert "decision_digest_mismatch" in blocker_types
    assert "excluded_identifier_in_lineage" in blocker_types
    assert result.target_rows == 2


def test_product_canonical_promotion_blocks_malformed_manifest_counts(tmp_path: Path) -> None:
    materialization_dir, state_path, output_dir = write_ready_package(tmp_path)
    manifest_path = materialization_dir / MANIFEST_NAME
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["counts"] = ["invalid"]
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

    result = run_product_canonical_promotion(materialization_dir, state_path, output_dir)
    with result.blockers_path.open(newline="", encoding="utf-8") as handle:
        blockers = list(csv.DictReader(handle))

    assert result.status == "blocked"
    assert sum(row["blocker_type"] == "manifest_count_mismatch" for row in blockers) == 3


def test_product_canonical_promotion_refuses_different_existing_outputs(tmp_path: Path) -> None:
    materialization_dir, state_path, output_dir = write_ready_package(tmp_path)
    first = run_product_canonical_promotion(materialization_dir, state_path, output_dir)
    first.report_path.write_text("changed generated evidence\n", encoding="utf-8")

    try:
        run_product_canonical_promotion(materialization_dir, state_path, output_dir)
    except ValueError as error:
        assert "existing generated evidence was not overwritten" in str(error)
    else:
        raise AssertionError("Different existing promotion outputs must be refused.")
    assert first.report_path.read_text(encoding="utf-8") == "changed generated evidence\n"


def test_product_canonical_promotion_cli_contract() -> None:
    args = build_parser().parse_args(
        [
            "product-canonical-promotion-plan",
            "--materialization",
            "materialization",
            "--state",
            "state.yml",
            "--output",
            "promotion",
        ]
    )

    assert args.command == "product-canonical-promotion-plan"
    assert args.materialization == Path("materialization")
    assert args.state == Path("state.yml")
    assert args.output == Path("promotion")
