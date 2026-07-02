from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .source_onboarding import DATA_MODEL_DIR, backup_existing, ensure_dir, write_yaml


OUTPUT_DIR = Path("outputs/originaldatabase_analysis/schema_overview")
BUSINESS_FLOW_RULES = "business_flow_rules.yml"
MAPPING_MD = "business_flow_mapping.md"
RELATIONSHIP_CANDIDATES_CSV = "business_flow_relationship_candidates.csv"
BUSINESS_CONFIRMED_STATUS = "business_confirmed_pending_field_validation"
LINE_STATUS = "manually_confirmed_pending_application"
NOT_APPROVED = "not_approved_pending_validation"


@dataclass(frozen=True)
class BusinessFlowMappingResult:
    config_path: Path
    mapping_md: Path
    relationship_candidates_csv: Path
    supplier_flow_count: int
    sales_flow_count: int
    line_rule_count: int
    relationship_candidate_count: int


def run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def relationship_candidate(
    flow_name: str,
    source_business_object: str,
    source_table_candidate: str,
    target_business_object: str,
    target_table_candidate: str,
    expected_source_ref: str,
    expected_target_ref: str,
    relationship_type: str,
    notes: str,
) -> dict[str, Any]:
    return {
        "flow_name": flow_name,
        "source_business_object": source_business_object,
        "source_table_candidate": source_table_candidate,
        "target_business_object": target_business_object,
        "target_table_candidate": target_table_candidate,
        "expected_source_ref": expected_source_ref,
        "expected_target_ref": expected_target_ref,
        "relationship_type": relationship_type,
        "business_status": BUSINESS_CONFIRMED_STATUS,
        "technical_validation_status": "pending_field_validation",
        "approved_status": NOT_APPROVED,
        "notes": notes,
    }


def document_line_rule(line_table: str, header_table: str) -> dict[str, Any]:
    return {
        "line_table": line_table,
        "header_table": header_table,
        "relationship": f"{line_table}.ref_nr -> {header_table}.ref_nr",
        "relationship_type": "header_line",
        "line_ref_column": "ref_nr",
        "header_ref_column": "ref_nr",
        "line_key_rule": "ref_nr + row_position",
        "line_key_type": "technical_only",
        "status": LINE_STATUS,
        "notes": "`ref_nr` points to the document header and is not the primary key of the line table.",
    }


def flow_rules_payload(relationship_candidates: list[dict[str, Any]]) -> dict[str, Any]:
    line_rules = [
        document_line_rule("salesorderline", "salesorder"),
        document_line_rule("purchaseorderline", "purchaseorder"),
        document_line_rule("deliverynoteline", "deliverynote"),
        document_line_rule("goodsreceptionline", "goodsreception"),
        document_line_rule("salesinvoiceline", "salesinvoice"),
        document_line_rule("purchaseinvoiceline", "purchaseinvoice"),
        document_line_rule("salesquotationline", "salesquotation"),
        document_line_rule("purchasequotationline", "purchasequotation"),
        document_line_rule("salesopportunityline", "salesopportunity"),
    ]
    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": "business_flow_documented_pending_technical_validation",
        "supplier_purchase_flow": {
            "flow": "RFQ -> ON -> GO -> IF",
            "supplier_context": "Creditor / Organisation",
            "status": BUSINESS_CONFIRMED_STATUS,
            "objects": [
                {"code": "RFQ", "business_name": "Purchase Quotation / Purchase RFQ", "table_candidate": "purchasequotation"},
                {"code": "ON", "business_name": "Purchase Order", "table_candidate": "purchaseorder"},
                {"code": "GO", "business_name": "Goods Reception", "table_candidate": "goodsreception"},
                {"code": "IF", "business_name": "Purchase Invoice", "table_candidate": "purchaseinvoice"},
            ],
            "notes": "Supplier purchase flow can start from RFQ and continue through purchase order, goods reception, and purchase invoice.",
        },
        "sales_customer_flow": {
            "primary_flow": "VK -> CQ -> OC -> GU -> CI",
            "operational_flow": "Organisation / Debtor -> CP -> OC -> ON -> GO -> GU -> CI",
            "customer_context": "Debtor / DE maps to customer or financial customer side; Organisation is general company/person context.",
            "status": BUSINESS_CONFIRMED_STATUS,
            "objects": [
                {"code": "VK", "business_name": "Sales Opportunity", "table_candidate": "salesopportunity"},
                {"code": "CQ", "business_name": "Sales Quotation", "table_candidate": "salesquotation"},
                {"code": "OC", "business_name": "Sales Order", "table_candidate": "salesorder"},
                {"code": "GU", "business_name": "Delivery Note", "table_candidate": "deliverynote"},
                {"code": "CI", "business_name": "Sales Invoice", "table_candidate": "salesinvoice"},
                {"code": "CP", "business_name": "Customer Project", "table_candidate": "customerproject"},
            ],
            "notes": "VK does not necessarily have an internal project. CP may relate to multiple commercial document references including OC and ON.",
        },
        "document_line_rules": line_rules,
        "master_data_context": {
            "creditor": "Supplier or purchase-side financial context.",
            "debtor": "Customer or sales-side financial customer context.",
            "organisation": "General company/person master context shared by supplier and customer flows.",
            "product": "Canonical master table with generated product_id and reconciled product_ref_nr pending final application.",
            "status": "business_confirmed_pending_key_and_relationship_application",
        },
        "document_flow_candidates": relationship_candidates,
        "guardrails": [
            "This file does not approve keys or relationships.",
            "`approved_keys.yml` must not be updated by the business-flow mapping step.",
            "`approved_relationships.yml` must not be updated by the business-flow mapping step.",
            "Field-level validation is still required before applying document-flow relationships.",
        ],
    }


