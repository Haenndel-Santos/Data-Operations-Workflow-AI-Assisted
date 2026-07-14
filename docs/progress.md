# Current Project State

## Objective

Turn local operational spreadsheets into validated analytical datasets and an approved ERP model, then let users ask governed analytical questions without requiring SQL knowledge.

## Current Stage

Three active tracks: Product Stage 3E.6 is `ready_for_canonical_state_review` with no canonical apply; AI analytics has Stage 5A-5D governed planning/execution/translation plus synthetic Stage 5E answer evaluation, per-case benchmark review/approval infrastructure, and dry-run dataset-backed binding validation, but no real approved catalog, approved benchmark pack, dataset-backed execution, or live provider; and benchmark onboarding remains pending dataset export/review and approval.

## Last Completed Milestone

On 2026-07-14, Stage 5E added hash-bound benchmark review preparation and explicit approval generation. The pending review lists every case and requires human decisions for the recorded response, expected request, expected result, comparison policy, and bounded use scopes. Approval is dry-run by default, requires explicit `--apply`, writes only a user-supplied immutable path, and carries the review hash plus normalized decision digest. No real review, approval, dataset connection, query, provider, network, upload, or training was used.

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
- Execute an exact reviewed structured plan against local DuckDB with read-only, timeout, memory, thread, temporary-storage, row, and byte controls.
- Produce hash-bound result CSV, manifest control totals, blockers, and explicit no-row diagnostics without partial output on failure or divergent overwrite.
- Validate candidate dataset/table names, synonyms, dimensions, measures, and relationship paths against live DuckDB metadata and approved relationships.
- Resolve normalized business terms as unique, ambiguous, unknown, or catalog-blocked without silently selecting a candidate.
- Prepare a pending human semantic review bound to the exact compiled catalog by SHA-256.
- Validate complete semantic decisions in dry-run mode and apply a minimal approved registry only with explicit authority.
- Preserve ambiguity for clarification or record one exact human-selected target without promoting candidate relationships.
- Compile structured semantic intent into the existing Stage 5A request using only applied approved definitions.
- Return explicit clarification evidence for ambiguous terms and reject model-supplied SQL, aggregates, columns, and physical joins.
- Translate a local question through an injected provider contract while minimizing semantic context and preserving the authoritative question.
- Reproduce provider behavior offline from recorded responses and block network providers unless explicitly authorized per invocation.
- Evaluate Stage 5D offline with governed exact/equivalent intent, clarification, hallucination, unsafe-output, timeout, and provider-failure expectations.
- Report separate status, semantic-intent, blocker, clarification, and overall metrics without persisting questions or provider responses.
- Materialize bounded temporary DuckDB fixtures from structured allowlisted synthetic tables, types, and values without accepting setup SQL.
- Require an exact versioned request before Stage 5A planning and Stage 5B execution in synthetic expected-answer evaluation.
- Compare exact ordered CSV output plus row, column, null, pipeline, and request controls across grouped, filtered, no-row, null-filter, and approved-join cases.
- Validate a version-1 dataset-backed benchmark package without opening its DuckDB artifact or reading its catalog, tables, or rows.
- Bind dataset identity, approved semantics, approved relationships, candidate pack, and separate human approval by SHA-256.
- Validate bounded typed expected answers with exact comparison or explicit per-column numeric tolerances while refusing live-provider, upload, and training authority.
- Prepare a pending per-case benchmark review bound to dataset, semantic, relationship, and pack hashes without duplicating case content into evidence.
- Validate complete human case and scope decisions in dry-run mode and generate a separate approval only with explicit apply authority.
- Refuse pending, rejected, missing, duplicate, unknown, drifted, scope-expanding, or divergent review/approval state without partial authority writes.
- Inventory local benchmark sources with hashes, provenance/license status, and separate use approvals.
- Convert supported T-SQL samples to deterministic DuckDB/Parquet artifacts while ignoring operational SQL and retaining foreign keys as pending candidates.
- Restore and integrity-check the official AdventureWorks 2025 backup in an isolated local read-only SQL Server database.

## Test Status

- Automated suite: 131 tests passed offline on 2026-07-14; latest run completed in 16.59 seconds.
- All 12 project-local skills passed the official skill validator on 2026-07-13.
- Internal link check: 45 checked, 0 broken on 2026-07-14.
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
- No concrete semantic catalog has completed human review or been applied; Stage 5D therefore remains operationally blocked for real datasets.
- A live model provider, result narration, approved real benchmark pack, and dataset-backed execution are not implemented yet. Synthetic Stage 5D/5E packs and the dataset-binding dry-run validate backend contracts only and are not live-model or real-dataset quality evidence.
- Stage 5B plan-to-execution drift still uses size and nanosecond modification time. The new dataset-backed package contract adds a full database SHA-256 before future evaluation, but no execution runner consumes that authority yet.
- Exact download provenance and licensing remain unconfirmed for Northwind, Pubs, and Contoso; local conversion or restoration is not benchmark, training, publication, or upload approval.
- AdventureWorks now has a compatible local restore runtime, but the SQL Server-to-DuckDB/Parquet export is not implemented; the Contoso recipe references external data and was not executed.
- A second SQL Server 2025 Evaluation instance (`DATAOPSLAB`) remains installed but stopped; project work should use the default Developer instance only when an explicitly authorized restore/export task requires it.

## Active Blockers

- `config/data_model/approved_keys.yml` and `config/data_model/approved_relationships.yml` remain empty by design.
- Broader canonical key and relationship approvals remain pending; the Product-specific state does not populate `approved_keys.yml` or `approved_relationships.yml`.
- No explicit apply contract or approved versioned representation exists yet for the candidate canonical Product snapshot.
- EDS cross-table analytics remain blocked because `approved_relationships.yml` is intentionally empty.
- No applied `config/analytics/approved_semantic_catalog.yml` exists for a real authorized dataset.
- Northwind and Pubs are converted but remain pending provenance, license, schema, relationship, and benchmark-use approval.
- AdventureWorks is restored and validated but remains pending reproducible export, schema review, relationship approval, and benchmark-use approval.

## Next Logical Milestone

Design and implement the dataset-backed offline evaluator that consumes a valid generated approval, rechecks every immutable hash, replays recorded Stage 5D responses, preserves exact Stage 5A request gating and Stage 5B read-only controls, and applies exact or reviewed numeric comparison. Test only with temporary synthetic data first. Do not export/query AdventureWorks or use EDS merely to implement the runner. Keep live-provider selection, narration, Product canonical apply, and external/database work separate. In parallel, profile the highest-memory Pandas stages before selecting one measured DuckDB pushdown refactor.

## Last Verified Commit

`7144863` (`feat(analytics): add dataset benchmark validation`)

## Last Updated

2026-07-14 by Codex after the dataset benchmark review and approval checkpoint.
