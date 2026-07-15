# AI-Assisted Analytics Backend

## Product Direction

The target experience lets a user ask an operational question in natural language and receive a reproducible answer, supporting evidence, data-quality warnings, and the generated analytical plan without needing to write SQL.

The AI is an interpretation layer, not a database authority. It may propose a structured intent, but deterministic local code validates and compiles that intent before any query can run.

## Target Flow

```text
User question
  -> AI intent translation
  -> versioned structured analytics request
  -> semantic catalog and approved-relationship validation
  -> deterministic parameterized SELECT compiler
  -> cost/safety review
  -> read-only DuckDB execution
  -> deterministic result validation and presentation
  -> grounded cited explanation
  -> auditable answer package
```

No model-generated SQL is executed directly. This boundary keeps the backend testable and allows the AI provider or model to change without changing query safety.

## Current Foundation

Stage 5A provides `analytics-query-plan`, a dry-run command that:

- Opens one local DuckDB database in read-only mode.
- Discovers tables and columns from the database catalog.
- Accepts only a limited version-1 YAML request.
- Supports dimensions, allowlisted aggregates, scalar filters, ordering, limits, and left/inner joins.
- Requires every cross-table join to match `approved_relationships.yml` or another explicitly supplied approved registry.
- Compiles quoted SQL with parameter placeholders.
- Excludes question text and filter values from generated evidence.
- Produces a ready/blocked plan without executing SQL.

Stage 5B adds `analytics-query-execute`. It recompiles the structured request,
requires an exact reviewed Stage 5A plan, revalidates catalog and approved
relationships, and executes only against local DuckDB in read-only mode. It
enforces runtime, memory, thread, temporary-storage, row, and result-byte limits;
disables external access and extension autoload; and writes a result manifest,
control totals, blockers, diagnostics, and CSV only on success. External
database access remains unimplemented.

Stage 5C adds `analytics-semantic-catalog`. It validates candidate business
names, synonyms, dimensions, measures, and multi-hop relationship paths against
the live DuckDB schema and approved relationships. It emits a normalized term
index with explicit unique, ambiguous, and unknown resolution behavior. Valid
catalogs remain `ready_for_semantic_review`; automated approval and Stage 5D
adapter use are not authorized. See [Analytics Semantic Catalog](analytics-semantic-catalog.md).

The semantic review and approval contract now prepares a hash-bound pending
review, validates complete human decisions in dry-run mode, and can persist a
minimal approved registry only with explicit `--apply`. Rejected, pending,
missing, duplicate, or stale decisions fail closed. Ambiguities either remain
clarification points or resolve to an exact candidate selected by a human.
The first real Northwind catalog compiles with 13 tables, 60 dimensions, 19
measures, 18 approved paths, 339 terms, zero ambiguities, and zero blockers. Its
separate 111-entity review is complete and the hash-bound approved registry is
applied. A real structured intent passed Stage 5D and Stage 5A without execution;
  Northwind is no longer semantically blocked. A local Ollama provider passed a
  separate English smoke question. Phase 5 has started with a
versioned 13-case English answer design. Its 13 exact Stage 5A plans received
separate human collection approval and completed sequential fixed-limit Stage
5B execution. All four final decisions per case were then approved, producing
  immutable answer authority, and the recorded offline evaluator passed 13/13.
  A separately authorized 13-case local Ollama development comparison then
  passed 9/13 end to end; four mismatches were blocked before query execution.
  See
[Northwind Semantic Catalog Review](northwind-semantic-review.md),
[Northwind Expected-Answer Plan Review](northwind-answer-benchmark-review.md),
  [Northwind Expected-Answer Review](northwind-expected-answer-review.md),
  [Dataset Benchmark Live Evaluation](analytics-dataset-benchmark-live-evaluation.md), and
[Analytics Semantic Review And Approval](analytics-semantic-approval.md).

Stage 5D now provides `analytics-semantic-adapter`, an offline deterministic
compiler for a supplied version-1 semantic intent. It requires applied approved
semantic state, copies aggregates/columns/paths only from that state, preserves
ambiguities as clarification requests, rejects raw SQL and physical joins, and
emits the existing Stage 5A request. Provider integration remains separate from
this deterministic authority. See
[Analytics Semantic Adapter](analytics-semantic-adapter.md).

