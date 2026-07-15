# Current Project State

## Objective

Turn local operational spreadsheets into validated analytical datasets and an approved ERP model, then let users ask governed analytical questions without requiring SQL knowledge.

## Current Stage

Three active tracks: Product Stage 3E.6 is `ready_for_canonical_state_review` with no canonical apply; AI roadmap Phases 0-4 passed their gates for Northwind and the selected local Ollama development provider; and Phase 5 is active after passing its first approved real-dataset recorded offline answer baseline. Stage 5A-5F governed analytics has its first applied real semantic catalog, loopback live intent provider, immutable 13-case Northwind answer authority, and reproducible 13/13 recorded evaluation, but still lacks comparative live-provider evidence, dynamic dispatch, live narration, or a user interface.

## Last Completed Milestone

On 2026-07-15, the project owner approved all four required decisions for each of the 13 Northwind expected-answer cases. The completed review SHA-256 is `deaa274d7a015071896d91788a7ca8f2d7c2f358e416f4e9b40833242493630f`; the generated immutable approval SHA-256 is `b1ceda6e675448d3fc808d21af2a919c26de4f2016e7d68dfbb6b32b019016b0`. Approval dry-run/apply and final package validation reported zero blockers. The recorded offline evaluator then passed 13/13 cases: pipeline, request, result, and control accuracy were all 1.0; exact-result accuracy was 12/12 and numeric-tolerance accuracy was 1/1. The repeated approval and evaluation runs were byte-idempotent. Only recorded responses and fixed-limit read-only DuckDB queries were used. No live Ollama call, external network, upload, training, publication, or narration occurred.

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
- Translate one English question through local Ollama `gpt-oss:20b` with a literal loopback endpoint, proxy exclusion, no credentials, kind-specific semantic-ID JSON Schema, bounded inference, and deterministic Stage 5D validation.
- Evaluate Stage 5D offline with governed exact/equivalent intent, clarification, hallucination, unsafe-output, timeout, and provider-failure expectations.
- Report separate status, semantic-intent, blocker, clarification, and overall metrics without persisting questions or provider responses.
- Materialize bounded temporary DuckDB fixtures from structured allowlisted synthetic tables, types, and values without accepting setup SQL.
- Require an exact versioned request before Stage 5A planning and Stage 5B execution in synthetic expected-answer evaluation.
- Compare exact ordered CSV output plus row, column, null, pipeline, and request controls across grouped, filtered, no-row, null-filter, and approved-join cases.
- Validate a bounded versioned real-dataset answer design with exact dataset, semantic, relationship, recorded-intent, result-shape, typed-column, coverage, and comparison bindings.
- Batch recorded Stage 5D and exact Stage 5A preparation into one immutable checkpoint and aggregate per-case execution-review template without Stage 5B, table-row access, or network use.
- Refuse provider SQL, source drift, nondeterministic multi-row designs, output-alias drift, invalid tolerance policy, review auto-approval, and divergent preparation evidence.
- Validate a completed aggregate execution review with exact source, scope, case, and plan hashes before any real answer query.
- Execute approved real-dataset plans sequentially through ordinary Stage 5B revalidation with fixed read-only limits and authority checks before and after every case.
- Convert result CSV into explicit benchmark comparison types only after validating hashes, schema, DuckDB types, row/column/null controls, no-row status, and truncation controls.
- Write a candidate expected-answer pack only when every case completes and the complete pack passes the existing dataset benchmark contract.
- Hash-bind persistent materialization case, blocker, and report evidence; refuse partial, divergent, or tampered reuse without overwriting it.
- Accept the legacy minimal relationship registry and the validated governed projection carrying completed-review authority and non-authorization metadata.
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
- Validate exact reference-dataset provenance, SPDX license evidence, current
  artifact hashes, independent conversion equivalence, read-only schema/counts,
  declared primary keys, declared relationship integrity, and explicit use
  scopes before generating a separate pending relationship review.
- Require a completed review to bind the exact reference-manifest and candidate
  hashes and accept or reject every relationship with reviewer/time/notes before
  reporting `ready_for_semantic_modeling`.
