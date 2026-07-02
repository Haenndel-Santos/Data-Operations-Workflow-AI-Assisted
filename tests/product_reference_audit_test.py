from __future__ import annotations

from pathlib import Path

import pandas as pd

from data_ops_lab.product_reference_audit import run_product_reference_audit


def test_product_reference_audit_masks_duplicates_and_preserves_approved_files(tmp_path: Path) -> None:
    data_dir = tmp_path / "originaldatabase"
    output_dir = tmp_path / "outputs"
    config_dir = tmp_path / "config" / "data_model"
    data_dir.mkdir()
    output_dir.mkdir()
    config_dir.mkdir(parents=True)

    product_path = data_dir / "Product.xlsx"
    product_rows = pd.DataFrame(
        [
            {
                "Part. nr. (SKU)": "SECRET-DUP-REF",
                "Name": "Product A",
                "Item Description": "Widget A",
                "Creditor": "Supplier 1",
                "Product Group Name": "Group A",
                "Gross Sales": "10",
            },
            {
                "Part. nr. (SKU)": "SECRET-DUP-REF",
                "Name": "Product B",
                "Item Description": "Widget B",
                "Creditor": "Supplier 2",
                "Product Group Name": "Group B",
                "Gross Sales": "20",
            },
            {
                "Part. nr. (SKU)": "PD2600001",
                "Name": "Serial Product",
                "Item Description": "Serial description",
                "Creditor": "Supplier 3",
                "Product Group Name": "Group C",
                "Gross Sales": "30",
            },
            {
                "Part. nr. (SKU)": "",
                "Suppl. part nr. (SKU)": "ALT-001",
                "Name": "Repair Candidate",
                "Item Description": "Has alternate reference",
                "Creditor": "Supplier 4",
                "Product Group Name": "Group D",
                "Gross Sales": "40",
            },
            {
                "Part. nr. (SKU)": "",
                "Name": "Human Review",
                "Item Description": "No alternate reference",
                "Creditor": "Supplier 5",
                "Product Group Name": "Group E",
                "Gross Sales": "50",
            },
        ]
    )
    with pd.ExcelWriter(product_path, engine="openpyxl") as writer:
        product_rows.to_excel(writer, sheet_name="Export_Product", index=False)

    approved_keys = config_dir / "approved_keys.yml"
    approved_relationships = config_dir / "approved_relationships.yml"
    approved_keys.write_text("approved_keys:\n- keep: true\n", encoding="utf-8")
    approved_relationships.write_text("approved_relationships:\n- keep: true\n", encoding="utf-8")
    product_before = product_path.read_bytes()
    keys_before = approved_keys.read_text(encoding="utf-8")
    relationships_before = approved_relationships.read_text(encoding="utf-8")

    result = run_product_reference_audit(data_dir, output_dir)

    assert result.report_path.exists()
    assert result.total_products == 5
    assert result.duplicate_group_count == 1
    assert result.duplicate_occurrence_count == 1
    assert result.empty_reference_count == 2
    assert result.product_status == "manually_confirmed_pending_duplicate_validation"
    assert product_path.read_bytes() == product_before
    assert approved_keys.read_text(encoding="utf-8") == keys_before
    assert approved_relationships.read_text(encoding="utf-8") == relationships_before

    report = result.report_path.read_text(encoding="utf-8")
    assert "product_dup_001_" in report
    assert "likely_distinct_products_sharing_reference" in report
    assert "repair_candidate" in report
    assert "requires_human_review" in report
    assert "SECRET-DUP-REF" not in report
    assert "ALT-001" not in report
