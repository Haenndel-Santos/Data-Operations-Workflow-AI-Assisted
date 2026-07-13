---
name: product-reference-specialist
description: Reconcile ERP Product references including Product_ref.nr, PD references, SKU or textual references, duplicates, missing values, and Product key decisions. Use for Product mapping, authoritative reference enrichment, duplicate review, technical-key recommendations, and Product-related human decisions.
---

# Product Reference Specialist

## Purpose

Handle Product, `Product_ref.nr`, PD references, SKU references, duplicate product references, missing product refs, and reconciliation logic.

## When to use this skill

Use this skill for product mapping, product key design, `Product_ref.nr.xlsx` interpretation, PD/SKU/reference reconciliation, duplicate product references, missing product references, and product-related human review decisions.

## Project-specific knowledge

- Use `.codex/project-context/eds-sql-domain-rules.md` as shared context.
- `Product_ref.nr.xlsx` is the authoritative correction/enrichment source for product reference numbers.
- Product references may appear as PD-style references, SKU references, or textual part references.
- `part_nr_sku` is the canonical business/search/customer/supplier-facing product reference candidate.
- `pd_ref_nr` may be optional and must not be assumed to exist for every product.
- Current modeling recommendation: use a technical/generated `product_id` as primary key where product reference reconciliation is not fully finalized.
- Use `product_ref_nr` as the corrected canonical reference from `Product_ref.nr` where supported.

## Hard rules

- `Product_ref.nr` is authoritative for corrected product references.
- `part_nr_sku` is a business reference, not automatically a safe PK.
- `pd_ref_nr` is optional.
- Product key decisions must respect completed human review files.
- Do not assume all products have PD codes.
- Conflicts with human review must be flagged.

## Recommended workflow

1. Read the shared domain rules and relevant human review files.
2. Identify all product reference fields involved in the task.
3. Compare raw references to `Product_ref.nr.xlsx` corrections where available.
4. Separate PD-style references, SKU references, textual part references, and missing references.
5. Check duplicates, nulls, conflicting mappings, and unresolved human review items.
6. Recommend either a final key, a candidate key, or a blocked decision with evidence.

## Expected outputs

- Product reference reconciliation notes.
- Conflict list.
- Final or pending key recommendation.
- Evidence-backed product mapping assumptions.

## Things to never do

- Never assume every product has a valid PD reference.
- Never use `part_nr_sku` as a primary key without duplicate and approval checks.
- Never ignore `Product_ref.nr.xlsx` when corrected references are relevant.
- Never silently replace completed human review decisions.
- Never merge product identities when evidence is ambiguous.
