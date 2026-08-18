from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .source_onboarding import backup_existing, ensure_dir


OUTPUT_DIR = Path("outputs/originaldatabase_analysis/schema_overview")


@dataclass(frozen=True)
class ConceptualTable:
    table_name: str
    table_group: str
    table_role: str
    expected_prefix: str
    planned_primary_key: str
    semantic_ref: str
    foreign_keys: str
    source_table: str
    source_file: str
    source_status: str
    approval_status: str
    pending_issue: str
    columns: list[tuple[str, str, str]]


@dataclass(frozen=True)
class SchemaOverviewResult:
    output_dir: Path
    overview_md: Path
    conceptual_sql: Path
    relationship_map_md: Path
    pending_questions_md: Path
    summary_csv: Path
    conceptual_table_count: int


def run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def base_audit_columns() -> list[tuple[str, str, str]]:
    return [
        ("source_table", "TEXT", "Physical source table or normalized source table name."),
        ("source_file", "TEXT", "Original source file name."),
        ("source_record_id", "TEXT", "Original row or record identifier from source."),
        ("review_status", "TEXT", "Modeling or human-review status."),
    ]


def master_table(
    table_name: str,
    source_table: str,
    source_file: str,
    expected_prefix: str,
    semantic_ref: str,
    pending_issue: str = "",
) -> ConceptualTable:
    columns = [
        (f"{table_name.removeprefix('dim_')}_id", "BIGINT", "Generated technical primary key."),
        (semantic_ref, "TEXT", "Semantic business reference when approved."),
        ("business_name", "TEXT", "Display or business name where available."),
    ] + base_audit_columns()
    return ConceptualTable(
        table_name=table_name,
        table_group="master_data",
        table_role="master",
        expected_prefix=expected_prefix,
        planned_primary_key=f"{table_name.removeprefix('dim_')}_id",
        semantic_ref=semantic_ref,
        foreign_keys="",
        source_table=source_table,
        source_file=source_file,
        source_status="canonical_source_identified",
        approval_status="manually_confirmed_pending_application",
        pending_issue=pending_issue,
        columns=columns,
    )


def document_header(
    table_name: str,
    table_group: str,
    source_table: str,
    source_file: str,
    expected_prefix: str,
    semantic_ref: str,
    foreign_keys: str = "",
) -> ConceptualTable:
    columns = [
        (f"{table_name.removeprefix('fact_')}_id", "BIGINT", "Generated technical primary key for the header table."),
        (semantic_ref, "TEXT", f"Semantic document reference validated by expected prefix {expected_prefix}."),
        ("document_date", "DATE", "Document date where available."),
        ("status", "TEXT", "Document status where available."),
    ] + fk_columns(foreign_keys) + base_audit_columns()
    return ConceptualTable(
        table_name=table_name,
        table_group=table_group,
        table_role="document_header",
        expected_prefix=expected_prefix,
        planned_primary_key=f"{table_name.removeprefix('fact_')}_id",
        semantic_ref=semantic_ref,
        foreign_keys=foreign_keys,
        source_table=source_table,
        source_file=source_file,
        source_status="canonical_source_identified",
        approval_status="manually_confirmed_pending_application",
        pending_issue="relationship approval not applied yet",
        columns=columns,
    )


def document_line(
    table_name: str,
    table_group: str,
    source_table: str,
    source_file: str,
    header_ref: str,
    foreign_keys: str,
) -> ConceptualTable:
    columns = [
        (f"{table_name.removeprefix('fact_')}_line_id", "BIGINT", "Generated technical primary key for line grain."),
        (header_ref, "TEXT", "Header semantic reference carried by the line table."),
        ("row_position", "INTEGER", "Analytical row position within the document header."),
        ("product_id", "BIGINT", "Optional resolved Product technical key after Product reconciliation."),
        ("product_ref_nr", "TEXT", "Corrected Product reference when reconciled."),
        ("part_nr_sku", "TEXT", "Business/product search reference carried by the line."),
        ("quantity", "DECIMAL(18, 4)", "Line quantity where available."),
        ("net_amount", "DECIMAL(18, 4)", "Line amount where available."),
    ] + fk_columns(foreign_keys) + base_audit_columns()
    return ConceptualTable(
        table_name=table_name,
        table_group=table_group,
        table_role="document_line",
        expected_prefix="",
        planned_primary_key=f"{table_name.removeprefix('fact_')}_line_id",
        semantic_ref=header_ref,
        foreign_keys=foreign_keys,
        source_table=source_table,
        source_file=source_file,
        source_status="canonical_source_identified",
        approval_status="pending_relationship_review",
        pending_issue="line grain uses ref_nr + row_position only as analytical key; not ERP business key",
        columns=columns,
    )


