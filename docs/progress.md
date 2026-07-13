# Current Project State

## Objective

Turn local operational spreadsheets into validated analytical datasets and an approved ERP model through a modular, traceable, human-controlled workflow.

## Current Stage

Stage 3E.4 readiness: Product reference final review is clean and ready for an explicit apply workflow. No Product decisions have been applied to approved model files yet.

## Last Completed Milestone

On 2026-07-13, the user confirmed that the 10 blocking Product review items are invalid. Their final decisions were recorded as `rejected` with explicit exclusion notes in a new review workbook and validated without applying them. The validation is clean: 28 valid decisions, 18 approved, 10 rejected, 0 pending, 0 missing notes, and 0 inconsistencies. The current report is `outputs/019f21a4-daf0-7272-b2a7-09b4f0e2c75b/product_refnr_final_review_validation_report.md`.

## Current Capabilities

- Convert and normalize local CSV/XLSX inputs.
- Profile, clean, infer schemas/keys, and validate relationships.
- Generate SQL suggestions, DuckDB datasets, Tableau exports, and data dictionaries.
- Onboard ERP sources and keep generated model candidates pending review.
- Import serial reference rules and prepare human approval packages.
- Reconcile Product references and validate staged human decisions without applying them.
- Produce a clean, validated Product review workbook that is ready for a future apply workflow.
- Generate conceptual schema and business-flow documentation.

## Test Status

- Automated suite: 28 tests passed offline on 2026-07-13; latest run completed in 3.39 seconds.
- All 12 project-local skills passed the official skill validator on 2026-07-13.
- Internal link check: 10 checked, 0 broken on 2026-07-13.
- Main suite is offline and uses temporary directories for generated test artifacts.
- Documentation link checker is available at `scripts/check_internal_links.py`.
- The relocated `.venv` has a stale editable-install path; use the `PYTHONPATH=src` command in `docs/testing.md` until environment repair is explicitly approved.

## Open Risks

- Reports under `outputs/originaldatabase_analysis/` are stale and still show earlier Product blockers; use the 2026-07-13 validation path cited above.
- Organisation business-key selection and several document-flow relationships still need business context.
- Conflicted line extracts must not be promoted to approved relationships.
- The current orchestrator does not yet expose module discovery, dependency resolution, checkpoints, resume, or dry-run as shared infrastructure.

## Active Blockers

- `config/data_model/approved_keys.yml` and `config/data_model/approved_relationships.yml` remain empty by design.
- The repository has no implemented Step 3E.4 contract/command for applying Product reconciliation decisions.
- Applying the clean workbook requires an explicit, reversible mapping from rejected review items to target-model exclusion state; raw Product sources must not be deleted or edited.

## Next Logical Milestone

Define and review the reversible Step 3E.4 apply contract. It must consume the validated workbook, exclude the 10 rejected review items from the target Product model, preserve raw sources, record an audit trail, and update approved model state only under explicit authorization.

## Last Verified Commit

`d9dc95e` (`docs(project): add execution and continuity protocol`)

## Last Updated

2026-07-13 by Codex after clean Product final-review validation.