def relationship_candidates() -> list[dict[str, Any]]:
    return [
        relationship_candidate("supplier_purchase_flow", "RFQ", "purchasequotation", "ON", "purchaseorder", "rfq_ref_nr", "rfq_ref_nr / source reference field", "document_flow", "RFQ can lead to ON."),
        relationship_candidate("supplier_purchase_flow", "ON", "purchaseorder", "GO", "goodsreception", "on_ref_nr", "on_ref_nr / source reference field", "document_flow", "Purchase Order can lead to Goods Reception."),
        relationship_candidate("supplier_purchase_flow", "GO", "goodsreception", "IF", "purchaseinvoice", "go_ref_nr", "go_ref_nr / source reference field", "document_flow", "Goods Reception can lead to Purchase Invoice."),
        relationship_candidate("sales_customer_flow", "VK", "salesopportunity", "CQ", "salesquotation", "vk_ref_nr", "vk_ref_nr / source reference field", "document_flow", "Sales Opportunity can lead to Sales Quotation."),
        relationship_candidate("sales_customer_flow", "CQ", "salesquotation", "OC", "salesorder", "cq_ref_nr", "cq_ref_nr / source reference field", "document_flow", "Sales Quotation can lead to Sales Order."),
        relationship_candidate("sales_customer_flow", "OC", "salesorder", "GU", "deliverynote", "oc_ref_nr", "oc_ref_nr / source reference field", "document_flow", "Sales Order can lead to Delivery Note."),
        relationship_candidate("sales_customer_flow", "GU", "deliverynote", "CI", "salesinvoice", "gu_ref_nr", "gu_ref_nr / source reference field", "document_flow", "Delivery Note can lead to Sales Invoice."),
        relationship_candidate("sales_customer_flow", "CP", "customerproject", "OC", "salesorder", "cp_ref_nr", "cp_ref_nr / project reference field", "document_flow", "Customer Project may contain or relate to Sales Orders."),
        relationship_candidate("cross_operational_flow", "OC", "salesorder", "ON", "purchaseorder", "oc_ref_nr", "oc_ref_nr / sales order reference field", "document_flow", "Sales Order may drive Purchase Order in the operational flow."),
        relationship_candidate("master_to_document_flow", "Organisation/Debtor", "organisation / debtor", "CP", "customerproject", "organisation_ref / debtor_ref", "customer/project party reference", "master_document_context", "Customer context can lead to Customer Project."),
        relationship_candidate("master_to_document_flow", "Creditor/Organisation", "creditor / organisation", "RFQ", "purchasequotation", "creditor_ref / organisation_ref", "supplier party reference", "master_document_context", "Supplier context can lead to RFQ."),
        relationship_candidate("master_to_document_flow", "Creditor/Organisation", "creditor / organisation", "ON", "purchaseorder", "creditor_ref / organisation_ref", "supplier party reference", "master_document_context", "Supplier context can be present on Purchase Order."),
        relationship_candidate("master_to_document_flow", "Creditor/Organisation", "creditor / organisation", "IF", "purchaseinvoice", "creditor_ref / organisation_ref", "supplier party reference", "master_document_context", "Supplier context can be present on Purchase Invoice."),
    ]


