# Current Project State

## Objective

Turn local operational spreadsheets into validated analytical datasets and an approved ERP model, then let users ask governed analytical questions without requiring SQL knowledge.

## Current Stage

Three active tracks: Product Stage 3E.6 is `ready_for_canonical_state_review` with no canonical apply; AI roadmap Phases 0-1 now have a validated static session registry plus measured synthetic scale evidence and one contract-preserving DuckDB pushdown, while Stage 5A-5F governed analytics still lacks a real approved catalog, approved benchmark pack, live provider, dynamic dispatch, or user interface; and benchmark onboarding remains pending dataset selection/export/review and approval.

## Last Completed Milestone

On 2026-07-14, AI roadmap Phase 1 added an isolated synthetic performance harness and optimized the measured schema/key bottleneck with Arrow metadata and local DuckDB pushdown. On identical 3-table/50,000-row inputs, schema peak process memory fell from 184,971,264 to 134,606,848 bytes (-27.23%) and runtime from 35.096404 to 0.353394 seconds (-98.99%). Exact equivalence tests preserve schema, nullability, empty-table behavior, primary-key candidates, repeated line references, and candidate relationships. No real dataset, approved state, provider, network, external database, upload, or training was used.

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
- Execute an approved dataset-backed pack through recorded Stage 5D, exact request gating, Stage 5A planning, and Stage 5B read-only revalidation with fixed limits.
- Recheck manifest, database, semantic, relationship, pack, and approval SHA-256 immediately before each query and discard evidence on drift.
- Compare ordered typed results exactly by default or with per-column reviewed numeric tolerance while keeping expectation failures separate from contract blockers.
- Revalidate completed Stage 5B evidence into a deterministic local Markdown result and a bounded facts package without reconnecting to DuckDB.
- Preserve exact displayed CSV text, stable cell/control fact IDs, source hashes, explicit no-row diagnostics, and preview-truncation caveats.
- Validate recorded result narration against the exact presentation manifest and facts SHA-256 before any provider call.
- Require every narrative claim to cite supplied facts, preserve all cited numeric tokens exactly, and include row, no-row, and preview-truncation controls.
- Reject SQL-like narration, unknown or missing citations, facts drift, implicit network providers, divergent outputs, and narrative authority over Stage 5B evidence.
- Prepare a recorded local analytics session through translation, semantic adaptation, and Stage 5A without authorizing execution.
- Generate a pending execution-review template bound to exact preparation and plan hashes rather than self-approving a ready plan.
- Resume only from a separately completed human review and preserve the last valid execution, presentation, or narration checkpoint on failure.
- Reuse byte-identical nested stage evidence while refusing divergent session checkpoints and exposing no review bypass or network switch.
- Statically validate the versioned analytics-session module registry, exact
  entrypoint parameters, test files, dependency closure, cycles, stage order,
  fail-closed policies, and non-automatic human execution gate.
- Generate deterministic synthetic Parquet and measure profiler, cleaner,
  schema/key, and relationship-validation runtime, peak process/Python memory,
  input footprint, outputs, and temporary storage in isolated processes.
- Infer schema, nullability, uniqueness, PK candidates, and eligible FK overlap
  through Arrow metadata and local DuckDB pushdown without full-table Pandas
  loads or changing candidate/approved separation.
- Maintain a versioned AI implementation roadmap with ordered phases, exit gates, quality targets, and explicit non-authorizations.
- Inventory local benchmark sources with hashes, provenance/license status, and separate use approvals.
- Convert supported T-SQL samples to deterministic DuckDB/Parquet artifacts while ignoring operational SQL and retaining foreign keys as pending candidates.
- Restore and integrity-check the official AdventureWorks 2025 backup in an isolated local read-only SQL Server database.

## Test Status

- Automated suite: 173 tests passed offline on 2026-07-14; latest run completed in 26.18 seconds.
- All 12 project-local skills passed the official skill validator on 2026-07-13.
- Internal link check: 59 checked, 0 broken on 2026-07-14.
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
- The recorded analytics session now has a validated static registry and narrow checkpoints/resume semantics, but registry-driven dispatch and generic partial-run/dry-run infrastructure remain deliberately absent.
- Cleaning is now the highest-memory measured synthetic stage and still loads a full Parquet table into Pandas before writing Parquet and CSV; any bounded-batch refactor must preserve type-detection and exact output contracts.
- No concrete semantic catalog has completed human review or been applied; Stage 5D therefore remains operationally blocked for real datasets.
- A live model provider, approved real benchmark pack, real dataset-backed evaluation, and user interface are not implemented or authorized. Recorded narration proves grounding controls only; synthetic Stage 5D/5E packs and temporary dataset-backed tests are not live-model or business-quality evidence.
- Stage 5B plan-to-execution drift still uses size and nanosecond modification time in ordinary queries. The dataset-backed evaluator additionally rechecks the complete database SHA-256 and every other authority hash before each Stage 5B call and after evaluation.
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

AI roadmap Phase 2 requires a human selection of the first reference dataset and explicit confirmation of authoritative source, version, license, checksum, permitted local benchmark use, and relationship-review scope. Northwind is the recommended first small commercial dataset, but its current local copy remains pending exact provenance/license approval; Chinook would require separately authorized acquisition. Until that strategic authority exists, do not query or promote existing benchmark assets. A separate safe engineering option is another measured Phase 1 increment for cleaning, using only the synthetic harness and exact type/output equivalence tests.

## Last Verified Commit

`3951d7f` (`feat(orchestrator): validate analytics module registry`)

## Last Updated

2026-07-14 by Codex after completing the measured schema/key pushdown for AI roadmap Phase 1.
