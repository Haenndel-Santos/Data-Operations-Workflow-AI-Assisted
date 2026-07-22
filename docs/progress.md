# Current Project State

## Objective

Turn local operational spreadsheets into validated analytical datasets and an approved ERP model, then let users ask governed analytical questions without requiring SQL knowledge.

## Current Stage

Four active tracks: Product Stage 3E.6 is `ready_for_canonical_state_review` with no canonical apply; AI roadmap Phases 0-4 passed their gates for Northwind and the selected local Ollama development provider; AI Phase 5.1 is approved and Phase 5.2 is active for the selected AdventureWorks 2025 holdout; and Backend Phase II completed increment 2.4 and its documented exit gate. The project owner froze the exact Phase 5 KPI thresholds and guardrails before holdout results, selected AdventureWorks, and authorized only its default-instance local read-only SQL Server export. The additive exporter, optional ODBC adapter, deterministic DuckDB/Parquet materialization, and composite relationship-candidate v2 contract are implemented and offline-tested. A real export attempted the authorized connection but stopped before staging because `MSSQLSERVER` is stopped and this process lacks local administrator authority to start it. CLI registration now contains 48 commands across ten coherent registrars while preserving all prior shapes. Relationship approval, semantic approval, pack design, answer collection, live provider use, provider selection, dynamic dispatch, live narration, and a user interface remain pending.

## Last Completed Milestone

On 2026-07-22, PR #17 was merged at `729658d`, the project owner approved its
exact thresholds and guardrails, selected AdventureWorks 2025, and separately
authorized Phase 5.2's local read-only export. The implementation adds a
fail-closed SQL Server exporter, optional `pyodbc` dependency, one additive CLI
command, version-2 composite relationship candidates, and backward-compatible
reference validation. The full offline suite passed with 284 tests and 2
expected live-provider skips; 113 internal links passed. The authorized real
connection attempt created no output or staging because the required default
SQL Server service is stopped.

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
- Dry-run a separately authorized dataset-backed live comparison without calling a provider or opening DuckDB.
- Evaluate an exact ordered pack sequentially through literal-loopback Ollama, Stage 5D, Stage 5A, and fixed-limit read-only Stage 5B only after immutable live authority and explicit invocation flags pass.
- Report literal and reviewed alias-normalized semantic/request accuracy separately while refusing to normalize tables, columns, functions, paths, filters, ordering directions, or limits.
- Persist sanitized latency, token, cost, RAM/GPU, component, pipeline, result, and control evidence without questions, provider responses, SQL, parameters, filter values, or rows.
- Repeat the exact approved development comparison through a separately authorized local soak with provider concurrency one, per-case resource/`STOP` gates, atomic cycle checkpoints, and aggregate per-case stability evidence.
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
- Stream an explicitly authorized default-instance local SQL Server database to
  deterministic DuckDB/Parquet only after exact `ONLINE`/`READ_ONLY`, integrated
  authentication, ODBC read-only, source-hash, primary-key, and output-drift
  gates; preserve composite foreign keys as pending candidates.
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
- Reuse one common streaming file SHA-256 implementation and one common
  standard analytics blocker implementation through backward-compatible module
  exports.
- Reuse common atomic new-directory publication and atomic text-checkpoint
  replacement while preserving consumer-specific retry schedules and errors.
- Build source SHA-256 maps through explicit existing-only or fully declared
  binding semantics without changing module-owned drift policies.
- Classify standard analytics blocker codes as separate additive metadata while
  preserving the original persisted code and blocker shape.
- Bind all 10 dynamic blocker call sites to reviewed provenance and expand the
  registry only through complete consumer families, while keeping exception
  behavior, free-text statuses, and Product's `artifact` blocker format
  separate.
- Classify the complete dataset-benchmark family, including exact provenance
  for two direct blocker-list reuses, without converting its live
  `provider_outcome` values into blocker codes.
- Classify natural-language translation and its offline evaluator as one
  complete family while keeping provider exceptions and result statuses as
  separately provenanced surfaces.
- Classify the synthetic answer evaluator while preserving inherited blockers,
  compound exception fallbacks, and pipeline statuses as distinct surfaces.
- Classify deterministic result presentation and recorded narration as one
  complete family while preserving exact evidence authority, sanitized
  exception mappings, and readiness statuses as distinct surfaces.
- Classify the two-phase analytics-session coordinator while preserving its
  human-review gate, nested stage statuses, exception fallbacks, and last valid
  checkpoint as distinct surfaces.
- Classify the static module-registry validator while preserving non-execution,
  disabled dynamic controls, the human gate, exception sanitization, and its
  validation status as distinct surfaces.
- Classify the bounded local Ollama soak while preserving separate authority,
  runtime status, stop-reason control text, exception fallbacks, and embedded
  lowercase blocker identifiers.