- Project accepted relationship decisions into a hash-bound local approved
  registry only after completed-review validation; pending or rejected
  decisions never enter the approved list.
- Compile the versioned real Northwind semantic candidate against its live local
  catalog and approved relationship projection, with explicit grains, direct
  measures, multilingual synonyms, fanout caveats, and a separate hash-bound
  111-entity review.
- Validate and apply the separately completed Northwind semantic review into a
  hash-bound approved registry, then compile one real structured semantic intent
  through Stage 5D and Stage 5A without executing its review-ready plan.
- Restore and integrity-check the official AdventureWorks 2025 backup in an isolated local read-only SQL Server database.

## Test Status

- Automated suite: 206 tests passed and 1 opt-in live-provider test skipped offline on 2026-07-15; latest run completed in 36.64 seconds.
- Isolated local Ollama smoke test: 1 passed in 18.82 seconds on 2026-07-15 with an 8,192-token context; it used no database or SQL execution.
- All 12 project-local skills passed the official skill validator on 2026-07-13.
- Internal link check: 103 checked, 0 broken on 2026-07-15.
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
- Northwind semantic state is approved and operational for deterministic local Stage 5D use, but its current catalog cannot express calculated revenue or a self-join employee-manager path; those remain explicit version-1 limitations.
- The local Ollama provider has only one passing contract smoke question. The 13-case Northwind answer authority and its 13/13 recorded offline result prove deterministic pipeline and answer behavior, not 13 live-model passes. No comparative live semantic/answer accuracy evidence, live narration provider, dynamic dispatch, concurrency evidence, or user interface exists yet.
- Stage 5B plan-to-execution drift still uses size and nanosecond modification time in ordinary queries. The dataset-backed evaluator additionally rechecks the complete database SHA-256 and every other authority hash before each Stage 5B call and after evaluation.
- Exact download provenance and licensing remain unconfirmed for Pubs and Contoso. Northwind provenance and MIT licensing are verified, but its technical relationship evidence is not promotion authority.
- Northwind's two `customer_customer_demo` relationships were explicitly accepted as official structural relationships without positive row coverage; semantic modeling must retain that limitation instead of presenting them as row-validated.
- AdventureWorks now has a compatible local restore runtime, but the SQL Server-to-DuckDB/Parquet export is not implemented; the Contoso recipe references external data and was not executed.
- A second SQL Server 2025 Evaluation instance (`DATAOPSLAB`) remains installed but stopped; project work should use the default Developer instance only when an explicitly authorized restore/export task requires it.

## Active Blockers

- `config/data_model/approved_keys.yml` and `config/data_model/approved_relationships.yml` remain empty by design.
- Broader canonical key and relationship approvals remain pending; the Product-specific state does not populate `approved_keys.yml` or `approved_relationships.yml`.
- No explicit apply contract or approved versioned representation exists yet for the candidate canonical Product snapshot.
- EDS cross-table analytics remain blocked because `approved_relationships.yml` is intentionally empty.
- Northwind is `semantic_catalog_approved` with 13 accepted exact relationships and 111 approved semantic entities. Its local Ollama intent-provider boundary is implemented and explicitly opt-in. All 13 exact plans and all four required expected-answer decisions per case are approved; the recorded offline evaluator passed 13/13 with zero blockers. Live-provider use remains explicitly outside that approval. Pubs remains pending provenance, license, schema, relationship, and benchmark-use review.
- AdventureWorks is restored and validated but remains pending reproducible export, schema review, relationship approval, and benchmark-use approval.

## Next Logical Milestone

Define the next bounded Phase 5 live-comparison contract and review its prompt minimization, case isolation, latency/token/memory evidence, failure handling, and non-persistence boundaries. The existing answer approval explicitly does not authorize live-provider use, so obtain separate invocation authority before running the 13 cases through loopback Ollama. Do not infer live quality from the 13/13 recorded baseline, enable dynamic dispatch, add live narration, upload, publish, or train a model.

## Last Verified Commit

`3536ddc` (`feat(benchmarks): approve northwind answer pack`).

## Last Updated

2026-07-15 by Codex after applying the Northwind per-case answer approval and passing the 13-case recorded offline benchmark.