The provider-neutral translation boundary is now implemented with prompt
minimization, strict response validation, sanitized timeout/failure handling,
explicit network opt-in, and mandatory Stage 5D adapter chaining. The recorded
provider remains the offline regression default. The additive local provider
calls Ollama `gpt-oss:20b` only through an explicit literal loopback endpoint,
disables proxies, requires no credentials, bounds context/output/time, uses
semantic-ID JSON Schema, and never retries. One isolated live smoke test passed;
this is provider availability evidence, not model-quality evidence. See
[Analytics Natural-Language Translation](analytics-nl-translation.md).

The Stage 5D synthetic evaluation harness replays exact/equivalent intent,
clarification, hallucination, unsafe-output, timeout, and provider-failure cases
through that same boundary. It reports explicit status, intent, blocker, and
clarification accuracy without persisting questions or responses. This is
offline contract-regression evidence, not a live-model benchmark. See
[Analytics Translation Evaluation](analytics-translation-evaluation.md).

Stage 5E now has a synthetic expected-answer foundation. A versioned pack
materializes allowlisted rows into temporary DuckDB, requires the Stage 5D
request to exactly match the expected request, runs Stage 5A and Stage 5B, and
compares exact CSV output plus row, column, and null controls. Runtime artifacts
are discarded and evaluator evidence omits case content. See
[Analytics Expected-Answer Evaluation](analytics-answer-evaluation.md).

Real expected-answer preparation now has its own pre-execution checkpoint. A
bounded design binds the verified dataset, approved semantic state, approved
relationships, recorded semantic intents, intended output types, and comparison
policies. It compiles every case through Stage 5D and Stage 5A, then generates
one aggregate pending review bound to every plan hash. It does not call Stage
5B or read table rows. See
[Dataset Benchmark Answer Preparation](analytics-dataset-benchmark-preparation.md).

The companion answer materializer validates that completed review before any
table-row access, rechecks all immutable sources plus each request and plan
before and after every query, runs Stage 5B sequentially with fixed limits, and
constructs a typed candidate pack only after result hashes, schemas, types, and
control totals pass. It does not call a model or approve collected values. See
[Dataset Benchmark Answer Materialization](analytics-dataset-benchmark-materialization.md).

The dataset-backed Stage 5E dry-run validator now binds a verified local DuckDB
artifact, approved semantic state, approved relationships, candidate benchmark
pack, and separate human approval by SHA-256. It validates expected results and
exact or explicitly bounded numeric comparison policies without opening or
querying the database. Northwind now has the required dataset manifest,
completed 13-case review, and generated approval. Its final validation reported
`ready_for_offline_evaluation` with zero blockers. See
[Dataset-Backed Benchmark Validation](analytics-dataset-benchmark.md).

The companion benchmark governance workflow prepares a pending hash-bound
review, requires complete per-case and scope decisions, validates in dry-run by
default, and writes a separate immutable approval only with `--apply`. It never
executes a case or authorizes live providers, upload, or model training. See
[Dataset Benchmark Review And Approval](analytics-dataset-benchmark-review.md).

The approved dataset-backed evaluator now rechecks every immutable authority,
replays recorded Stage 5D responses, requires exact Stage 5A requests, and uses
Stage 5B fixed-limit read-only execution before exact or reviewed numeric
comparison. Persistent evidence omits case content and results. Northwind is the
first approved real package to run through this boundary: 13/13 cases passed,
including 12/12 exact and 1/1 reviewed-tolerance results, with zero blockers and
no live provider or network. See
[Dataset-Backed Offline Benchmark Evaluation](analytics-dataset-benchmark-evaluation.md).

The separate live dataset evaluator requires its own SHA-256-bound human
authorization, dry-runs without a provider or database, and in live mode accepts
only exact literal-loopback Ollama plus explicit execution and socket flags. It
runs cases sequentially, rehashes authority before provider/query use, permits
only reviewed alias normalization after every non-alias request field matches,
and persists no question, response, SQL, parameter, or result row. The first
Northwind development run passed 9/13 with zero contract blockers and USD 0
hosted cost. Because these cases informed prompt and alias-policy refinement,
they are not a holdout; a fresh reviewed pack is required before provider
selection. See
[Dataset Benchmark Live Evaluation](analytics-dataset-benchmark-live-evaluation.md).