def product_table() -> ConceptualTable:
    columns = [
        ("product_id", "BIGINT", "Generated technical primary key. Planned final Product primary key."),
        ("product_ref_nr", "TEXT", "Corrected canonical ERP product reference from Product_ref.nr when reconciled."),
        ("part_nr_sku", "TEXT", "Business/search/customer/supplier-facing product reference."),
        ("pd_ref_nr", "TEXT", "Optional PD-style serial reference when available."),
        ("product_description", "TEXT", "Product description."),
        ("product_group_name", "TEXT", "Product group or category."),
        ("supplier_part_nr_sku", "TEXT", "Supplier-facing product reference where available."),
        ("is_active", "BOOLEAN", "Active/inactive marker when available or derived after review."),
    ] + base_audit_columns()
    return ConceptualTable(
        table_name="dim_product",
        table_group="master_data",
        table_role="master",
        expected_prefix="PD optional",
        planned_primary_key="product_id",
        semantic_ref="product_ref_nr",
        foreign_keys="",
        source_table="product_export_product + product_refnr",
        source_file="Product.xlsx + Product_ref.nr.xlsx",
        source_status="canonical_source_identified_with_refnr_enrichment",
        approval_status="not_finalized_pending_reconciliation_review",
        pending_issue="Product notes missing and duplicate/refnr reconciliation inconsistencies block final application",
        columns=columns,
    )


def organisation_table() -> ConceptualTable:
    columns = [
        ("organisation_id", "BIGINT", "Generated technical primary key."),
        ("organisation_ref_nr", "TEXT", "Generic organisation reference; no forced serial prefix."),
        ("organisation_name", "TEXT", "Organisation name where available."),
    ] + base_audit_columns()
    return ConceptualTable(
        table_name="dim_organisation",
        table_group="master_data",
        table_role="master",
        expected_prefix="",
        planned_primary_key="organisation_id",
        semantic_ref="organisation_ref_nr",
        foreign_keys="",
        source_table="organisation_export_organisation",
        source_file="Organisation.xlsx",
        source_status="canonical_source_identified",
        approval_status="needs_business_context",
        pending_issue="Organisation final business-key decision remains pending; do not force serial prefix",
        columns=columns,
    )


def enrichment_table(table_name: str, source_table: str, source_file: str) -> ConceptualTable:
    columns = [
        (f"{table_name.removeprefix('dim_')}_id", "BIGINT", "Generated technical primary key for enrichment table."),
        ("product_id", "BIGINT", "Resolved Product technical key after reconciliation."),
        ("product_ref_nr", "TEXT", "Corrected Product reference when available."),
        ("part_nr_sku", "TEXT", "Business/search product reference."),
        ("attribute_name", "TEXT", "Generic enrichment attribute name."),
        ("attribute_value", "TEXT", "Generic enrichment attribute value."),
    ] + base_audit_columns()
    return ConceptualTable(
        table_name=table_name,
        table_group="product_enrichment",
        table_role="enrichment",
        expected_prefix="",
        planned_primary_key=f"{table_name.removeprefix('dim_')}_id",
        semantic_ref="product_ref_nr",
        foreign_keys="product_id -> dim_product.product_id",
        source_table=source_table,
        source_file=source_file,
        source_status="complement_source_identified",
        approval_status="pending_review",
        pending_issue="enrichment grain and relevance require review before analytical use",
        columns=columns,
    )


def fk_columns(foreign_keys: str) -> list[tuple[str, str, str]]:
    columns = []
    if "dim_debtor" in foreign_keys:
        columns.append(("debtor_id", "BIGINT", "Optional resolved debtor/customer key."))
    if "dim_creditor" in foreign_keys:
        columns.append(("creditor_id", "BIGINT", "Optional resolved creditor/supplier key."))
    if "dim_product" in foreign_keys:
        columns.append(("product_id", "BIGINT", "Optional resolved product key."))
    return columns


