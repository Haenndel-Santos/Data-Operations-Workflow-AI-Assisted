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
  -> result validation and explanation
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
control totals, blockers, diagnostics, and CSV only on success. Natural-language
translation, result narration, and external database access remain unimplemented.

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
No real semantic catalog has been approved, so Stage 5D remains operationally
blocked. See [Analytics Semantic Review And Approval](analytics-semantic-approval.md).

Stage 5D now provides `analytics-semantic-adapter`, an offline deterministic
compiler for a supplied version-1 semantic intent. It requires applied approved
semantic state, copies aggregates/columns/paths only from that state, preserves
ambiguities as clarification requests, rejects raw SQL and physical joins, and
emits the existing Stage 5A request. Model-provider integration and direct
free-text interpretation remain unimplemented. See
[Analytics Semantic Adapter](analytics-semantic-adapter.md).

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

This architecture supports datasets larger than available RAM more effectively than a DataFrame-only pipeline. Actual limits remain dependent on file format, query shape, disk throughput, and available temporary storage.

## Dataset And Model Strategy

### EDS

EDS is the first private domain implementation and the strongest source of real ERP semantics. Its data may be used locally for development fixtures, regression checks, retrieval context, and evaluation only under the existing privacy rules. It must not be uploaded to an external model or used for parameter training without a separate documented authorization, minimization plan, retention policy, and leakage assessment.

### Public Benchmarks

The local benchmark area now contains user-supplied Northwind, Pubs,
AdventureWorks 2025, and a Contoso warehouse load recipe. Northwind and Pubs
have reproducible DuckDB/Parquet conversions, but their exact download origins
and licenses remain unconfirmed and all extracted relationships remain
`pending_review`. AdventureWorks exactly matches Microsoft's official MIT-licensed
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

### Learning Stages

1. Deterministic tests and benchmark questions with expected SQL/results.
2. Prompt and retrieval evaluation over schema metadata and business definitions.
3. Model/provider comparison using accuracy, safety, cost, and latency metrics.
4. Fine-tuning only if benchmark evidence shows a durable advantage over prompting/retrieval and data governance permits it.

Calling all dataset use "training" would hide important differences. The initial goal is evaluation and grounded retrieval; model-parameter training is a later, optional decision.

## Roadmap

1. **Stage 5A - Safe query planning:** structured request, catalog validation, approved joins, parameterized SQL, dry-run evidence. Implemented.
2. **Stage 5B - Controlled local execution:** read-only DuckDB executor, timeout/resource limits, result manifest, control totals, and no-result diagnostics. Implemented.
3. **Stage 5C - Semantic catalog:** business names, synonyms, measures, dimensions, relationship paths, ambiguity scores, and dataset-specific domain packs. Technical validation plus the human review/apply infrastructure are implemented; a concrete approved catalog remains pending.
4. **Stage 5D - Natural-language adapter:** deterministic approved-semantic intent compiler and clarification boundary implemented; model-provider translation from free text remains pending. Raw SQL is never accepted.
5. **Stage 5E - Benchmark harness:** EDS local evaluations plus separately approved AdventureWorks and Chinook packs with expected questions, plans, and answers.
6. **Stage 5F - User experience:** query interface, result tables/charts, evidence view, saved analyses, feedback, and role-aware governance.
7. **Stage 5G - Optional data connectors:** separately authorized read-only database connectors with credential isolation and online tests outside the default suite.

## Success Measures

- Structured-plan validity and safe rejection rate.
- Correct table, column, metric, filter, and relationship selection.
- Exact answer agreement on benchmark questions.
- Join-fanout and control-total preservation.
- Peak memory, runtime, scanned bytes, and output size.
- Clarification quality for ambiguous requests.
- Zero unauthorized writes, private-value leakage, or unapproved relationships.
