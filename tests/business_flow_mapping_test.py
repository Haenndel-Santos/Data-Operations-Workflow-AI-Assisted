from __future__ import annotations

import csv
from pathlib import Path

import yaml

from data_ops_lab.business_flow_mapping import run_business_flow_mapping


def test_business_flow_mapping_outputs_and_preserves_protected_files(tmp_path: Path) -> None:
    output_dir = tmp_path / "schema_overview"
    originaldatabase = tmp_path / "originaldatabase"
    config_dir = tmp_path / "config" / "data_model"
    originaldatabase.mkdir()
    config_dir.mkdir(parents=True)

    product = originaldatabase / "Product.xlsx"
    product_refnr = originaldatabase / "Product_ref.nr.xlsx"
    approved_keys = config_dir / "approved_keys.yml"
    approved_relationships = config_dir / "approved_relationships.yml"
    product.write_bytes(b"product")
    product_refnr.write_bytes(b"product refnr")
    approved_keys.write_text("approved_keys:\n- keep: true\n", encoding="utf-8")
    approved_relationships.write_text("approved_relationships:\n- keep: true\n", encoding="utf-8")
    protected_before = {
        product: product.read_bytes(),
        product_refnr: product_refnr.read_bytes(),
        approved_keys: approved_keys.read_text(encoding="utf-8"),
        approved_relationships: approved_relationships.read_text(encoding="utf-8"),
    }

    result = run_business_flow_mapping(config_dir, output_dir)

    assert result.config_path.exists()
    assert result.mapping_md.exists()
    assert result.relationship_candidates_csv.exists()
    assert result.line_rule_count == 9
    assert result.relationship_candidate_count == 13
    assert product.read_bytes() == protected_before[product]
    assert product_refnr.read_bytes() == protected_before[product_refnr]
    assert approved_keys.read_text(encoding="utf-8") == protected_before[approved_keys]
    assert approved_relationships.read_text(encoding="utf-8") == protected_before[approved_relationships]

    payload = yaml.safe_load(result.config_path.read_text(encoding="utf-8"))
    assert "supplier_purchase_flow" in payload
    assert "sales_customer_flow" in payload
    assert "document_line_rules" in payload
    assert "master_data_context" in payload
    assert "document_flow_candidates" in payload
    assert payload["supplier_purchase_flow"]["flow"] == "RFQ -> ON -> GO -> IF"
    assert payload["sales_customer_flow"]["primary_flow"] == "VK -> CQ -> OC -> GU -> CI"
    assert all(rule["line_key_type"] == "technical_only" for rule in payload["document_line_rules"])
    assert all(row["approved_status"] == "not_approved_pending_validation" for row in payload["document_flow_candidates"])

    mapping = result.mapping_md.read_text(encoding="utf-8")
    assert "RFQ -> ON -> GO -> IF" in mapping
    assert "VK -> CQ -> OC -> GU -> CI" in mapping
    assert "Organisation / Debtor -> CP -> OC -> ON -> GO -> GU -> CI" in mapping
    assert "approved_relationships.yml" in mapping

    with result.relationship_candidates_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 13
    assert any(row["source_business_object"] == "RFQ" and row["target_business_object"] == "ON" for row in rows)
    assert any(row["source_business_object"] == "OC" and row["target_business_object"] == "ON" for row in rows)
    assert all(row["business_status"] == "business_confirmed_pending_field_validation" for row in rows)
