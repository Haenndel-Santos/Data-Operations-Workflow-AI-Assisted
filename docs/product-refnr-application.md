# Step 3E.4 Product Reconciliation Application Contract

## Purpose

Step 3E.4 converts a clean Product final-review workbook into an auditable application plan and, only with explicit authorization, a versioned local model-state file. It never edits source Product rows or the human-review workbook.

## Applied Checkpoint

The user explicitly approved this representation on 2026-07-13. `config/data_model/product_reconciliation_state.yml` is applied with decision digest `f2a7f0bdf338d8733ce03d4b82bfe0056e7e06d47ad157b36a059a9e1c4c0183`: 28 decisions, 18 approvals, and 10 logical target-model exclusions. An immediate reapplication was idempotent and did not rewrite the state.

## Inputs

- A completed Product final-review workbook.
- Every consolidated row must pass the existing final-review validation.
- `pending`, empty, invalid, inconsistent, or missing-note decisions block the operation.
- `needs_business_context` is valid for review tracking but blocks Step 3E.4 application.

The command revalidates workbook contents. A filename alone is not treated as proof of validation.

## Decision Mapping

| Human decision | Target action |
|---|---|
| `approved_use_corrected_product_ref_nr` | `apply_corrected_product_ref_nr` |
| `approved_keep_original_part_nr_sku_only` | `keep_original_part_nr_sku` |
| `approved_create_technical_product_id_only` | `create_technical_product_id` |
| `merge_duplicate_records` | `merge_duplicate_records` |
| `keep_as_separate_products` | `keep_separate_products` |
| `rejected` | `exclude_from_target_product_model` |

Rejection is a logical target-model exclusion. It is not source-row deletion.

## Outputs

- `product_refnr_application_plan.csv`: detailed local plan, including review notes; keep under ignored `outputs/`.
- `product_refnr_application_report.md`: execution mode, digest, counts, exclusions, and safety assertions.
- `config/data_model/product_reconciliation_state.yml`: minimal versioned state written only in apply mode.

The versioned state contains hashes, the Product model contract, counts, review IDs, decisions, and actions. It intentionally excludes raw Product references, descriptions, and workbook notes.

## Model Contract

- Target table: `product`.
- Primary key: generated technical `product_id`.
- Main business/search/matching reference: `part_nr_sku`.
- Corrected canonical reference: `product_ref_nr`.
- Optional serial reference: `pd_ref_nr`.
- Rejected records: excluded from the target Product model and not assigned a Product identity.

## Safety And Idempotency

The command defaults to dry-run. `--apply` is required to write approved state. Reapplying the same decision digest does not rewrite the state file. A different existing state is rejected unless `--replace-existing` is also explicitly supplied; replacement preserves the old file under `config/data_model/history/`.

The command does not modify `approved_keys.yml` or `approved_relationships.yml`, connect to a database, run a migration, import data, or synchronize an external system.

## Commands

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m data_ops_lab apply-product-refnr-decisions `
  --workbook "outputs/<run-id>/product_refnr_human_review_shortlist_validated.xlsx" `
  --output "outputs/<run-id>/step3e4_product_application"
```

After reviewing the contract and dry-run artifacts, authorized application uses the same command with `--apply`.