- Classify reference-dataset validation while preserving its local blocker
  format, exact human-review gate, status surfaces, catch behavior, and
  approved-relationship projection as distinct contracts.
- Classify Product canonical promotion while preserving its dynamic integrity
  tuple, `artifact` blockers, dry-run status, private data boundary, and
  explicit requirement for a separate apply contract.
- Classify Product materialization while preserving its candidate and persisted
  blocker formats, issue/source identifiers, preview status, action domains,
  exact applied-state gate, private data boundary, and preview-only authority.
- Project the proven four-field core from 23 existing run-result classes without
  changing inheritance, public return types, opaque status values, blocker
  records, artifact paths, or persisted evidence.
- Govern private local artifacts for cloud-first work by versioning only safe
  metadata and keeping raw sources, generated outputs, completed sensitive
  reviews, and secrets outside any repository that may become public.

## Test Status

- Automated suite: 276 tests passed and 2 opt-in live-provider tests skipped offline on 2026-07-20; latest run completed in 44.98 seconds on Windows.
- First GitHub Actions CI run: 276 passed and 2 opt-in live-provider tests
  skipped in 93.18 seconds on Windows/Python 3.13; 110 internal links checked,
  0 broken; pull-request diff check passed.
- CI documentation revalidation: 276 passed and 2 opt-in live-provider tests
  skipped in 50.58 seconds on Windows/Python 3.13; 111 internal links checked,
  0 broken; pull-request diff check passed.
- ERP modeling registration revalidation: 276 tests passed and 2 opt-in
  live-provider tests skipped in 46.37 seconds on Windows/Python 3.13; 111
  internal links checked, 0 broken; pull-request diff check passed.
- Product reference final validation: 276 tests passed and 2 opt-in
  live-provider tests skipped in 52.44 seconds on Windows/Python 3.13; 111
  internal links checked, 0 broken; pull-request diff check passed.
- Product publication final validation: 276 tests passed and 2 opt-in
  live-provider tests skipped in 46.73 seconds on Windows/Python 3.13; 111
  internal links checked, 0 broken; pull-request diff check passed.
- Model-documentation final validation: 276 tests passed and 2 opt-in
  live-provider tests skipped in 53.27 seconds on Windows/Python 3.13; 111
  internal links checked, 0 broken; pull-request diff check passed.
- Final analytics-operations registration validation: 276 tests passed and 2
  opt-in live-provider tests skipped in 93.00 seconds on Windows/Python 3.13;
  111 internal links checked, 0 broken; pull-request diff check passed.
- Post-merge `main` validation: GitHub Actions run `29778080598` completed
  successfully at exact merge commit `f038cc5` on 2026-07-20.
- Phase 5 selection-scope draft validation: GitHub Actions run `29920603444`
  passed at `701586f` with 276 tests, 2 opt-in live-provider skips, 113 valid
  internal links, and a clean exact pull-request diff from `f038cc5`.
- Phase 5.2 local implementation validation: 284 tests passed and 2 opt-in
  live-provider tests skipped in 47.92 seconds on Windows/Python 3.13; 113
  internal links checked, 0 broken; focused exporter/reference/taxonomy suite
  passed 43 tests.
- Backend Phase II run-result compatibility and registered-consumer suite: 238
  passed in 39.63 seconds.
- Backend Phase II existing-file binding consumer suite: 76 passed in 17.77 seconds.
- Backend Phase II declared-file binding consumer suite: 19 passed in 4.73 seconds.
- Isolated local Ollama smoke test: 1 passed in 39.48 seconds on 2026-07-15 with an 8,192-token context; it used no database or SQL execution.
- All 12 project-local skills passed the official skill validator on 2026-07-13.
- Internal link check: 110 checked, 0 broken on 2026-07-20.
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
- The local Ollama provider passed only 9/13 Northwind development cases end to end. Two cases were rejected, one missed a filter, and one scalar request mismatched alias/limit; all four were blocked before query execution. Literal request agreement was only 2/13, so alias normalization must remain visible. Northwind informed prompt/policy refinement and cannot serve as the final holdout. No selected provider, fresh holdout evidence, live narration provider, dynamic dispatch, concurrency evidence, or user interface exists yet.
- The completed soak stopped safely on available RAM after 6 hours 38 minutes. The prior samples cannot distinguish Ollama/model retention from Windows cache or unrelated processes, and one cycle lost publishable evidence to a transient `PermissionError`. Retry and process attribution are implemented but require a new bounded run to validate under sustained load. Repetition of Northwind cannot upgrade development evidence into a holdout or provider-selection result.
- Stage 5B plan-to-execution drift still uses size and nanosecond modification time in ordinary queries. The dataset-backed evaluator additionally rechecks the complete database SHA-256 and every other authority hash before each Stage 5B call and after evaluation.
- Exact download provenance and licensing remain unconfirmed for Pubs and Contoso. Northwind provenance and MIT licensing are verified, but its technical relationship evidence is not promotion authority.
- Northwind's two `customer_customer_demo` relationships were explicitly accepted as official structural relationships without positive row coverage; semantic modeling must retain that limitation instead of presenting them as row-validated.
- AdventureWorks has an offline-validated SQL Server-to-DuckDB/Parquet exporter,
  but the real dual export and reference evidence remain blocked until a local
  administrator starts `MSSQLSERVER`; the failed connection created no output
  or staging directory. The Contoso recipe references external data and was not
  executed.
