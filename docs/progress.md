# Current Project State

## Objective

Turn local operational spreadsheets into validated analytical datasets and an approved ERP model through a modular, traceable, human-controlled workflow.

## Current Stage

Stage 3E.4 complete: the approved Product reconciliation state is versioned locally. The next Product milestone is a read-only materialization contract that consumes this state without changing raw sources.

## Last Completed Milestone

On 2026-07-13, the user explicitly approved the documented Step 3E.4 representation. `config/data_model/product_reconciliation_state.yml` was created from the validated workbook with digest `f2a7f0bdf338d8733ce03d4b82bfe0056e7e06d47ad157b36a059a9e1c4c0183`: 28 decisions, 18 approvals, and 10 `exclude_from_target_product_model` actions. A second application returned `state_changed=False` and preserved the exact state hash.

## Current Capabilities

- Convert and normalize local CSV/XLSX inputs.
- Profile, clean, infer schemas/keys, and validate relationships.
- Generate SQL suggestions, DuckDB datasets, Tableau exports, and data dictionaries.
- Onboard ERP sources and keep generated model candidates pending review.
- Import serial reference rules and prepare human approval packages.
- Reconcile Product references, validate staged human decisions, and persist explicitly approved Product reconciliation state.
- Produce a clean, validated Product review workbook and a revalidated Step 3E.4 application plan.
- Apply Product reconciliation state only through an explicit, idempotent, reversible command.
- Generate conceptual schema and business-flow documentation.

## Test Status

- Automated suite: 33 tests passed offline on 2026-07-13; latest run completed in 3.56 seconds.
- All 12 project-local skills passed the official skill validator on 2026-07-13.
- Internal link check: 11 checked, 0 broken on 2026-07-13.
- Main suite is offline and uses temporary directories for generated test artifacts.
- Documentation link checker is available at `scripts/check_internal_links.py`.
- The relocated `.venv` has a stale editable-install path; use the `PYTHONPATH=src` command in `docs/testing.md` until environment repair is explicitly approved.
- The relocated `.venv\Scripts\dataops.exe` launcher exits unsuccessfully because it still embeds the previous environment location; use `.venv\Scripts\python.exe -m data_ops_lab` with `PYTHONPATH=src`.

## Open Risks

- Reports under `outputs/originaldatabase_analysis/` are stale and still show earlier Product blockers; use the 2026-07-13 validation path cited above.
- `canonical_tables.yml` still describes the pre-application Product key candidate; downstream work must treat `product_reconciliation_state.yml` as the approved Product-specific contract until those representations are deliberately reconciled.
- Organisation business-key selection and several document-flow relationships still need business context.
- Conflicted line extracts must not be promoted to approved relationships.
- The current orchestrator does not yet expose module discovery, dependency resolution, checkpoints, resume, or dry-run as shared infrastructure.

## Active Blockers

- `config/data_model/approved_keys.yml` and `config/data_model/approved_relationships.yml` remain empty by design.
- No Product materialization module currently consumes `product_reconciliation_state.yml` to build the target Product dataset.
- Broader canonical key and relationship approvals remain pending; the Product-specific state does not populate `approved_keys.yml` or `approved_relationships.yml`.

## Next Logical Milestone

Define and review a read-only Product materialization contract that consumes `product_reconciliation_state.yml`, applies the 18 approved actions, excludes the 10 rejected items, generates technical `product_id` values only for retained records, and produces local validation artifacts before any database or import work.

## Last Verified Commit

`4cfc336` (`feat(product): add reconciliation apply contract`)

## Last Updated

2026-07-13 by Codex after the explicitly approved Step 3E.4 state application.
