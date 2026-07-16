# Decisions

## 2026-07-13 - Human Approval Is Authoritative

**Decision:** Completed human review decisions override automated recommendations.

**Context:** ERP key, relationship, and Product reference inference can be ambiguous or conflict with business knowledge.

**Alternatives:** Allow automation to replace or normalize human decisions; treat missing review as approval.

**Reason:** Human control is a core integrity requirement and is already enforced by domain guidance and preservation tests.

**Impact:** Conflicts must be reported, missing evidence remains blocked, and review files cannot be changed silently.

## 2026-07-13 - Candidates Stay Separate From Approvals

**Decision:** Candidate keys/relationships and approved keys/relationships remain in separate files and states.

**Context:** Source onboarding generates evidence-backed candidates but does not establish business approval.

**Alternatives:** Promote high-confidence candidates automatically.

**Reason:** Confidence metrics alone do not prove ERP semantics.

**Impact:** `approved_keys.yml` and `approved_relationships.yml` remain unchanged until an explicit, validated apply step.

## 2026-07-13 - Product Uses A Technical Primary Key

**Decision:** The target Product model uses generated `product_id` as the primary key. `part_nr_sku` remains the main business/search/matching reference and may become a unique business constraint only after cleanup and revalidation. `pd_ref_nr` remains optional.

**Context:** Product references include duplicates, missing values, textual references, and optional PD-style values.

**Alternatives:** Use `part_nr_sku` or `pd_ref_nr` as the global primary key.

**Reason:** A technical key preserves identity and import stability while reference reconciliation remains incomplete.

**Impact:** Product reference fields cannot be promoted to a final primary key by automation.

## 2026-07-13 - Repository Files Are Shared Agent Memory

**Decision:** Agents use `AGENTS.md`, the `docs/` state files, Git, code, and tests for continuity instead of private conversation history.

**Context:** Codex, Claude Code, and other agents may work on the project at different times.

**Alternatives:** Depend on chat summaries or maintain one monolithic project document.

**Reason:** Versioned, responsibility-specific files are auditable and resilient across tools.

**Impact:** Every versioned change session updates the handoff and consolidated progress state; durable decisions are appended here.

## 2026-07-13 - Orchestrator Coordinates, Modules Own Domain Logic

**Decision:** Orchestration selects, orders, validates, records, and resumes module work; specialized transformation and ERP logic stays in modules.

**Context:** The current default workflow is a fixed sequence and staged CLI commands are dispatched independently.

**Alternatives:** Centralize all logic in the CLI/workflow or let modules call one another implicitly.

**Reason:** Explicit coordination and module contracts reduce coupling and make partial execution testable.

**Impact:** Future orchestration work must avoid duplicating business logic and should add capabilities incrementally behind preserved entrypoints.

## 2026-07-13 - Ten Blocking Product Review Items Are Invalid

**Decision:** Treat the 10 final Product review blockers as invalid Product records. Record each final decision as `rejected`, exclude the record from the future target Product model, and do not create a technical Product identity for the five unmatched original records.

**Context:** The user confirmed that Product approvals had already been reviewed and explicitly directed that the remaining 10 blocking items be considered invalid. The affected issue IDs are `CONFLICT_001`, `CONFLICT_004`, `CONFLICT_005`, `UNMATCHED_ORIGINAL_001` through `UNMATCHED_ORIGINAL_005`, `DUPLICATE_REFNR_001`, and `DUPLICATE_REFNR_004`.

**Alternatives:** Retain five unmatched records with generated `product_id`; preserve the prior rejected decisions without notes; delete or edit raw Product source rows.

**Reason:** The explicit human decision is authoritative. `rejected` is the valid project decision value that represents exclusion; notes make the intended Product-level outcome auditable.

**Impact:** Final review validation is clean with 28 valid decisions, 18 approved and 10 rejected. No raw records were deleted, no reconciliation was applied, and approved model YAML files remain unchanged. A future Step 3E.4 apply contract must consume these rejections as target-model exclusions.

## 2026-07-13 - Step 3E.4 State Is Minimal And Explicit

**Decision:** Represent applied Product reconciliation decisions in a separate `product_reconciliation_state.yml`. Keep raw Product values and notes in ignored local outputs; version only hashes, the model contract, counts, review IDs, decisions, and target actions.

**Context:** The clean workbook is ready for application, but Product exclusions need an auditable representation that does not mutate sources or overload the key and relationship approval schemas.

**Alternatives:** Edit raw Product rows; place Product exclusions in `approved_keys.yml`; commit full workbook values; update canonical model files directly without a decision digest.

**Reason:** A separate minimal state preserves privacy and ownership boundaries, supports idempotency, and makes the exact human-decision set verifiable before downstream model construction.

**Impact:** `apply-product-refnr-decisions` defaults to dry-run, revalidates its input, blocks unresolved context, and requires `--apply` for the state write. The real dry-run maps 10 rejected items to logical target-model exclusions. The representation remains unapplied until explicitly approved.

## 2026-07-13 - Step 3E.4 Product State Is Approved And Applied

**Decision:** Apply the documented `product_reconciliation_state.yml` representation using the validated Product workbook and decision digest `f2a7f0bdf338d8733ce03d4b82bfe0056e7e06d47ad157b36a059a9e1c4c0183`.