def render_mapping_md(payload: dict[str, Any], candidates: list[dict[str, Any]]) -> str:
    lines = [
        "# Business Flow Mapping",
        "",
        "This file documents confirmed operational flow logic only. It does not approve keys, relationships, SQL views, Tableau outputs, or business analysis.",
        "",
        "## Supplier / Purchase Flow",
        "",
        "- Flow: `RFQ -> ON -> GO -> IF`",
        "- `RFQ` = Purchase Quotation / Purchase RFQ.",
        "- `ON` = Purchase Order.",
        "- `GO` = Goods Reception.",
        "- `IF` = Purchase Invoice / finance side.",
        "- Creditor / Organisation represents supplier context.",
        f"- Relationship status: `{BUSINESS_CONFIRMED_STATUS}`.",
        "",
        "## Sales / Customer Flow",
        "",
        "- Flow: `VK -> CQ -> OC -> GU -> CI`",
        "- Operational context: `Organisation / Debtor -> CP -> OC -> ON -> GO -> GU -> CI`.",
        "- `VK` = Sales Opportunity.",
        "- `CQ` = Sales Quotation.",
        "- `OC` = Sales Order.",
        "- `GU` = Delivery Note.",
        "- `CI` = Sales Invoice / customer billing side.",
        "- `CP` = Customer Project.",
        "- Debtor / DE represents the customer or financial customer side and maps to Organisation context.",
        "- Organisation is the general company/person master context.",
        f"- Relationship status: `{BUSINESS_CONFIRMED_STATUS}`.",
        "",
        "## Finance Invoice Context",
        "",
        "- `CI` is customer billing / Sales Invoice.",
        "- `IF` is supplier finance / Purchase Invoice.",
        "",
        "## Confirmed Line Table Logic",
        "",
        "- Line tables represent internal rows/items belonging to document headers.",
        "- In line tables, `ref_nr` points to the header and is not the primary key of the line.",
        "- `ref_nr + row_position` may be used only as a technical analytical key.",
    ]
    for rule in payload["document_line_rules"]:
        lines.append(f"- `{rule['relationship']}`; key rule `{rule['line_key_rule']}`; status `{rule['status']}`.")
    lines.extend(
        [
            "",
            "## Business-Confirmed Pending Field Validation",
            "",
        ]
    )
    for candidate in candidates:
        lines.append(
            f"- {candidate['source_business_object']} -> {candidate['target_business_object']} "
            f"({candidate['flow_name']}): {candidate['source_table_candidate']} -> {candidate['target_table_candidate']}; "
            f"status `{candidate['business_status']}`; approved `{candidate['approved_status']}`."
        )
    lines.extend(
        [
            "",
            "## Not Approved Automatically",
            "",
            "- Document-flow relationships above require field-level validation before approval.",
            "- Header-line rules are manually confirmed conceptually but still not written to `approved_relationships.yml`.",
            "- `approved_keys.yml` and `approved_relationships.yml` are not modified by this step.",
        ]
    )
    return "\n".join(lines)


def write_candidates_csv(path: Path, candidates: list[dict[str, Any]], current_run_id: str) -> None:
    ensure_dir(path.parent)
    backup_existing(path, current_run_id)
    columns = [
        "flow_name",
        "source_business_object",
        "source_table_candidate",
        "target_business_object",
        "target_table_candidate",
        "expected_source_ref",
        "expected_target_ref",
        "relationship_type",
        "business_status",
        "technical_validation_status",
        "approved_status",
        "notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(candidates)


def run_business_flow_mapping(
    config_dir: Path = DATA_MODEL_DIR,
    output_dir: Path = OUTPUT_DIR,
) -> BusinessFlowMappingResult:
    current_run_id = run_id()
    candidates = relationship_candidates()
    payload = flow_rules_payload(candidates)
    ensure_dir(config_dir)
    ensure_dir(output_dir)

    config_path = config_dir / BUSINESS_FLOW_RULES
    mapping_md = output_dir / MAPPING_MD
    relationship_candidates_csv = output_dir / RELATIONSHIP_CANDIDATES_CSV
    write_yaml(config_path, payload, current_run_id)
    backup_existing(mapping_md, current_run_id)
    mapping_md.write_text(render_mapping_md(payload, candidates), encoding="utf-8")
    write_candidates_csv(relationship_candidates_csv, candidates, current_run_id)

    return BusinessFlowMappingResult(
        config_path=config_path,
        mapping_md=mapping_md,
        relationship_candidates_csv=relationship_candidates_csv,
        supplier_flow_count=3,
        sales_flow_count=7,
        line_rule_count=len(payload["document_line_rules"]),
        relationship_candidate_count=len(candidates),
    )