def conceptual_tables() -> list[ConceptualTable]:
    return [
        master_table("dim_creditor", "creditor_export_creditor", "Creditor.xlsx", "CR", "cr_ref_nr"),
        master_table("dim_debtor", "debtor_export_debtor", "Debtor.xlsx", "DE", "de_ref_nr"),
        organisation_table(),
        product_table(),
        document_header("fact_customer_project", "sales_flow", "customerproject_export_customerproject", "CustomerProject.xlsx", "CP", "cp_ref_nr", "dim_debtor.debtor_id"),
        document_header("fact_sales_opportunity", "sales_flow", "salesopportunity", "SalesOpportunity.csv", "VK", "vk_ref_nr", "dim_debtor.debtor_id"),
        document_line("fact_sales_opportunity_line", "sales_flow", "salesopportunityline_export_salesopportunityline", "SalesOpportunityLine.xlsx", "vk_ref_nr", "fact_sales_opportunity.vk_ref_nr; dim_product.product_id"),
        document_header("fact_sales_quotation", "sales_flow", "salesquotation", "SalesQuotation.csv", "CQ", "cq_ref_nr", "fact_sales_opportunity.vk_ref_nr; dim_debtor.debtor_id"),
        document_line("fact_sales_quotation_line", "sales_flow", "salesquotationline_export_salesquotationline", "SalesQuotationLine.xlsx", "cq_ref_nr", "fact_sales_quotation.cq_ref_nr; dim_product.product_id"),
        document_header("fact_sales_order", "sales_flow", "salesorder", "SalesOrder.csv", "OC", "oc_ref_nr", "fact_sales_quotation.cq_ref_nr; dim_debtor.debtor_id"),
        document_line("fact_sales_order_line", "sales_flow", "salesorderline", "SalesOrderLine.csv / SalesOrderLine.xlsx", "oc_ref_nr", "fact_sales_order.oc_ref_nr; dim_product.product_id"),
        document_header("fact_delivery_note", "sales_flow", "deliverynote_export_deliverynote", "DeliveryNote.xlsx", "GU", "gu_ref_nr", "fact_sales_order.oc_ref_nr; dim_debtor.debtor_id"),
        document_line("fact_delivery_note_line", "sales_flow", "deliverynoteline", "DeliveryNoteLine.csv / DeliveryNoteLine.xlsx", "gu_ref_nr", "fact_delivery_note.gu_ref_nr; dim_product.product_id"),
        document_header("fact_sales_invoice", "sales_flow", "salesinvoice", "SalesInvoice.csv", "CI", "ci_ref_nr", "fact_delivery_note.gu_ref_nr; dim_debtor.debtor_id"),
        document_line("fact_sales_invoice_line", "sales_flow", "salesinvoiceline_export_salesinvoiceline", "SalesInvoiceLine.xlsx", "ci_ref_nr", "fact_sales_invoice.ci_ref_nr; dim_product.product_id"),
        document_header("fact_purchase_quotation", "purchase_flow", "purchasequotation", "PurchaseQuotation.csv", "RFQ", "rfq_ref_nr", "dim_creditor.creditor_id"),
        document_line("fact_purchase_quotation_line", "purchase_flow", "purchasequotationline_export_purchasequotationline", "PurchaseQuotationLine.xlsx", "rfq_ref_nr", "fact_purchase_quotation.rfq_ref_nr; dim_product.product_id"),
        document_header("fact_purchase_order", "purchase_flow", "purchaseorder_3_export_purchaseorder", "PurchaseOrder (3).xlsx", "ON", "on_ref_nr", "fact_purchase_quotation.rfq_ref_nr; dim_creditor.creditor_id"),
        document_line("fact_purchase_order_line", "purchase_flow", "purchaseorderline_export_purchaseorderline", "PurchaseOrderLine.xlsx", "on_ref_nr", "fact_purchase_order.on_ref_nr; dim_product.product_id"),
        document_header("fact_goods_reception", "purchase_flow", "goodsreception_export_goodsreception", "GoodsReception.xlsx", "GO", "go_ref_nr", "fact_purchase_order.on_ref_nr; dim_creditor.creditor_id"),
        document_line("fact_goods_reception_line", "purchase_flow", "goodsreceptionline_export_goodsreceptionline", "GoodsReceptionLine.xlsx", "go_ref_nr", "fact_goods_reception.go_ref_nr; dim_product.product_id"),
        document_header("fact_purchase_invoice", "purchase_flow", "purchaseinvoice", "PurchaseInvoice.csv", "IF", "if_ref_nr", "fact_goods_reception.go_ref_nr; fact_purchase_order.on_ref_nr; dim_creditor.creditor_id"),
        document_line("fact_purchase_invoice_line", "purchase_flow", "purchaseinvoiceline", "PurchaseInvoiceLine.csv / PurchaseInvoiceLine.xlsx", "if_ref_nr", "fact_purchase_invoice.if_ref_nr; dim_product.product_id"),
        enrichment_table("dim_product_supplier", "productsupplier_export_productsupplier", "ProductSupplier.xlsx"),
        enrichment_table("dim_product_description", "productdescription_export_productdescription", "ProductDescription.xlsx"),
        enrichment_table("dim_product_composition", "productcomposition_export_productcomposition", "ProductComposition.xlsx"),
        enrichment_table("dim_product_price_break", "productpricebreak_export_productpricebreak", "ProductPriceBreak.xlsx"),
    ]