**Context:** The user reviewed the dry-run outcome and explicitly instructed Codex to proceed. The input contains 28 clean decisions: 18 approved and 10 rejected.

**Alternatives:** Keep the state at dry-run only; alter the state schema; apply decisions directly to raw files or a database.

**Reason:** The separate minimal state had already passed contract, preservation, privacy, rejection, and idempotency tests and matched the authoritative human decisions.

**Impact:** Product reconciliation state is now versioned and authoritative for downstream Product modeling. Rejected records map to logical exclusion and receive no target Product identity. Raw data, review workbooks, `approved_keys.yml`, and `approved_relationships.yml` remain unchanged.

## 2026-07-14 - Product Materialization Fails Closed

**Decision:** Product materialization v1 generates a local preview only when every retained exception has materializable source evidence. Exclusion takes precedence for repeated source identifiers, technical IDs are deterministic UUID5 values bound to the applied digest and source hashes, and no partial preview is written when blockers exist.

**Context:** Several review issues can reference the same source row, and applied human approval does not by itself create missing source values. The real applied state includes three approved `Product_ref.nr` rows that are completely empty.

**Alternatives:** Generate arbitrary identities for empty rows; preserve approvals but omit blocked rows from an otherwise partial preview; infer references from row position; overwrite prior generated evidence.

**Reason:** Those alternatives would silently override human decisions, invent Product records, or create an apparently complete but incomplete target model.

**Impact:** `product-materialization-preview` validates exact applied state, source-row range, same-row conflict evidence, corrected references, exclusions, IDs, and output idempotency. The real run is blocked pending human clarification for three issue IDs and produced no Product preview.

## 2026-07-14 - Empty Product RefNr Rows Are Invalid

**Decision:** Classify `UNMATCHED_REFNR_006`, `UNMATCHED_REFNR_008`, and `UNMATCHED_REFNR_013` as `rejected`. Exclude `refnr_row_1731`, `refnr_row_1733`, and `refnr_row_1739` from the target Product model and do not assign Product identities to those empty records.

**Context:** The authoritative `Product_ref.nr` rows are completely empty, so the prior approvals could not supply a corrected reference, business reference, attributes, or defensible identity. The human owner explicitly instructed Codex to proceed with treating the rows as invalid.

**Alternatives:** Supply corrected source evidence; generate arbitrary identities; omit the rows without changing the approved decision state.

**Reason:** Explicit human authority resolves the conflict without inventing data. Rejection uses the existing reviewed decision and application contracts and remains auditable and reversible.

**Impact:** The applied state now contains 28 decisions, 15 approved and 13 rejected, with digest `4f14e2cb265d9729263ab5bd572a41365f4bbbceec7e007d930b539faa5fe260`. The prior state is preserved under `config/data_model/history/`. Product materialization is no longer blocked and produces a 1,733-row local preview with 13 exclusions.

## 2026-07-14 - Canonical Product Promotion Is Hash-Bound And Dry-Run First

**Decision:** Require a local, hash-bound promotion plan before any canonical Product state can be proposed for application. Step 3E.6 validates the complete Step 3E.5 package against applied reconciliation state and has no apply mode.

**Context:** The resolved Product preview is complete, but it contains private row values and does not itself define how canonical state should be versioned or applied.

**Alternatives:** Treat the preview as approved canonical state; copy Product rows directly into versioned configuration; mutate `canonical_tables.yml`; add database import behavior to the promotion check.

**Reason:** A separate dry-run checkpoint proves snapshot integrity and preserves the human approval boundary without exposing private values or combining model governance with operational writes.

**Impact:** `product-canonical-promotion-plan` records artifact hashes, schema, counts, and validation results only. The real plan is `ready_for_canonical_state_review` with 1,733 candidate rows, 13 exclusions, and zero blockers. No canonical state, approved key, approved relationship, database, import, migration, or synchronization was changed.

## 2026-07-14 - AI Produces Structured Intent, Not Executable SQL

**Decision:** Place a versioned structured analytics request between natural-language interpretation and SQL. Deterministic local code must resolve the DuckDB catalog, enforce approved relationships, quote identifiers, parameterize values, and produce a dry-run plan before any future execution step.

**Context:** The product direction now includes conversational analysis for users without SQL knowledge. Direct execution of model-generated SQL would weaken safety, reproducibility, privacy, and provider independence.

**Alternatives:** Execute raw SQL returned by an LLM; build a fixed library of natural-language templates; postpone the safety boundary until the UI exists.

**Reason:** A narrow intermediate representation can be tested offline, blocks DDL/DML by construction, preserves human relationship authority, and lets different AI models target the same backend contract.

**Impact:** Stage 5A adds `analytics-query-plan` with no execution mode. EDS remains private local evaluation evidence. AdventureWorksDW2019 and Chinook are candidate benchmark packs only after provenance, license, checksum, schema, and relationship review; no public dataset was downloaded.

## 2026-07-14 - Benchmark SQL Is Parsed, Never Executed

**Decision:** Store user-supplied benchmark sources and derived datasets outside Git, version their checksums and approval state, and convert supported T-SQL by parsing only table definitions and local insert rows. Treat extracted foreign keys as unapproved candidates.

