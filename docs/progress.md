# Current Project State

## Objective

Turn local operational spreadsheets into validated analytical datasets and an approved ERP model through a modular, traceable, human-controlled workflow.

## Current Stage

Stage 3: human review and Product reference reconciliation. Tooling has reached final Product review validation, but application is blocked.

## Last Completed Milestone

The final Product RefNr review workbook was read and validated without applying decisions. All 28 decisions are syntactically valid and none are pending, but 10 required `final_human_notes` values are missing. The latest report is `outputs/originaldatabase_analysis/step3e_human_approval_spreadsheet/product_refnr_final_review_validation_report.md` (2026-06-17 14:39 local file time).

## Current Capabilities

- Convert and normalize local CSV/XLSX inputs.
- Profile, clean, infer schemas/keys, and validate relationships.
- Generate SQL suggestions, DuckDB datasets, Tableau exports, and data dictionaries.
- Onboard ERP sources and keep generated model candidates pending review.
- Import serial reference rules and prepare human approval packages.
- Reconcile Product references and validate staged human decisions without applying them.
- Generate conceptual schema and business-flow documentation.

## Test Status

- Automated suite: 28 tests passed offline on 2026-07-13 in 3.41 seconds.
- All 12 project-local skills passed the official skill validator on 2026-07-13.
- Internal link check: 10 checked, 0 broken on 2026-07-13.
- Main suite is offline and uses temporary directories for generated test artifacts.
- Documentation link checker is available at `scripts/check_internal_links.py`.
- The relocated `.venv` has a stale editable-install path; use the `PYTHONPATH=src` command in `docs/testing.md` until environment repair is explicitly approved.

## Open Risks

- `outputs/.../schema_overview/pending_modeling_questions.md` is stale: it reports 18 missing notes and 2 inconsistencies, while the newer final validation reports 10 missing notes and 0 inconsistencies.
- Organisation business-key selection and several document-flow relationships still need business context.
- Conflicted line extracts must not be promoted to approved relationships.
- The current orchestrator does not yet expose module discovery, dependency resolution, checkpoints, resume, or dry-run as shared infrastructure.

## Active Blockers

- Ten Product final-review rows require human notes.
- `config/data_model/approved_keys.yml` and `config/data_model/approved_relationships.yml` remain empty by design.
- No final Product decision may be applied until validation reports `ready_for_apply=true` and the user explicitly authorizes the apply step.

## Next Logical Milestone

Complete the 10 missing human notes, rerun `validate-product-refnr-final-review`, and confirm a clean readiness report. Only then define and review a reversible apply contract before changing approved model files.

## Last Verified Commit

`5bb4058` (`Initial project sync`)

## Last Updated

2026-07-13 by Codex during shared execution-protocol adoption.