def render_overview(tables: list[ConceptualTable]) -> str:
    lines = [
        "# Main Database Schema Overview",
        "",
        "This is a conceptual/logical schema overview only. It does not create a final database, apply approvals, export Tableau files, or modify raw data.",
        "",
        "## Model Summary",
        "",
        "- Product is a canonical master table, but final Product application remains pending until Product RefNr human review notes and inconsistencies are fixed.",
        "- Document headers use validated serial references such as `oc_ref_nr`, `on_ref_nr`, `gu_ref_nr`, and `ci_ref_nr` when approved.",
        "- Document lines point to their header through the header semantic reference; line `ref_nr` alone is not a primary key.",
        "- Organisation remains a generic master with no forced serial prefix.",
        "",
        "## Canonical Tables",
        "",
        "| Table | Group | Role | Prefix | Planned key | Semantic ref | Approval status | Pending issue |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for table in tables:
        lines.append(
            f"| `{table.table_name}` | {table.table_group} | {table.table_role} | {table.expected_prefix or 'none'} | `{table.planned_primary_key}` | `{table.semantic_ref}` | {table.approval_status} | {table.pending_issue or 'none'} |"
        )
    lines.extend(
        [
            "",
            "## Principal Relationships",
            "",
            "- Sales flow: `VK -> CQ -> OC -> GU -> CI`.",
            "- Purchase flow: `RFQ -> ON -> GO -> IF`.",
            "- Line tables use the header semantic reference plus `row_position` as analytical line grain.",
            "- Product links to line tables through `product_ref_nr`, `part_nr_sku`, and supplier part references until Product reconciliation is finalized.",
            "- Debtor links to the sales/customer side.",
            "- Creditor links to the purchase/supplier side.",
            "- Organisation remains a generic master pending final business-key decision.",
            "",
            "## Risks Pending",
            "",
            "- Product RefNr decisions have missing required notes and duplicate-review inconsistencies.",
            "- `approved_keys.yml` and `approved_relationships.yml` are not updated by this overview.",
            "- Source canonical choices for duplicate CSV/XLSX exports remain pending in some areas.",
            "- Conflicting line extracts such as `purchaseorderline2`, `purchaseorderline3`, and `salesorderline2` require business context.",
            "",
            "## Not Ready For Analysis",
            "",
            "- Do not use this SQL as a deployed production schema.",
            "- Do not use Product final key assumptions until Product RefNr review is completed.",
            "- Do not use line-table relationships with conflicts as approved joins.",
        ]
    )
    return "\n".join(lines)


def sql_identifier(name: str) -> str:
    return name.replace(" ", "_").lower()


def render_sql(tables: list[ConceptualTable]) -> str:
    lines = [
        "-- Main Database Schema Overview",
        "-- Conceptual SQL only. Do not execute as final production DDL.",
        "-- No approvals are applied by this file.",
        "",
    ]
    for table in tables:
        lines.extend(
            [
                f"-- {table.table_name}",
                f"-- group: {table.table_group}",
                f"-- role: {table.table_role}",
                f"-- source: {table.source_table} / {table.source_file}",
                f"-- approval_status: {table.approval_status}",
                f"-- pending_issue: {table.pending_issue or 'none'}",
                f"CREATE TABLE IF NOT EXISTS {table.table_name} (",
            ]
        )
        column_lines = []
        for index, (column, data_type, comment) in enumerate(table.columns):
            suffix = " PRIMARY KEY" if column == table.planned_primary_key else ""
            comma = "," if index < len(table.columns) - 1 else ""
            column_lines.append(f"    {sql_identifier(column)} {data_type}{suffix}{comma} -- {comment}")
        lines.append("\n".join(column_lines))
        lines.extend([");", "-- Foreign keys are conceptual pending approval and are documented in relationship map.", ""])
    return "\n".join(lines)


def render_relationship_map() -> str:
    return "\n".join(
        [
            "# Main Database Relationship Map",
            "",
            "## Document Flow",
            "",
            "- Sales: `VK -> CQ -> OC -> GU -> CI`",
            "- Purchase: `RFQ -> ON -> GO -> IF`",
            "",
            "## Header-Line Relationships",
            "",
            "- `fact_sales_order_line.oc_ref_nr -> fact_sales_order.oc_ref_nr`",
            "- `fact_purchase_order_line.on_ref_nr -> fact_purchase_order.on_ref_nr`",
            "- `fact_delivery_note_line.gu_ref_nr -> fact_delivery_note.gu_ref_nr`",
            "- `fact_goods_reception_line.go_ref_nr -> fact_goods_reception.go_ref_nr`",
            "- All line tables require generated line keys or `ref_nr + row_position`; `ref_nr` alone is not a line primary key.",
            "",
            "## Product Relationships",
            "",
            "- Product links to document line tables through `product_ref_nr`, `part_nr_sku`, `supplier_part_nr_sku`, or a resolved `product_id` after reconciliation.",
            "- `dim_product.product_id` should become the technical key for downstream line-table joins after cleanup.",
            "",
            "## Master Relationships",
            "",
            "- `dim_debtor` links to sales/customer side documents.",
            "- `dim_creditor` links to purchase/supplier side documents.",
            "- `dim_organisation` remains generic master pending final business-key decision.",
        ]
    )


def render_pending_questions() -> str:
    return "\n".join(
        [
            "# Pending Modeling Questions",
            "",
            "## Product",
            "",
            "- Product RefNr review has 18 missing required notes and 2 inconsistencies blocking final application.",
            "- Product final key decision remains pending.",
            "- Confirm whether `product_ref_nr` can be applied after human notes are completed.",
            "",
            "## Organisation",
            "",
            "- Confirm final Organisation business key.",
            "- Do not force a serial prefix for Organisation.",
            "",
            "## Document Flow Relationships",
            "",
            "- Confirm document-flow relationships that remain `needs_business_context` before applying approvals.",
            "- Validate source canonical choices for CSV vs XLSX exports where duplicates exist.",
            "",
            "## Known Conflicts",
            "",
            "- `purchaseorderline2_export_purchaseorderline`: observed OC prefix while expected ON.",
            "- `purchaseorderline3_export_purchaseorderline`: observed OC prefix while expected ON.",
            "- `salesorderline2_export_salesorderline`: observed CR prefix while expected OC.",
            "",
            "## Not To Use Yet",
            "",
            "- Do not use Product final keys in analysis.",
            "- Do not use conflicted line extracts as approved relationships.",
            "- Do not update approved YAML files from this overview.",
        ]
    )


def write_summary_csv(path: Path, tables: list[ConceptualTable], current_run_id: str) -> None:
    ensure_dir(path.parent)
    backup_existing(path, current_run_id)
    columns = [
        "table_name",
        "table_group",
        "table_role",
        "expected_prefix",
        "planned_primary_key",
        "foreign_keys",
        "source_status",
        "approval_status",
        "pending_issue",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for table in tables:
            writer.writerow({column: getattr(table, column) for column in columns})


def write_text(path: Path, text: str, current_run_id: str) -> None:
    ensure_dir(path.parent)
    backup_existing(path, current_run_id)
    path.write_text(text, encoding="utf-8")


def run_schema_overview(output_dir: Path = OUTPUT_DIR) -> SchemaOverviewResult:
    current_run_id = run_id()
    tables = conceptual_tables()
    ensure_dir(output_dir)
    overview_md = output_dir / "main_database_schema_overview.md"
    conceptual_sql = output_dir / "main_database_schema_conceptual.sql"
    relationship_map_md = output_dir / "main_database_relationship_map.md"
    pending_questions_md = output_dir / "pending_modeling_questions.md"
    summary_csv = output_dir / "schema_overview_summary.csv"

    write_text(overview_md, render_overview(tables), current_run_id)
    write_text(conceptual_sql, render_sql(tables), current_run_id)
    write_text(relationship_map_md, render_relationship_map(), current_run_id)
    write_text(pending_questions_md, render_pending_questions(), current_run_id)
    write_summary_csv(summary_csv, tables, current_run_id)

    return SchemaOverviewResult(
        output_dir=output_dir,
        overview_md=overview_md,
        conceptual_sql=conceptual_sql,
        relationship_map_md=relationship_map_md,
        pending_questions_md=pending_questions_md,
        summary_csv=summary_csv,
        conceptual_table_count=len(tables),
    )