**Context:** The user supplied Northwind, Pubs, AdventureWorks 2025, and Contoso sample files and authorized their relocation and conversion to efficient local formats. The SQL scripts contain destructive and operational statements, the AdventureWorks backup needs an unavailable SQL Server runtime, and the Contoso recipe references external Azure data.

**Alternatives:** Execute the scripts against SQL Server; commit raw/derived datasets; infer approval from dataset presence; connect to the Contoso external source; discard unsupported files.

**Reason:** Restricted parsing produces reproducible DuckDB and Parquet evidence without executing untrusted SQL, connecting externally, or conflating local conversion with provenance, licensing, relationship, training, or publication approval.

**Impact:** Northwind and Pubs are locally converted and hash-validated. AdventureWorks and Contoso remain raw-only. Exact source/license confirmation, schema review, relationship approval, and benchmark expected-answer design remain pending.

## 2026-07-14 - SQL Server Is A Temporary Read-Only Restore Bridge

**Decision:** Use the default local SQL Server 2025 Developer instance only as an explicitly authorized compatibility bridge for restoring and exporting public SQL Server sample backups. Set restored benchmark databases to read-only, keep SQL services manual, and retain DuckDB/Parquet as the target analytical formats.

**Context:** The user installed SQL Server and authorized local configuration and AdventureWorks restoration. The supplied backup is byte-identical to Microsoft's official MIT-licensed `AdventureWorks2025.bak` release. `RESTORE VERIFYONLY`, restoration, read-only enforcement, and `DBCC CHECKDB` all succeeded on build `17.0.4055.5`.

**Alternatives:** Depend permanently on SQL Server for analytics; execute the backup against an external server; leave the dataset blocked; treat declared foreign keys as approved relationships.

**Reason:** A temporary local restore bridge preserves the backup's relational metadata and enables a later reproducible export without making SQL Server an application dependency or weakening relationship governance.

**Impact:** `AdventureWorks2025` is locally available as a read-only database with 71 tables, 20 views, 90 declared foreign keys, and 760,167 aggregate rows. Export, schema review, relationship approval, benchmark acceptance, model training, and external upload remain pending. The separate `DATAOPSLAB` Evaluation instance is stopped and is not a project dependency.

## 2026-07-14 - Reviewed Plans Are Recompiled Before Execution

**Decision:** Keep query planning and execution as separate Stage 5A/5B modules. Stage 5B must recompile the structured request, exactly match the reviewed plan including catalog and database-file fingerprint, reopen DuckDB read-only, and enforce explicit resource and result budgets before returning data.

**Context:** Stage 5A intentionally omits filter values from persisted plans. A later process therefore cannot safely execute from plan YAML alone, and accepting SQL from the plan or caller would reopen the raw-SQL boundary.

**Alternatives:** Persist private parameter values in the plan; accept SQL plus parameters directly; execute immediately during planning; trust a reviewed plan after request, approval, catalog, or database drift.

**Reason:** Deterministic recompilation preserves parameter privacy and the structured-request allowlist while exact comparison protects the human-reviewed evidence. Read-only mode, disabled external access, interruption, isolated temporary spill, and bounded rows/bytes keep execution local and fail closed.

**Impact:** `analytics-query-execute` can produce a hash-bound CSV and audit manifest or blockers without partial results. Byte-identical reruns reuse evidence and divergent reruns are refused; row order still follows SQL semantics and requires explicit `order_by` when it matters. The command does not authorize EDS use, candidate relationships, external databases, natural-language translation, or result narration. Database drift uses size and nanosecond modification time for efficiency; cryptographic dataset snapshot identity remains future work.

## 2026-07-14 - Semantic Ambiguity Is Preserved For Clarification

**Decision:** Keep Stage 5C semantic validation separate from human approval and future natural-language translation. Normalize business terms into an index, return every candidate for ambiguous terms, and require all relationship-path hops to match already approved physical relationships.

**Context:** Business words such as sales, customer, value, and order can legitimately refer to tables, dimensions, measures, or paths. Automatically choosing one would turn uncertain language into an authoritative query plan without evidence.

**Alternatives:** Select the first or highest-ranked term automatically; treat every ambiguity as a catalog blocker; import candidate ERP relationships into semantic paths; couple semantic validation directly to Stage 5A query compilation.

**Reason:** Explicit `resolved`, `ambiguous`, `unknown`, and `catalog_blocked` states let a future adapter request clarification while preserving stable business IDs and the existing approval boundary. Ambiguity itself is useful metadata, not a technical validation failure.

**Impact:** `analytics-semantic-catalog` produces `ready_for_semantic_review` evidence only. Semantic definitions, adapter use, EDS queries, candidate relationships, and model-generated requests remain unauthorized until separate contracts are reviewed and approved.

## 2026-07-14 - Semantic Approval Requires Complete Hash-Bound Human Review

**Decision:** Bind every semantic review to the exact compiled Stage 5C catalog by SHA-256. Require one explicit decision and note for every semantic entity and ambiguity. Keep approval validation as dry-run by default; write a versioned registry only with `--apply`, and require separate replacement authority for an existing different registry.

