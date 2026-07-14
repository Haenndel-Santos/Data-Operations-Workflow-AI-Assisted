# Product Canonical Promotion Plan Contract

## Module

```yaml
name: product_canonical_promotion
version: 1
status: dry_run_only
entrypoint: data_ops_lab.product_canonical_promotion.run_product_canonical_promotion
capabilities:
  - validate_complete_product_materialization
  - bind_candidate_snapshot_to_applied_state
  - report_canonical_promotion_readiness
failure_policy: fail_closed_and_preserve_existing_outputs
```

## Inputs

- A complete Step 3E.5 materialization package: preview, lineage, exclusions, blockers, manifest, and report.
- `config/data_model/product_reconciliation_state.yml` with status `applied`.

The module reads local artifacts only. It does not read raw Product workbooks, copy Product rows into versioned files, or trust an unbound preview.

## Validation

- Applied state and materialization manifest share the exact decision digest and review-workbook hash.
- The materialization status is `ready_for_local_preview` and its contract remains preview-only.
- Preview technical IDs are filled, unique, normalized UUID5 values, and match lineage exactly.
- Corrected Product references are filled and unique.
- Optional `pd_ref_nr` values follow the Product reference rule.
- Exclusion identifiers are filled, unique, and absent from all lineage source identifiers.
- Manifest counts and validation results match the current artifacts.
- The Step 3E.5 blockers file has no blocker rows.

## Outputs

- `product_canonical_promotion_plan.yml`
- `product_canonical_promotion_blockers.csv`
- `product_canonical_promotion_report.md`

Outputs contain hashes, schema names, counts, validation results, and blockers only. Product row values remain in ignored local Step 3E.5 artifacts. A byte-identical rerun does not rewrite outputs, and different existing outputs are never overwritten.

The plan status is `ready_for_canonical_state_review` only when every check passes; otherwise it is `blocked`. Readiness is evidence for human review, not approval or applied canonical state.

## Command

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m data_ops_lab product-canonical-promotion-plan `
  --materialization "outputs/<run-id>/step3e5_product_materialization" `
  --state "config/data_model/product_reconciliation_state.yml" `
  --output "outputs/<run-id>/step3e6_product_canonical_promotion"
```

There is intentionally no `--apply` option. The command does not modify `canonical_tables.yml`, approved keys, approved relationships, applied Product reconciliation state, raw sources, databases, imports, migrations, synchronization jobs, or external systems.

## Current Validation Checkpoint

The 2026-07-14 dry-run against decision digest `4f14e2cb265d9729263ab5bd572a41365f4bbbceec7e007d930b539faa5fe260` is `ready_for_canonical_state_review`: 1,733 candidate Product rows, 13 excluded identifiers, and zero blockers. A repeated run returned `outputs_changed=False`; all output hashes remained unchanged, and no private preview values were copied into the plan, blockers, or report.
