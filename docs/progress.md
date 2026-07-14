# Current Project State

## Objective

Turn local operational spreadsheets into validated analytical datasets and an approved ERP model, then let users ask governed analytical questions without requiring SQL knowledge.

## Current Stage

Two active tracks: Product Stage 3E.6 dry-run is `ready_for_canonical_state_review` with no canonical apply, and AI analytics Stage 5A now provides safe structured query planning with no SQL execution.

## Last Completed Milestone

On 2026-07-14, Stage 5A added a structured analytics request boundary between future natural-language interpretation and SQL. `analytics-query-plan` opens a local DuckDB catalog read-only, validates allowlisted analytical operations, requires approved cross-table relationships, compiles parameterized `SELECT` SQL, excludes question/filter values from evidence, and performs no execution.

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
- Validate a complete Product snapshot against applied state and produce a hash-bound dry-run canonical promotion plan.
- Fail closed without a partial preview when approved decisions lack materializable source evidence.
- Replace an applied Product decision set only with explicit authority while preserving the prior state in versioned history.
- Generate conceptual schema and business-flow documentation.
- Compile bounded structured analytical requests against a local DuckDB catalog without executing SQL.
- Reject raw SQL, unapproved joins, unknown schema references, unsafe limits, and malformed relationship registries.

## Test Status

- Automated suite: 50 tests passed offline on 2026-07-14; latest run completed in 5.02 seconds.
- All 12 project-local skills passed the official skill validator on 2026-07-13.
- Internal link check: 16 checked, 0 broken on 2026-07-14.
- Main suite is offline and uses temporary directories for generated test artifacts.
- Documentation link checker is available at `scripts/check_internal_links.py`.
- The relocated `.venv` has a stale editable-install path; use the `PYTHONPATH=src` command in `docs/testing.md` until environment repair is explicitly approved.
- The relocated `.venv\Scripts\dataops.exe` launcher exits unsuccessfully because it still embeds the previous environment location; use `.venv\Scripts\python.exe -m data_ops_lab` with `PYTHONPATH=src`.

## Open Risks

- Reports under `outputs/originaldatabase_analysis/` are stale and still show earlier Product blockers; use the 2026-07-14 resolved materialization report under `outputs/019f21a4-daf0-7272-b2a7-09b4f0e2c75b/step3e5_product_materialization_resolved/`.
- `canonical_tables.yml` still describes the pre-application Product key candidate; downstream work must treat `product_reconciliation_state.yml` as the approved Product-specific contract until those representations are deliberately reconciled.
- `ready_for_canonical_state_review` is dry-run evidence only; it is not approval to apply a Product snapshot or change `canonical_tables.yml`.
- Organisation business-key selection and several document-flow relationships still need business context.
- Conflicted line extracts must not be promoted to approved relationships.
- The current orchestrator does not yet expose module discovery, dependency resolution, checkpoints, resume, or dry-run as shared infrastructure.
- Several core pipeline stages still load whole Parquet tables into Pandas; larger-than-memory operation requires DuckDB pushdown and streaming refactors.
- The natural-language adapter, controlled executor, semantic catalog, result validator, and benchmark harness are not implemented yet.

## Active Blockers

- `config/data_model/approved_keys.yml` and `config/data_model/approved_relationships.yml` remain empty by design.
- Broader canonical key and relationship approvals remain pending; the Product-specific state does not populate `approved_keys.yml` or `approved_relationships.yml`.
- No explicit apply contract or approved versioned representation exists yet for the candidate canonical Product snapshot.
- EDS cross-table analytics remain blocked because `approved_relationships.yml` is intentionally empty.
- Public benchmark datasets require separate provenance, license, checksum, schema, and relationship approval before onboarding.

## Next Logical Milestone

Define Stage 5B as a controlled local DuckDB execution contract with read-only enforcement, timeout/resource/result limits, control totals, and auditable result manifests. Keep the Product canonical apply decision separate. Do not query EDS private data or download public benchmarks until the relevant dataset use is explicitly authorized.

## Last Verified Commit

`81a9d67` (`feat(product): add canonical promotion dry-run`)

## Last Updated

2026-07-14 by Codex after implementing the Stage 5A structured analytics query planner and backend roadmap.