**Rationale:** Technical schema validity is not business-semantic authority. Complete, hash-bound review prevents stale or partial decisions from authorizing the natural-language adapter. Blocking rejected entities forces candidate revision and technical revalidation instead of silently creating an inconsistent approved subset.

**Alternatives:** Treat technical validation as approval; approve the catalog as one opaque unit; silently omit rejected entities; infer ambiguity resolution; overwrite the existing registry.

**Impact:** The review template grants no authority. Pending, rejected, missing, duplicate, malformed, or stale decisions block application. A human may preserve an ambiguity for clarification or select one exact candidate. Approved state never promotes candidate physical relationships. No real catalog is approved merely because the contract exists.

## 2026-07-14 - Stage 5D Compiles Approved Semantic Intent Without SQL

**Decision:** Implement Stage 5D first as a deterministic offline compiler for a supplied structured semantic intent. Require applied approved semantic state, resolve every term through its approved term index, copy aggregates and physical mappings only from approved entities, and expand only approved semantic relationship paths. Emit the existing Stage 5A request or separate clarification/blocker evidence.

**Rationale:** Free-text model invocation and deterministic authorization are different responsibilities. Establishing the local compiler first makes provider output testable, prevents a model from choosing SQL, aggregates, columns, or joins, and preserves Stage 5A/5B as the physical planning and execution boundaries.

**Alternatives:** Call an LLM and execute its SQL; let the model emit physical Stage 5A fields directly; infer an ambiguous target from field context; merge semantic translation into query planning; wait for a UI before defining the boundary.

**Impact:** `analytics-semantic-adapter` accepts no raw SQL or physical joins, uses no model API or database, and never auto-selects ambiguity. `ready_for_query_plan` still requires Stage 5A live-catalog and relationship validation. Questions and filter values persist only in the local generated request; control evidence omits them. No real dataset becomes authorized by this implementation.

## 2026-07-14 - Model Translation Is Provider-Neutral, Minimized, And Opt-In

**Decision:** Put model-provider translation behind a narrow injected protocol. Send only the local question, minimized approved semantic metadata, and the response contract. Require explicit per-invocation network opt-in, sanitize provider errors, avoid automatic retries, and pass every accepted response through the deterministic Stage 5D semantic adapter.

**Rationale:** Provider choice, network disclosure, semantic authorization, and query execution are separate concerns. The project needs a testable translation boundary before credentials or a vendor SDK are introduced. Minimization reduces unnecessary disclosure, while recorded responses make the default suite deterministic and offline.

**Alternatives:** Add an OpenAI-specific dependency immediately; send the complete approved state or database schema; let the provider replace the question; persist provider errors and prompts verbatim; retry automatically; treat schema-shaped provider output as authorized.

**Impact:** `analytics-nl-translate-recorded` validates local recorded responses without inference or network access. Future live providers must implement the protocol, honor timeout, require explicit network authorization, and add isolated online tests. Physical mappings, approval identity, fingerprints, table rows, and databases are excluded from provider context. No live provider is currently implemented or authorized.

## 2026-07-14 - Synthetic Translation Evaluation Is Contract Evidence

**Decision:** Evaluate Stage 5D first with a versioned synthetic pack replayed through the real provider boundary and deterministic semantic adapter. Require exact governed outcomes for status, enumerated accepted intents, blockers, and clarification terms, while omitting questions and provider responses from persistent evaluation evidence.

**Rationale:** The project needs measurable translation regressions before selecting a provider, but recorded responses cannot establish model accuracy. A provider-independent pack can prove safety, ambiguity, failure, and compatibility behavior offline without credentials, network disclosure, real data, or a second interpretation path.

**Alternatives:** Select a live provider before defining metrics; compare generated YAML as text; accept fuzzy intent similarity; persist prompts and responses in reports; treat successful recorded cases as proof of model quality.

**Impact:** `analytics-translation-evaluate` distinguishes `passed`, expectation `failed`, and contract `blocked` states and covers exact/equivalent intents, clarification, hallucination, unsafe output, timeout, and failure. It measures deterministic backend behavior only. Live-provider choice, credentials, cost, retention, online testing, and dataset-backed expected answers remain separate authorization and implementation decisions.

## 2026-07-14 - Expected Requests Gate Synthetic Answer Execution

**Decision:** Build the initial Stage 5E expected-answer harness from a versioned synthetic pack. Materialize DuckDB only from structured allowlisted types and values, require the Stage 5D request to exactly match the expected request before planning, then require normal Stage 5A planning and Stage 5B revalidation before comparing exact CSV and control totals.

**Rationale:** An answer benchmark must measure the complete governed pipeline without turning generated intent into execution authority. The exact expected request catches semantic translation drift before SQL planning, while the existing planner and executor preserve catalog, relationship, raw-SQL, resource, and read-only controls.

**Alternatives:** Execute every schema-valid provider response; store setup SQL in the pack; compare unordered result sets; bypass Stage 5A review artifacts; call a narrator before validating results; begin with EDS or an unapproved benchmark.

**Impact:** `analytics-answer-evaluate` covers grouped, filtered, no-row, and null-filter synthetic cases with fixed conservative limits. Input packs contain synthetic case content, while generated evaluation evidence omits it and runtime databases/results are discarded. The harness is not approval for real datasets, live providers, benchmark relationships, business answers, or narration.

