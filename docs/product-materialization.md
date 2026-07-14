# Product Materialization Preview Contract

## Module

```yaml
name: product_materialization
version: 1
status: preview_only
entrypoint: data_ops_lab.product_materialization.run_product_materialization
capabilities:
  - validate_applied_product_state
  - materialize_local_product_preview
  - preserve_source_lineage
  - report_blockers_without_partial_preview
failure_policy: fail_closed_and_preserve_existing_outputs
```

## Inputs

- Read-only `originaldatabase/Product.xlsx`.
- Read-only authoritative `originaldatabase/Product_ref.nr.xlsx`.
- The validated final-review workbook whose SHA-256 is recorded in the applied state.
- `config/data_model/product_reconciliation_state.yml` with an exact decision and workbook match.

The module recomputes reconciliation from current source files. It does not trust stale generated reconciliation workbooks.

## Supported Decisions

Materialization v1 supports only the actions present in the applied checkpoint:

- `apply_corrected_product_ref_nr`
- `exclude_from_target_product_model`

Exclusion has precedence when several review decisions reference the same source identifier. Other retained actions fail closed until their row-level semantics are separately defined and tested.

## Identity And Resolution

- `product_id` is UUID5 generated from the applied decision digest, both source-file hashes, source type, and source row number.
- IDs are deterministic only for the exact approved decision and source snapshot.
- Normal original Product rows use the authoritative corrected reference found by the existing reconciliation module.
- An approved conflict may use the same-numbered `Product_ref.nr` row only when all shared source attributes match exactly and the corrected reference is present.
- A retained unmatched `Product_ref.nr` row becomes a Product only when it is non-empty and has a corrected reference.
- Rejected identifiers never receive a target Product identity.

## Outputs

When validation is clean:

- `product_materialization_preview.csv`
- `product_materialization_lineage.csv`
- `product_materialization_exclusions.csv`
- `product_materialization_blockers.csv` with headers and no rows
- `product_materialization_manifest.yml`
- `product_materialization_report.md`

When blocked, only blockers, manifest, and report are created. No partial Product preview is written.

Outputs are deterministic. A byte-identical rerun does not rewrite them. Different contract outputs in the same directory are never overwritten; use a new output directory.

## Validation

- Applied state exactly matches the validated workbook.
- Every retained exception has supported semantics and resolvable source evidence.
- Generated `product_id` values are filled and unique.
- Corrected Product references are filled for every preview row.
- Excluded source identifiers are absent from target lineage.
- Raw sources, review files, applied state, approved keys, and approved relationships remain unchanged.

## Command

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m data_ops_lab product-materialization-preview `
  --workbook "outputs/<run-id>/product_refnr_human_review_shortlist_validated.xlsx" `
  --output "outputs/<run-id>/step3e5_product_materialization"
```

This command is local preview validation only. It does not connect to a database or run imports, migrations, synchronization, or external operations.

## Current Validation Checkpoint

The 2026-07-14 run against the applied Product state is blocked. Three approved `Product_ref.nr` source rows are completely empty and cannot satisfy `apply_corrected_product_ref_nr`: `UNMATCHED_REFNR_006`, `UNMATCHED_REFNR_008`, and `UNMATCHED_REFNR_013`. The module generated blockers, manifest, and report only; no partial Product preview was written.
