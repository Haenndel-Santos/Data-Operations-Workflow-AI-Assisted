# Current Project State

## Objective

Turn local operational spreadsheets into validated analytical datasets and an approved ERP model through a modular, traceable, human-controlled workflow.

## Current Stage

Stage 3E.5 complete: the read-only Product materialization contract has produced and validated a deterministic local preview after the human owner rejected the three empty `Product_ref.nr` records.

## Last Completed Milestone

On 2026-07-14, the human owner classified `UNMATCHED_REFNR_006`, `UNMATCHED_REFNR_008`, and `UNMATCHED_REFNR_013` as invalid. The new validated decision set contains 28 decisions, 15 approved and 13 rejected, with digest `4f14e2cb265d9729263ab5bd572a41365f4bbbceec7e007d930b539faa5fe260`. Step 3E.4 replaced the applied state reversibly, and Step 3E.5 generated a complete local preview of 1,733 Product rows with 13 exclusions, 1,733 unique technical IDs, no empty or duplicate corrected references, and no blockers.

## Current Capabilities

- Convert and normalize local CSV/XLSX inputs.
- Profile, clean, infer schemas/keys, and validate relationships.
- Generate SQL suggestions, DuckDB datasets, Tableau exports, and data dictionaries.
- Onboard ERP sources and keep generated model candidates pending review.
- Import serial reference rules and prepare human approval packages.
- Reconcile Product references, validate staged human decisions, and persist explicitly approved Product reconciliation state.
- Produce a clean, validated Product review workbook and a revalidated Step 3E.4 application plan.
- Apply Product reconciliation state only through an explicit, idempotent, reversible command.
- Validate applied Product state and build deterministic local Product preview, lineage, exclusion, manifest, and blocker artifacts.
- Fail closed without a partial preview when approved decisions lack materializable source evidence.
- Replace an applied Product decision set only with explicit authority while preserving the prior state in versioned history.
- Generate conceptual schema and business-flow documentation.

## Test Status

- Automated suite: 38 tests passed offline on 2026-07-14; latest run completed in 4.14 seconds.
- All 12 project-local skills passed the official skill validator on 2026-07-13.
- Internal link check: 12 checked, 0 broken on 2026-07-14.
- Main suite is offline and uses temporary directories for generated test artifacts.
- Documentation link checker is available at `scripts/check_internal_links.py`.
- The relocated `.venv` has a stale editable-install path; use the `PYTHONPATH=src` command in `docs/testing.md` until environment repair is explicitly approved.
- The relocated `.venv\Scripts\dataops.exe` launcher exits unsuccessfully because it still embeds the previous environment location; use `.venv\Scripts\python.exe -m data_ops_lab` with `PYTHONPATH=src`.

## Open Risks

- Reports under `outputs/originaldatabase_analysis/` are stale and still show earlier Product blockers; use the 2026-07-14 resolved materialization report under `outputs/019f21a4-daf0-7272-b2a7-09b4f0e2c75b/step3e5_product_materialization_resolved/`.
- `canonical_tables.yml` still describes the pre-application Product key candidate; downstream work must treat `product_reconciliation_state.yml` as the approved Product-specific contract until those representations are deliberately reconciled.
- Organisation business-key selection and several document-flow relationships still need business context.
- Conflicted line extracts must not be promoted to approved relationships.
- The current orchestrator does not yet expose module discovery, dependency resolution, checkpoints, resume, or dry-run as shared infrastructure.

## Active Blockers

- `config/data_model/approved_keys.yml` and `config/data_model/approved_relationships.yml` remain empty by design.
- Broader canonical key and relationship approvals remain pending; the Product-specific state does not populate `approved_keys.yml` or `approved_relationships.yml`.

## Next Logical Milestone

Review the completed local Product preview and define the next explicit, offline consumption or promotion contract for the canonical Product model. Do not import, migrate, synchronize, or connect the preview to an external database without separate authorization.

## Last Verified Commit

`7d41fb3` (`feat(product): add fail-closed materialization preview`)

## Last Updated

2026-07-14 by Codex after resolving the empty-row decisions and validating the complete local Product preview.