- A second SQL Server 2025 Evaluation instance (`DATAOPSLAB`) remains installed but stopped; project work should use the default Developer instance only when an explicitly authorized restore/export task requires it.
- Backend Phase II has consolidated proven-equivalent file hashing, standard
  analytics blockers, two atomic-publication variants, and two source-binding
  absence semantics. Its error taxonomy covers 22 complete consumers; all
  dynamic sites, dataset-benchmark direct blocker-list reuses, and the Product
  materialization direct construction have provenance; 15 inherited blocker
  flows and 33 exception/fallback mappings are explicit. Four control-text
  surfaces, five local blocker formats, the reference approval projection, and
  three Product authority boundaries are separate. The source-only audit is
  complete, and 23 result classes expose the additive four-field run-result
  core. The consumer audit intentionally deferred runtime projection until a
  generic dispatcher or run recorder needs all four fields; CLI decomposition
  has moved all prior 47 registrations across ten coherent domain modules; the
  Phase 5.2 exporter is an additive 48th command. The final
  analytics-operations slices passed the complete automated Windows regression
  gate, and Backend Phase II is complete. Dispatch remains explicit and
  centralized. Free-text
  statuses remain intentionally separate. Binding comparison policies,
  deterministic `.building` workflows, and distinct blocker schemas must not
  be coerced without consumer and output characterization.

## Active Blockers

- `config/data_model/approved_keys.yml` and `config/data_model/approved_relationships.yml` remain empty by design.
- Broader canonical key and relationship approvals remain pending; the Product-specific state does not populate `approved_keys.yml` or `approved_relationships.yml`.
- No explicit apply contract or approved versioned representation exists yet for the candidate canonical Product snapshot.
- EDS cross-table analytics remain blocked because `approved_relationships.yml` is intentionally empty.
- Northwind is `semantic_catalog_approved` with 13 accepted exact relationships and 111 approved semantic entities. All 13 exact plans and expected-answer decisions are approved; the recorded evaluator passed 13/13. Separate live authority permitted one bounded loopback comparison, which passed 9/13 as development evidence. That authority does not extend to a changed prompt/provider, external service, holdout invocation, narration, upload, publication, or training. Pubs remains pending provenance, license, schema, relationship, and benchmark-use review.
- AdventureWorks is restored, validated, selected, and authorized for Phase 5.2,
  but remains pending two real reproducible exports, reference validation,
  schema review, relationship approval, and benchmark-use approval. The local
  default SQL Server service requires administrator authority to start.
- The Phase 5 thresholds and guardrails are approved and frozen. The missing
  bounded live intent/clarification evaluator is scoped but not implemented;
  live provider use remains not authorized.

## Next Logical Milestone

Start the default local `MSSQLSERVER` service with administrator authority, then
resume the already authorized Phase 5.2 operation. Produce current and
independent reproduction exports, verify exact source and derived hashes, add
the versioned AdventureWorks reference manifest, and run
`reference-dataset-validate`. Stop at `ready_for_relationship_review`; do not
approve any relationship or inspect any holdout model result in this increment.

Any later implementation must preserve all prior 47 command shapes plus the
additive Phase 5.2 command, `data_ops_lab.cli:main`, and the established hashing, blocker,
publication, binding, taxonomy, and run-result contracts. Keep execution and
result formatting in the existing domain modules, and keep the run-result
projection opt-in until a generic dispatcher or run recorder has a real
four-field use. Do not infer generic success from status, rename persisted
codes, add blocker fields, or combine module-specific blocker, artifact,
checkpoint, or authority semantics.

For cloud-first repository management, inventory local-only artifacts and commit
only safe manifests/hashes before any public visibility change; keep sensitive
files in a separate private store or encrypted artifact workflow.

## Last Verified Commit

`729658d` (`Merge pull request #17 from Haenndel-Santos/codex/phase-5-holdout-scope`).

## Last Updated

2026-07-22 by Codex after merging PR #17, recording the owner's Phase 5.1/5.2
authority, implementing and validating the read-only exporter, and stopping
safely on the unavailable administrator-controlled SQL Server service.
