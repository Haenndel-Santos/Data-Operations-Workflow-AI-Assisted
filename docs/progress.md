# Current Project State

## Objective

Turn local operational spreadsheets into validated analytical datasets and an approved ERP model through a modular, traceable, human-controlled workflow.

## Current Stage

Stage 3E.4 contract review: the Product application command, reversible state representation, tests, and real dry-run are complete. No Product decisions have been applied to approved model state yet.

## Last Completed Milestone

On 2026-07-13, Step 3E.4 was implemented with dry-run as the default and an explicit `--apply` gate. The real validated workbook produced 28 mapped decisions, 18 approvals, and 10 `exclude_from_target_product_model` actions with digest `f2a7f0bdf338d8733ce03d4b82bfe0056e7e06d47ad157b36a059a9e1c4c0183`. Protected-file hashes were unchanged and `config/data_model/product_reconciliation_state.yml` was not created.

## Current Capabilities

- Convert and normalize local CSV/XLSX inputs.
- Profile, clean, infer schemas/keys, and validate relationships.
- Generate SQL suggestions, DuckDB datasets, Tableau exports, and data dictionaries.
- Onboard ERP sources and keep generated model candidates pending review.
- Import serial reference rules and prepare human approval packages.
- Reconcile Product references and validate staged human decisions without applying them.
- Produce a clean, validated Product review workbook and a revalidated Step 3E.4 application plan.
- Apply Product reconciliation state only through an explicit, idempotent, reversible command.
- Generate conceptual schema and business-flow documentation.

## Test Status

- Automated suite: 33 tests passed offline on 2026-07-13; latest run completed in 3.27 seconds.
- All 12 project-local skills passed the official skill validator on 2026-07-13.
- Internal link check: 11 checked, 0 broken on 2026-07-13.
- Main suite is offline and uses temporary directories for generated test artifacts.
- Documentation link checker is available at `scripts/check_internal_links.py`.
- The relocated `.venv` has a stale editable-install path; use the `PYTHONPATH=src` command in `docs/testing.md` until environment repair is explicitly approved.
- The relocated `.venv\Scripts\dataops.exe` launcher exits unsuccessfully because it still embeds the previous environment location; use `.venv\Scripts\python.exe -m data_ops_lab` with `PYTHONPATH=src`.

## Open Risks

- Reports under `outputs/originaldatabase_analysis/` are stale and still show earlier Product blockers; use the 2026-07-13 validation path cited above.
- Organisation business-key selection and several document-flow relationships still need business context.
- Conflicted line extracts must not be promoted to approved relationships.
- The current orchestrator does not yet expose module discovery, dependency resolution, checkpoints, resume, or dry-run as shared infrastructure.

## Active Blockers

- `config/data_model/approved_keys.yml` and `config/data_model/approved_relationships.yml` remain empty by design.
- The proposed versioned representation, `config/data_model/product_reconciliation_state.yml`, has not yet received explicit apply authorization.
- `product_reconciliation_state.yml` does not exist; the completed run was intentionally dry-run only.

## Next Logical Milestone

Review the Step 3E.4 contract in `docs/product-refnr-application.md` and its dry-run artifacts. After explicit approval of this representation, rerun the same digest with `--apply`; do not use `--replace-existing` unless a future divergent state is separately reviewed.

## Last Verified Commit

`15f8c3c` (`docs(product): record rejected final review items`)

## Last Updated

2026-07-13 by Codex after Step 3E.4 contract implementation and dry-run validation.