The result-presentation boundary revalidates exact Stage 5B request/result
hashes and controls, then writes a deterministic local table and bounded fact
IDs with bounded-memory CSV streaming, without connecting to a database or
changing values. A separate narration
boundary accepts only that hash-bound facts package, requires citations for
every claim, preserves numeric tokens exactly, and requires row/no-row/preview
controls. Its concrete provider is recorded and offline; narration remains
non-authoritative. See [Deterministic Result Presentation](analytics-result-presentation.md)
and [Grounded Result Narration](analytics-result-narration.md).

The local analytics-session service composes these existing boundaries without
copying their logic. Preparation runs recorded translation and Stage 5A, then
stops for an exact hash-bound human plan review. Resume validates that separate
review before Stage 5B and records the last valid execution, presentation, or
narration checkpoint. See [Local Analytics Session](analytics-session.md).

The session modules and their two phases are now described by a versioned
declarative registry. Static dry-run validation checks entrypoints, exact
parameter names, dependencies, cycles, capabilities, workflow order, tests,
failure policies, and the execution-review gate without importing or calling
the registered entrypoints. See [Analytics Module Registry](analytics-module-registry.md).

## Request Contract

```yaml
version: 1
question: Which customers have the highest open-order value?
from: orders
joins:
  - source_table: orders
    source_column: order_id
    target_table: order_lines
    target_column: order_id
    kind: left
dimensions:
  - column: orders.customer_name
    alias: customer
metrics:
  - function: sum
    column: order_lines.amount
    alias: total_amount
filters:
  - column: orders.status
    operator: eq
    value: open
order_by:
  - field: total_amount
    direction: desc
limit: 100
```