## 2026-07-14 - Dataset Benchmarks Require Separate Hash-Bound Approval

**Decision:** Before any dataset-backed Stage 5E execution, require a verified
immutable local DuckDB manifest, approved semantic-state and relationship
hashes, a candidate pack containing reviewed expected requests/results, and a
separate human approval bound to every source by SHA-256. Exact comparison is
the default; numeric tolerance must be explicit, finite, typed, and reviewed per
numeric result column.

**Rationale:** Local availability or successful conversion does not establish
provenance, license, semantic correctness, relationship authority, expected
answer authority, or data-use consent. Keeping these authorities separate makes
drift visible and prevents a dataset manifest or generated pack from approving
itself.

**Alternatives:** Treat converted datasets as approved benchmarks; store approval
inside the candidate pack; use filenames or modification times as identity;
allow global floating-point tolerance; inspect or query the database during the
binding step; let offline approval authorize live providers, upload, or model
training.

**Impact:** `analytics-dataset-benchmark-validate` performs a dry-run contract
check and hashes the database as an opaque file without opening or querying it.
It may report `ready_for_offline_evaluation`, but it does not execute cases,
approve a live provider, authorize external disclosure or training, or make any
current EDS/public dataset an approved benchmark.

## 2026-07-14 - Benchmark Approval Requires Complete Per-Case Review

**Decision:** Generate dataset benchmark approval only from a completed human
review bound to the exact candidate sources. Require every case to approve its
recorded response, expected request, expected result, comparison policy, and
notes. Require local offline scope approval while live-provider, upload, and
training scopes remain explicitly not authorized.

**Rationale:** Aggregate approval booleans alone do not prove that every expected
answer was inspected. Per-case decisions expose omissions and conflicts, while
the review hash and normalized decision digest preserve traceability without
copying questions, responses, expected rows, or notes into approval evidence.

**Alternatives:** Let the candidate pack approve itself; accept one global
checkbox; copy all case content into generated evidence; permit pending or
rejected cases; overwrite a prior approval; combine approval with benchmark
execution.

**Impact:** `analytics-dataset-benchmark-review` prepares pending authority and
`analytics-dataset-benchmark-approval` validates it in dry-run by default.
`--apply` writes only an explicit immutable approval path. No current real
dataset was reviewed or approved, and dataset-backed execution remains absent.

## 2026-07-14 - Dataset Evaluation Reuses Governed Planning And Execution

**Decision:** Execute an approved dataset-backed pack only by replaying recorded
Stage 5D responses, requiring exact reviewed Stage 5A requests, rebuilding plans
with Stage 5A, rechecking every immutable authority hash immediately before
Stage 5B, and using Stage 5B fixed-limit read-only execution. Compare exact
results by default and apply numeric tolerance only to explicitly reviewed
columns.

**Rationale:** Approval should not create a second query engine or turn expected
answers into SQL authority. Reusing the existing stages preserves semantic,
relationship, catalog, parameterization, drift, resource, and external-access
controls while making dataset-backed results measurable.

**Alternatives:** Execute SQL stored in the pack; skip exact request comparison;
trust an earlier hash check; compare every number approximately; persist actual
rows or SQL in evaluator evidence; use a live provider; begin with EDS or an
unapproved public dataset.

**Impact:** `analytics-dataset-benchmark-evaluate` reports `passed`, expectation
`failed`, or contract `blocked` with separate exact/tolerance metrics. Runtime
case artifacts are temporary and persistent evidence omits content. The
implementation proves the controlled executor on synthetic fixtures only; no
real dataset, provider, upload, training, or narration is authorized.

## 2026-07-14 - Result Facts Remain Authority Over Narration

**Decision:** Revalidate exact Stage 5B evidence into a bounded deterministic
facts package before any explanation step. Require every narration claim to
cite supplied fact IDs, preserve cited numeric tokens exactly, and include row,
no-row, and preview-truncation controls. Keep narration non-authoritative and
provide only a recorded offline CLI provider.

**Rationale:** User-facing prose is useful only after result integrity is fixed.
Separating deterministic facts from narrative text prevents a model from
becoming query or numeric authority and makes omitted caveats, altered values,
source drift, and unsupported citations mechanically visible.

**Alternatives:** Send raw database access or SQL to a narrator; let prose
recalculate aggregates; accept uncited answers; persist all result rows in a
control manifest; select a live provider before defining the grounding
contract; treat fluent prose as evidence.

**Impact:** `analytics-result-present` creates a hash-bound local preview and
facts package without database access. `analytics-result-narrate-recorded`
validates exact presentation/facts bindings and cited recorded prose without
network access. The Stage 5B CSV remains authoritative; semantic truth beyond
mechanical citations still requires human or benchmark evaluation.

## 2026-07-14 - Analytics Sessions Use Two Immutable Phases

**Decision:** Coordinate the recorded local analytics path as separate prepare
and resume phases. Preparation may reach a review-ready Stage 5A plan but cannot
execute it. Resume requires a completed human review bound to both the exact
preparation checkpoint and reviewed plan SHA-256 before calling Stage 5B.

