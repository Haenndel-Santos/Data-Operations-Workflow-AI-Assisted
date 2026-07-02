from __future__ import annotations

import csv
from pathlib import Path

from data_ops_lab.schema_overview import run_schema_overview


def test_schema_overview_outputs_and_preserves_protected_files(tmp_path: Path) -> None:
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

    result = run_schema_overview(output_dir)

    assert result.conceptual_table_count == 27
    assert result.overview_md.exists()
    assert result.conceptual_sql.exists()
    assert result.relationship_map_md.exists()
    assert result.pending_questions_md.exists()
    assert result.summary_csv.exists()
    assert product.read_bytes() == protected_before[product]
    assert product_refnr.read_bytes() == protected_before[product_refnr]
    assert approved_keys.read_text(encoding="utf-8") == protected_before[approved_keys]
    assert approved_relationships.read_text(encoding="utf-8") == protected_before[approved_relationships]

    sql = result.conceptual_sql.read_text(encoding="utf-8")
    for table_name in [
        "dim_creditor",
        "dim_debtor",
        "dim_organisation",
        "dim_product",
        "fact_sales_order",
        "fact_sales_order_line",
        "fact_purchase_order",
        "fact_goods_reception_line",
        "dim_product_supplier",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table_name}" in sql
    assert "product_id BIGINT PRIMARY KEY" in sql
    assert "product_ref_nr TEXT" in sql
    assert "approval_status: not_finalized_pending_reconciliation_review" in sql

    overview = result.overview_md.read_text(encoding="utf-8")
    assert "Product is a canonical master table" in overview
    assert "Organisation remains a generic master with no forced serial prefix." in overview

    pending = result.pending_questions_md.read_text(encoding="utf-8")
    assert "Product RefNr review has 18 missing required notes" in pending
    assert "purchaseorderline2_export_purchaseorderline" in pending

    with result.summary_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 27
    product_row = next(row for row in rows if row["table_name"] == "dim_product")
    assert product_row["planned_primary_key"] == "product_id"
    assert product_row["approval_status"] == "not_finalized_pending_reconciliation_review"
    organisation_row = next(row for row in rows if row["table_name"] == "dim_organisation")
    assert organisation_row["expected_prefix"] == ""
    assert organisation_row["approval_status"] == "needs_business_context"
