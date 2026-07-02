# EDS SQL Domain Rules

This file contains shared ERP modeling rules for future Codex sessions working in the EDS SQL repository.

## Canonical ERP Prefixes And Entities

| Prefix | Entity |
| --- | --- |
| `CR` | Creditor |
| `DE` | Debtor |
| `CP` | Customer Project |
| `OC` | Sales Order |
| `CQ` | Sales Quotation |
| `CI` | Sales Invoice |
| `GU` | Delivery Note |
| `GO` | Goods Reception |
| `ON` | Purchase Order |
| `IF` | Purchase Invoice |
| `RFQ` | Purchase Quotation / Request for Quotation |
| `VK` | Sales Opportunity |
| `PD` | Product |

## Core Business Flow

```text
Organisation / Debtor -> CP -> OC -> ON -> GO -> GU -> CI
```

## Supplier-Side Flow

```text
Creditor / Organisation -> RFQ -> ON -> GO -> IF
```

## Line-Table Rule

When a document reference such as `OC26000001` has multiple product/detail rows, the corresponding line table contains all lines belonging to that header document.

In line tables, `ref_nr` is normally a foreign/document reference to the header, not a unique line-level primary key by itself.

## Product Rules

- `Product_ref.nr.xlsx` is the authoritative correction/enrichment source for product reference numbers.
- Product references may appear as PD-style references, SKU references, or textual part references.
- `part_nr_sku` is the canonical business/search/customer/supplier-facing product reference candidate.
- `pd_ref_nr` may be optional and must not be assumed to exist for every product.
- Current modeling recommendation: use a technical/generated `product_id` as primary key where product reference reconciliation is not fully finalized.
- Use `product_ref_nr` as the corrected canonical reference from `Product_ref.nr` where supported.
- Never assume every product has a valid PD reference.

## Human Approval Rules

- Human review always wins over automation.
- Human decisions must never be silently replaced.
- Conflicts must be flagged.
- Relevant human review files include:
  - `human_approval_matrix.xlsx`
  - `product_refnr_human_review_shortlist.xlsx`
  - `product_reference_human_review.xlsx`

## General Modeling Rules

- Do not invent relationships.
- Prefer evidence from ERP exports, validated outputs, tests, and approved human review files.
- Every modeling decision must be documented.
- Every PK/FK recommendation must include evidence, confidence, and unresolved risks.
- Distinguish header tables from line/detail tables.
- Keep candidates separate from approved decisions.
- Mark blocked decisions when required human review evidence is missing.