**Rationale:** A single command that generates and immediately executes its own
plan would make `ready_for_execution_review` equivalent to approval. Separate
immutable outputs preserve the human checkpoint, permit safe retries, and let
the coordinator reuse specialized stage contracts without absorbing their
logic.

**Alternatives:** Auto-approve newly generated plans; add a bypass flag; mutate
one session manifest in place; duplicate query/result validation in the
orchestrator; introduce a generic dependency engine before one workflow has
tested state semantics.

**Impact:** `analytics-session-prepare-recorded` stops at review or
clarification. `analytics-session-resume-recorded` validates exact authority and
records the last valid checkpoint through execution, presentation, and recorded
narration. Generic orchestration, live providers, UI, and real-data authority
remain separate future work.

## 2026-07-14 - Module Registry Validation Is Static And Non-Executing

**Decision:** Describe the two recorded analytics-session phases in a versioned
declarative registry and validate entrypoint source, exact parameter names,
tests, dependencies, cycles, workflow order, failure policies, capabilities,
and the human execution gate without importing, calling, or dynamically
dispatching registered entrypoints.

**Rationale:** A contract registry is useful before it becomes an execution
engine. Static inspection and disabled controls expose drift and unsafe workflow
changes without giving configuration new authority over review, database,
provider, or execution boundaries.

**Alternatives:** Dispatch directly from the first registry; import every module
during discovery; infer signatures at runtime; combine registry validation with
generic concurrency, partial runs, or review completion.

**Impact:** `analytics-module-registry-validate` writes immutable dry-run
evidence for 8 modules, 2 workflow phases, and 5 stages. Dynamic execution,
concurrency, network access, review auto-approval, and registry coverage of the
non-analytics pipelines remain disabled or pending.

## 2026-07-14 - Optimize Schema Candidates Only After Synthetic Measurement

**Decision:** Establish an isolated synthetic before/after baseline, then route
the measured schema/key output path through Arrow metadata and local DuckDB
aggregations while preserving the exact existing schema, candidate-key, and
candidate-relationship contract. Keep the legacy DataFrame functions callable.

**Rationale:** The original path loaded every Parquet table at once and built
Python sets for cross-table overlap. The fixed 3-table workload identified it
as both the peak-memory and dominant-runtime stage. Pushdown reduces retained
DataFrames without changing candidate authority or requiring real data.

**Alternatives:** Optimize an unmeasured stage; set performance thresholds from
one machine; use EDS or public benchmarks; rewrite all profiling/cleaning/schema
logic together; change key expectations to match a faster implementation.

**Impact:** Exact equivalence tests cover nulls, NaN, empty tables, repeated
line references, and PK/FK candidates. On identical synthetic inputs, schema
peak process memory fell from 184,971,264 to 134,606,848 bytes and runtime fell
from 35.096404 to 0.353394 seconds. Outputs remain candidates; no approved key,
relationship, data, or source file changed.

## 2026-07-15 - Reference Dataset Evidence Does Not Approve Relationships

**Decision:** Validate a reference dataset through fixed official provenance,
license, source/artifact hashes, independent conversion equivalence, read-only
schema/key/relationship profiling, and explicit permitted-use scopes. Keep the
exact relationship review as a separate human-authored artifact bound to both
the reference-manifest and candidate hashes.

**Rationale:** An official foreign-key declaration plus zero observed orphans is
strong technical evidence, but it is not a human modeling decision. Empty
tables can also produce zero-orphan results without positive row coverage.
Separating evidence from authority lets Phase 2 progress without turning a
successful profile, broad workflow authorization, or generated review template
into silent relationship promotion.

**Alternatives:** Treat every declared FK as approved; infer approval from the
project owner's general implementation authorization; require identical DuckDB
binary hashes across independent conversions; skip database profiling and trust
only conversion metadata; combine local benchmark scope with upload/training
permission.

**Impact:** `reference-dataset-validate` fails closed on provenance, license,
artifact, reproduction, scope, schema, key, relationship, and exact-review
drift. It opens DuckDB only read-only after preflight, emits immutable technical
evidence and a pending review, and reports `ready_for_semantic_modeling` only
after every exact candidate is accepted or rejected by a completed review.
Northwind has now reached `ready_for_semantic_modeling` after the project owner
accepted all 13 exact candidates. Version 2 derives an approved registry from
that completed review while keeping the review as authority; external upload,
publication, and model-parameter training remain not authorized.

## 2026-07-15 - Approve Northwind Semantics Without Expanding External Authority

**Decision:** Accept the complete Northwind semantic package as presented in the
grouped review guide: 1 dataset, 13 table grains, 60 dimensions, 19 direct-
column measures, and 18 many-to-one relationship paths. Bind all 111 approved
decisions to the exact compiled catalog, validate in dry-run mode, and apply the
resulting registry for deterministic local Stage 5D adapter use.

**Rationale:** Northwind had already passed provenance, license, conversion,
schema, relationship, and local-use gates. The semantic candidate preserved
those authorities, compiled with zero blockers/ambiguities, exposed its grain,
currency, fanout, empty-table, snapshot, and self-join limitations, and received
explicit project-owner approval after that review was presented.

**Alternatives:** Treat the prior physical relationship approval as semantic
approval; approve only an opaque aggregate status without entity decisions;
leave the completed package unapplied; add calculated revenue or a manager
self-join outside the version-1 contract; let semantic approval authorize a live
provider or expected answers.