Supported aggregates are `count`, `count_distinct`, `sum`, `avg`, `min`, and `max`. Supported filters are `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `is_null`, and `not_null`. One request is bounded to eight joins, 64 dimensions, 64 metrics, 64 filters, 64 order rules, 1,000 values per `in` filter, and 10,000 result rows.

## Safety And Governance

- No arbitrary SQL field, DDL, DML, procedure, extension, network operation, or external connector is accepted.
- Table and column references must resolve against the live local catalog.
- Output aliases follow a strict identifier grammar.
- Filter values stay in memory as parameters and are not copied into plan files.
- Candidate relationships are not sufficient for joins; human-approved relationships are required.
- A ready plan is not execution authorization.
- Controlled execution uses read-only connections, interruption, resource and result limits, input-drift checks, and an audit manifest.

## Scale And Memory Strategy

Excel should remain an onboarding format, not the large-scale analytical storage format.

1. Convert XLSX/CSV inputs to typed Parquet once.
2. Scan Parquet lazily with DuckDB and push filters, projections, joins, and aggregates into the engine.
3. Remove full-table Pandas loads from profiling, schema discovery, and relationship validation where practical.
4. Use samples for exploratory statistics and exact scans for keys, control totals, and approval-critical checks.
5. Persist reusable local metadata and invalidate it by source/catalog hashes.
6. Add memory, runtime, row-count, and join-fanout budgets before enabling query execution.

The first measured scale increment is complete. A generated synthetic Parquet
harness records runtime, Peak Working Set/`ru_maxrss`, Python allocation, input
footprint, output bytes, and temporary storage in isolated processes. The
schema/key stage now uses Arrow metadata plus local DuckDB aggregation and
candidate-overlap pushdown while preserving exact legacy outputs. On the
50,000-row x 3-table workload, its peak process memory fell 27.23% and runtime
fell 98.99%. See [Synthetic Pipeline Performance Baseline](performance-baseline.md).

This architecture supports datasets larger than available RAM more effectively than a DataFrame-only pipeline. Actual limits remain dependent on file format, query shape, disk throughput, and available temporary storage.

## Dataset And Model Strategy

### EDS

EDS is the first private domain implementation and the strongest source of real ERP semantics. Its data may be used locally for development fixtures, regression checks, retrieval context, and evaluation only under the existing privacy rules. It must not be uploaded to an external model or used for parameter training without a separate documented authorization, minimization plan, retention policy, and leakage assessment.

### Public Benchmarks

The local benchmark area now contains user-supplied Northwind, Pubs,
AdventureWorks 2025, and a Contoso warehouse load recipe. Northwind and Pubs
have reproducible DuckDB/Parquet conversions. Northwind is now byte-matched to
Microsoft's official source, MIT-license verified, independently reproduced,
and read-only validated across 13 declared PKs and 13 FK candidates. Its local
benchmark scope is approved, and a completed exact human review accepted all 13
physical relationships, producing `ready_for_semantic_modeling`. Northwind
semantics are approved, its 13 exact plans passed collection review, and all 13
expected answers were collected through sequential read-only Stage 5B with zero
materialization blockers. The separate per-case review approved every response,
request, result, and comparison policy; its recorded offline evaluation passed
13/13. The separately authorized live development comparison passed 9/13 and
does not complete provider selection. Pubs still
requires exact source/license and relationship review. AdventureWorks exactly
matches Microsoft's official MIT-licensed
2025 backup and is restored in a local SQL Server 2025 Developer instance as a
read-only database. Restore verification and `DBCC CHECKDB` passed; a
reproducible DuckDB/Parquet export and relationship review remain pending.
Contoso is retained as schema/load evidence only because its rows are external.
No external database was connected during onboarding or validation.

AdventureWorksDW2019 and Chinook remain candidate benchmark packs for broader
dimensional and media-commerce coverage. Every pack still requires an
authoritative source, version, license, checksum, expected schema, reviewed
relationships, and reproducible import procedure before benchmark approval.
See [Benchmark Datasets](benchmark-datasets.md).
The reusable Phase 2 gate is documented in
[Reference Dataset Validation](reference-dataset-validation.md).

### Learning Stages

1. Deterministic tests and benchmark questions with expected SQL/results.
2. Prompt and retrieval evaluation over schema metadata and business definitions.
3. Model/provider comparison using accuracy, safety, cost, and latency metrics.
4. Fine-tuning only if benchmark evidence shows a durable advantage over prompting/retrieval and data governance permits it.

Calling all dataset use "training" would hide important differences. The initial goal is evaluation and grounded retrieval; model-parameter training is a later, optional decision.

## Roadmap

The detailed implementation sequence, exit gates, quality targets, and
commercial-readiness path are maintained in
[AI Platform Implementation Roadmap](ai-implementation-roadmap.md).

1. **Stage 5A - Safe query planning:** structured request, catalog validation, approved joins, parameterized SQL, dry-run evidence. Implemented.
2. **Stage 5B - Controlled local execution:** read-only DuckDB executor, timeout/resource limits, result manifest, control totals, and no-result diagnostics. Implemented.
3. **Stage 5C - Semantic catalog:** business names, synonyms, measures, dimensions, relationship paths, ambiguity scores, and dataset-specific domain packs. Technical validation and human review/apply infrastructure are implemented; Northwind is the first concrete approved catalog.
4. **Stage 5D - Natural-language adapter:** deterministic approved-semantic compiler, provider-neutral translation boundary, synthetic offline regression pack, an explicitly authorized loopback Ollama adapter, and a governed live development-evaluation path are implemented. Raw SQL is never accepted.
5. **Stage 5E - Expected-answer harness:** synthetic evaluation, pre-execution answer preparation, reviewed sequential candidate-answer materialization, per-case dataset benchmark review/approval, dry-run immutable binding validation, approved offline dataset-backed execution, and separate hash-bound live comparison are implemented. Northwind passed its recorded baseline 13/13 and local Ollama development comparison 9/13; a fresh holdout, provider selection, and EDS evaluation remain pending.
6. **Stage 5F - User experience:** deterministic result tables, recorded cited narration, and a two-phase local session coordinator are implemented. Query UI, charts, evidence navigation, saved analyses, feedback, and role-aware governance remain pending.
7. **Stage 5G - Optional data connectors:** separately authorized read-only database connectors with credential isolation and online tests outside the default suite.

## Success Measures

- Structured-plan validity and safe rejection rate.
- Correct table, column, metric, filter, and relationship selection.
- Exact answer agreement on benchmark questions.
- Join-fanout and control-total preservation.
- Peak memory, runtime, scanned bytes, and output size.
- Clarification quality for ambiguous requests.
- Zero unauthorized writes, private-value leakage, or unapproved relationships.
