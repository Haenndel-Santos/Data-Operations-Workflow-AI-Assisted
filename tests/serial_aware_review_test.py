from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
import yaml

from data_ops_lab.serial_aware_review import run_serial_aware_review


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def seed_inputs(root: Path) -> tuple[Path, Path, Path, Path, Path]:
    step3 = root / "outputs" / "originaldatabase_analysis" / "step3_modeling"
    step3c = root / "outputs" / "originaldatabase_analysis" / "step3c_serial_reference_rules"
    config = root / "config" / "data_model"
    output = root / "outputs" / "originaldatabase_analysis" / "step3d_serial_aware_review"
    data_dir = root / "originaldatabase"
    data_dir.mkdir(parents=True)
    pd.DataFrame([{"Ref. nr.": "OC2600001", "Amount": 1}]).to_csv(data_dir / "SalesOrder.csv", index=False)
    pd.DataFrame([{"Ref. nr.": "OC2600001", "Amount": 1}]).to_csv(data_dir / "SalesOrderLine.csv", index=False)
    pd.DataFrame([{"Ref. nr.": "CR2600001", "Amount": 1}]).to_csv(data_dir / "SalesOrderLine2.csv", index=False)

    write_csv(
        step3 / "key_candidates.csv",
        [
            {
                "table_name": "salesorder",
                "source_file": "SalesOrder.csv",
                "candidate_key": "ref_nr",
                "key_type": "natural",
                "non_null_rate": "100.0",
                "uniqueness_rate": "100.0",
                "duplicate_count": "0",
                "confidence_level": "high",
                "reason": "measured",
                "status": "pending_review",
            },
            {
                "table_name": "salesorderline",
                "source_file": "SalesOrderLine.csv",
                "candidate_key": "ref_nr + row_position",
                "key_type": "composite",
                "non_null_rate": "100.0",
                "uniqueness_rate": "100.0",
                "duplicate_count": "0",
                "confidence_level": "high",
                "reason": "measured",
                "status": "pending_review",
            },
        ],
    )
    write_csv(
        step3 / "relationship_candidates.csv",
        [
            {
                "source_table": "salesorderline",
                "source_column": "ref_nr",
                "target_table": "salesorder",
                "target_column": "ref_nr",
                "relationship_type": "header_line",
                "match_rate": "100.0",
                "unmatched_count": "0",
                "target_duplicate_count": "0",
                "join_risk": "low",
                "confidence_level": "high",
                "reason": "measured",
                "status": "pending_review",
                "notes": "candidate only",
            }
        ],
    )
    write_csv(
        step3c / "ref_pattern_validation.csv",
        [
            {
                "table_name": "salesorder",
                "source_file": "SalesOrder.csv",
                "raw_ref_column": "ref_nr",
                "expected_prefix": "OC",
                "detected_prefixes": "OC:1",
                "expected_regex": "^OC[0-9]{2}[0-9]{5}$",
                "total_rows": "1",
                "non_null_ref_count": "1",
                "prefix_match_rate": "100.0",
                "regex_match_rate": "100.0",
                "invalid_ref_count": "0",
                "multiple_prefixes_detected": "False",
                "confidence_level": "high",
                "status": "pending_review",
                "notes": "",
            },
            {
                "table_name": "salesorderline",
                "source_file": "SalesOrderLine.csv",
                "raw_ref_column": "ref_nr",
                "expected_prefix": "OC",
                "detected_prefixes": "OC:1",
                "expected_regex": "^OC[0-9]{2}[0-9]{5}$",
                "total_rows": "1",
                "non_null_ref_count": "1",
                "prefix_match_rate": "100.0",
                "regex_match_rate": "100.0",
                "invalid_ref_count": "0",
                "multiple_prefixes_detected": "False",
                "confidence_level": "high",
                "status": "pending_review",
                "notes": "",
            },
            {
                "table_name": "salesorderline2_export_salesorderline",
                "source_file": "SalesOrderLine2.csv",
                "raw_ref_column": "ref_nr",
                "expected_prefix": "OC",
                "detected_prefixes": "CR:1",
                "expected_regex": "^OC[0-9]{2}[0-9]{5}$",
                "total_rows": "1",
                "non_null_ref_count": "1",
                "prefix_match_rate": "0.0",
                "regex_match_rate": "0.0",
                "invalid_ref_count": "1",
                "multiple_prefixes_detected": "False",
                "confidence_level": "needs_business_context",
                "status": "needs_business_context",
                "notes": "",
            },
        ],
    )
    write_csv(
        step3c / "key_candidate_serial_enrichment.csv",
        [
            {
                "table_name": "salesorder",
                "candidate_key": "ref_nr",
                "previous_confidence_level": "high",
                "non_null_rate": "100.0",
                "uniqueness_rate": "100.0",
                "expected_prefix": "OC",
                "prefix_match_rate": "100.0",
                "regex_match_rate": "100.0",
                "semantic_namespace": "sales_order",
                "semantic_ref_name": "oc_ref_nr",
                "new_confidence_suggestion": "high",
                "status": "pending_review",
                "notes": "",
            }
        ],
    )
    config.mkdir(parents=True)
    (config / "semantic_ref_mapping.yml").write_text(
        yaml.safe_dump(
            {
                "table_ref_mapping": {
                    "salesorder": {
                        "expected_prefix": "OC",
                        "semantic_namespace": "sales_order",
                        "semantic_ref_name": "oc_ref_nr",
                        "raw_column": "ref_nr",
                        "status": "pending_review",
                    },
                    "salesorderline": {
                        "expected_prefix": "OC",
                        "semantic_namespace": "sales_order",
                        "semantic_ref_name": "oc_ref_nr",
                        "raw_column": "ref_nr",
                        "status": "pending_review",
                    },
                    "salesorderline2_export_salesorderline": {
                        "expected_prefix": "OC",
                        "semantic_namespace": "sales_order",
                        "semantic_ref_name": "oc_ref_nr",
                        "raw_column": "ref_nr",
                        "status": "pending_review",
                    },
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return step3, step3c, config, output, data_dir


def test_serial_aware_review_generates_outputs_and_no_approved_status(tmp_path: Path) -> None:
    step3, step3c, config, output, data_dir = seed_inputs(tmp_path)

    result = run_serial_aware_review(step3, step3c, config, output, data_dir)

    assert result.key_review_count == 2
    assert result.relationship_review_count == 1
    assert (output / "serial_aware_key_review.csv").exists()
    assert (output / "serial_aware_relationship_review.csv").exists()
    assert (output / "conflict_investigation.md").exists()
    assert (output / "human_decision_shortlist.md").exists()
    assert (config / "human_approval_template_serial_aware.yml").exists()

    rows = list(csv.DictReader((output / "serial_aware_key_review.csv").open(encoding="utf-8")))
    relationship_rows = list(csv.DictReader((output / "serial_aware_relationship_review.csv").open(encoding="utf-8")))
    assert "approved" not in {row["status"] for row in rows + relationship_rows}
    assert any(row["recommended_human_decision"] == "approve_as_semantic_primary_key" for row in rows)
    assert any(row["recommended_human_decision"] == "approve_header_line_relationship" for row in relationship_rows)


def test_serial_aware_review_preserves_approved_files(tmp_path: Path) -> None:
    step3, step3c, config, output, data_dir = seed_inputs(tmp_path)
    approved_keys = config / "approved_keys.yml"
    approved_relationships = config / "approved_relationships.yml"
    approved_keys.write_text("approved_keys:\n- keep: true\n", encoding="utf-8")
    approved_relationships.write_text("approved_relationships:\n- keep: true\n", encoding="utf-8")
    keys_before = approved_keys.read_text(encoding="utf-8")
    relationships_before = approved_relationships.read_text(encoding="utf-8")

    run_serial_aware_review(step3, step3c, config, output, data_dir)

    assert approved_keys.read_text(encoding="utf-8") == keys_before
    assert approved_relationships.read_text(encoding="utf-8") == relationships_before