**Impact:** `config/analytics/approved_semantic_catalog.yml` is now the first
applied real semantic registry. It is bound to the candidate, compiled physical
catalog, approved relationships, completed review, and decision digest. A real
structured intent reached Stage 5A `ready_for_execution_review` without SQL
execution. Live-provider use, network disclosure, expected-answer authority,
upload, publication, training, and database writes remain separate decisions.

## 2026-07-15 - Select Loopback Ollama For The First Live Semantic Provider

**Decision:** Use the project owner's local Ollama `gpt-oss:20b` runtime as the
first live Stage 5D semantic-intent provider. Require a literal loopback HTTP
origin, disable proxy routing, require explicit per-invocation socket authority,
use English prompts and approved semantic entity IDs, bound context/output/time,
sanitize failures, and preserve the recorded provider as the offline default.

**Rationale:** The selected model is already installed and runs without an API
credential or hosted-token charge on the available workstation. The existing
provider-neutral boundary and deterministic semantic adapter can constrain its
role to interpretation while keeping approved relationships, physical mapping,
SQL planning, and execution authoritative in local code. Literal loopback
validation plus proxy exclusion prevents an apparently local configuration from
silently becoming external disclosure.

**Alternatives:** Call a hosted OpenAI or Anthropic model; accept `localhost`, a
LAN address, or arbitrary OpenAI-compatible base URL; add a vendor SDK; allow
automatic retries; let the model emit physical SQL or joins; replace the
recorded provider in the default suite; enable live model dispatch from the
static module registry.

**Impact:** `analytics-nl-translate-ollama` calls only
`http://127.0.0.1:<port>` or `http://[::1]:<port>` after `--allow-network`, sends
the minimized semantic context, and constrains each semantic field to approved
IDs of the correct kind through JSON Schema. Offline tests mock the HTTP
transport; an environment-gated live test passed one English Northwind question
without DuckDB access or SQL execution. Phase 4 is complete for this local
development boundary. Phase 5 model accuracy, reviewed expected answers, live
narration, concurrency, external providers, upload, publication, training, and
automatic execution remain separate decisions.

## 2026-07-15 - Expected-Answer Collection Requires Exact Plan Review

**Decision:** Before collecting any expected result from a real benchmark,
compile every versioned English question and recorded semantic intent through
Stage 5D and Stage 5A, then require a separate aggregate human review bound to
the complete preparation manifest and every exact plan SHA-256. Treat this as
answer-collection authority only; review the resulting expected requests,
typed results, and comparison policies again through the existing dataset-pack
approval workflow before evaluation.

**Rationale:** A human cannot review an expected answer until it exists, but
creating that answer requires a real query. The generic authorization to start
Phase 5 is not exact plan approval. Adding a narrow pre-execution checkpoint
resolves this ordering dependency without bypassing Stage 5B review or letting
query execution approve the expected values it produces.

**Alternatives:** Query Northwind directly while drafting the pack; treat broad
Phase 5 authorization as approval for unknown plans; calculate answers outside
the governed planner/executor; skip the second per-case expected-answer review;
or use live Ollama responses while establishing the gold pack.

**Impact:** `analytics-dataset-benchmark-answer-prepare` validates a bounded
design, immutable dataset authority, approved semantics and relationships, then
creates recorded Stage 5D and exact Stage 5A evidence for every case. The first
Northwind design produced 13 review-ready plans and zero blockers without
Stage 5B, table-row reads, answers, a live provider, or network access. Expected
answers, local read-only collection, live-model comparison, narration, upload,
publication, and training remain unapproved until their exact later gates.

## 2026-07-15 - Materialize Candidate Answers Sequentially And Preserve Final Review

**Decision:** Record the project owner's approval of all 13 exact Northwind
plans as a versioned completed execution review authorizing only local read-only
answer collection. Validate that authority before table-row access, recheck all
immutable hashes before and after every case, execute Stage 5B sequentially
with fixed limits, and keep the resulting pack `candidate_for_review` until the
existing separate per-case benchmark approval workflow is complete.

**Rationale:** Plan correctness and expected-value correctness are distinct
human decisions. The first gate authorizes known queries; it cannot make their
outputs gold answers. Sequential execution reduces workstation pressure and
makes the exact case order auditable, while normal Stage 5B recompilation and
plan matching preserve the established no-raw-SQL boundary.

**Alternatives:** Execute cases concurrently; let a broad Phase 5 approval
replace exact decisions; call Ollama while constructing gold answers; write a
pack directly from ad hoc SQL; auto-approve values that match execution control
totals; discard a blocked run; reject the governed approved-relationship
projection because it includes versioned authority metadata.

**Impact:** `analytics-dataset-benchmark-answer-materialize` now requires the
completed scope and per-case decisions, accepts both the legacy minimal and the
validated governed relationship-registry shapes, and writes no pack on a
blocker. The first preserved run completed all queries but blocked pack output
when the older final validator rejected legitimate registry metadata. After a
compatible authority-shape fix and focused regression test, a new run completed
all 13 cases with zero blockers and wrote a hash-bound candidate pack. A second
pending review now requires independent decisions for the recorded response,
expected request, expected result, and comparison policy of every case. Live
provider use, upload, publication, training, and benchmark evaluation remain
not authorized.

