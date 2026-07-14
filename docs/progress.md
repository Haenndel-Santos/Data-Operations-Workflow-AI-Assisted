# Current Project State

## Objective

Turn local operational spreadsheets into validated analytical datasets and an approved ERP model, then let users ask governed analytical questions without requiring SQL knowledge.

## Current Stage

Three active tracks: Product Stage 3E.6 is `ready_for_canonical_state_review` with no canonical apply; AI analytics Stage 5A provides safe structured query planning with no SQL execution; and benchmark onboarding provides restricted Northwind/Pubs conversion plus a verified read-only AdventureWorks 2025 restore pending export and dataset approval.

## Last Completed Milestone

On 2026-07-14, the local AdventureWorks backup was proven byte-identical to Microsoft's official release, restored to SQL Server 2025 Developer CU6, set to `READ_ONLY`, and validated with `RESTORE VERIFYONLY` and `DBCC CHECKDB`. The database contains 71 tables, 20 views, 90 declared foreign keys, and 760,167 aggregate table rows. No DuckDB/Parquet export or relationship approval was performed.

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
- Inventory local benchmark sources with hashes, provenance/license status, and separate use approvals.
- Convert supported T-SQL samples to deterministic DuckDB/Parquet artifacts while ignoring operational SQL and retaining foreign keys as pending candidates.
- Restore and integrity-check the official AdventureWorks 2025 backup in an isolated local read-only SQL Server database.

## Test Status

- Automated suite: 56 tests passed offline on 2026-07-14; latest run completed in 9.09 seconds.
- All 12 project-local skills passed the official skill validator on 2026-07-13.
- Internal link check: 20 checked, 0 broken on 2026-07-14.
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
- The natural-language adapter, controlled executor, semantic catalog, result validator, and benchmark question/answer harness are not implemented yet.
- Exact download provenance and licensing remain unconfirmed for Northwind, Pubs, and Contoso; local conversion or restoration is not benchmark, training, publication, or upload approval.
- AdventureWorks now has a compatible local restore runtime, but the SQL Server-to-DuckDB/Parquet export is not implemented; the Contoso recipe references external data and was not executed.
- A second SQL Server 2025 Evaluation instance (`DATAOPSLAB`) remains installed but stopped; project work should use the default Developer instance only when an explicitly authorized restore/export task requires it.

## Active Blockers

- `config/data_model/approved_keys.yml` and `config/data_model/approved_relationships.yml` remain empty by design.
- Broader canonical key and relationship approvals remain pending; the Product-specific state does not populate `approved_keys.yml` or `approved_relationships.yml`.
- No explicit apply contract or approved versioned representation exists yet for the candidate canonical Product snapshot.
- EDS cross-table analytics remain blocked because `approved_relationships.yml` is intentionally empty.
- Northwind and Pubs are converted but remain pending provenance, license, schema, relationship, and benchmark-use approval.
- AdventureWorks is restored and validated but remains pending reproducible export, schema review, relationship approval, and benchmark-use approval.

## Next Logical Milestone

Implement a fail-closed, read-only SQL Server-to-DuckDB/Parquet export for AdventureWorks and validate it first with controlled fixtures, then review its schema and declared relationships without promoting them. In parallel, confirm Northwind/Pubs provenance and define Stage 5B against synthetic fixtures. Keep Product canonical apply separate and do not query EDS private data.

## Last Verified Commit

`a13f9c7` (`feat(benchmarks): add safe local dataset conversion`)

## Last Updated

2026-07-14 by Codex after official AdventureWorks restore and integrity validation.