## 2026-07-15 - Bind Live Benchmark Runs Separately And Preserve Holdout Integrity

**Decision:** Evaluate an approved dataset pack through local Ollama only with a
separate additive authorization bound to every immutable source, ordered case,
exact provider/prompt configuration, timeout, and execution control. Require
dry-run preflight, explicit live and loopback-network flags, sequential cases,
authority rehashing, Stage 5A/5B controls, and minimized non-content evidence.
Permit canonicalization only for aliases already approved in the expected
request and only after every non-alias field matches. Report literal and
alias-normalized accuracy separately.

**Rationale:** Offline recorded answers prove the deterministic pipeline but not
model interpretation. A live comparison exposes local model quality, latency,
tokens, and workstation pressure, while a separate cryptographic authority
prevents an answer approval from silently expanding into provider use. Alias
spelling is not a semantic decision when the resolved table, columns, function,
paths, filters, ordering, and limits are identical, but hiding literal drift
would make model quality look better than measured.

**Alternatives:** Reuse offline approval as live authority; accept external or
LAN endpoints; execute model-generated SQL; normalize tables, columns, filters,
limits, or relationship paths; run cases concurrently; persist questions,
responses, SQL, or rows; keep tuning against Northwind and call the same pack a
holdout; treat a partial live pass as provider selection.

**Impact:** `analytics-dataset-benchmark-evaluate-ollama` now dry-runs without
provider/database access and live-runs only through literal loopback Ollama. The
authorized Northwind v3 development run passed 9/13 end to end; two provider
rejections, one filter mismatch, and one scalar alias/limit mismatch were
blocked before query execution. The run cost USD 0 in hosted API charges and
recorded latency, token, RAM, and GPU evidence without case content. Because the
prompt and alias policy were refined using Northwind, its pack is now a
development set. Phase 5 provider selection requires thresholds fixed in
advance and a fresh separately reviewed holdout. External providers, upload,
training, narration, publication, concurrency, dynamic dispatch, and production
use remain unapproved.

## 2026-07-15 - Run Local Endurance Sequentially Under Resource Guards

**Decision:** Permit one bounded unattended repetition of the already approved
Northwind development comparison through local loopback Ollama and read-only
DuckDB. Bind duration, maximum cycles, cooldown, provider concurrency, resource
limits, technical-error threshold, and `STOP` behavior in a separate additive
authorization. Fix model-call concurrency at one and checkpoint safe aggregate
evidence after every cycle.

**Rationale:** The installed 20B model is approximately 13 GB while the RTX 3070
Ti has 8 GB VRAM. A canary used about 7.3 GB VRAM and split execution between
CPU and GPU. Concurrent requests would add context/cache and system-memory
pressure rather than provide useful parallel speedup. Sequential repetition
still uses GPU tensor parallelism and can measure sustained quality variation,
latency, tokens, memory, temperature, and failure behavior without a hosted API.

**Alternatives:** Run two or more model requests concurrently; restart Ollama
with experimental parallel settings; leave the process unbounded; train or
fine-tune model parameters; use a hosted provider; run the default pytest suite
in a loop; interpret repeated development cases as holdout evidence.

**Impact:** `analytics-ollama-soak` is opt-in and standalone. Its first authority
allows 12 hours or 96 cycles, a 45-second cooldown, maximum 78-degree GPU
temperature, minimum 6,144 MB available RAM and 20,480 MB free disk, one
provider call at a time, immediate timeout stop, and two consecutive technical
errors. Resources and `STOP` are checked between model cases. The runtime uses
no Codex or hosted-model API, but local electricity/hardware cost remains.
Repeated Northwind results remain development stability evidence only; external
providers, upload, training, narration, publication, dynamic dispatch, and
production use stay unapproved.

## 2026-07-16 - Consolidate Internal Contracts Through Compatible Extraction

**Decision:** Start Backend Phase II by moving only behavior proven equivalent
into small internal contracts while preserving legacy module exports and
persisted output shapes. Centralize the existing streaming file SHA-256
implementation and the standard four-field analytics blocker append behavior
before attempting atomic publication, source bindings, error taxonomy, common
run results, or CLI decomposition.

**Rationale:** Safety-critical duplication creates a divergence risk, but a
broad rewrite would mix contract design with behavior change. Compatibility
exports and focused identity/shape tests allow gradual adoption without forcing
all blocker schemas or module consumers into an abstraction that does not yet
fit them.

**Alternatives:** Keep identical implementations distributed across modules;
replace every hashing and blocker variant in one refactor; change consumer
imports immediately; or combine this work with orchestrator dispatch and CLI
redesign.

**Impact:** `src/data_ops_lab/contracts/` now owns common file hashing and the
standard analytics blocker. Source onboarding, Product application, reference
dataset validation, analytics planning/execution, and semantic
catalog/approval use those implementations while their old import paths remain
valid. Product materialization, canonical promotion, and reference validation
blocker shapes remain distinct. No approval, source, generated artifact, CLI
entrypoint, dynamic dispatch, provider, database, migration, or public output
contract changed.
