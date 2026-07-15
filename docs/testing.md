# Testing

## Safe Offline Validation

The main suite does not require network access, external databases, credentials, migrations, or production data. Tests write generated artifacts under pytest temporary directories and include checks that protected inputs and approved files remain unchanged.

Because the relocated `.venv` still references the previous editable-install path, use this PowerShell sequence. The generated `.venv\Scripts\dataops.exe` launcher also embeds the old environment location and should not be used until the environment is explicitly repaired.

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
.\.venv\Scripts\python.exe scripts\check_internal_links.py
```

Unset `PYTHONPATH` after the session if needed:

```powershell
Remove-Item Env:PYTHONPATH
```

Repairing the editable install is a separate environment change and should be performed only when explicitly approved.

## Controlled Analytics Execution Validation

Stage 5B tests use temporary synthetic DuckDB files only. They verify exact
plan matching, read-only preservation, parameter privacy, approved joins,
database/request drift blocking, resource limits, no-row diagnostics,
idempotency, and non-overwrite behavior:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\analytics_query_execution_test.py tests\analytics_query_plan_test.py
```

Do not use this focused test command to execute EDS, benchmark, external, or
production databases. Real dataset execution requires its own explicit data-use
approval and reviewed plan.

## Semantic Catalog Validation

Stage 5C tests use schema-only temporary DuckDB fixtures. They verify physical
table/column resolution, numeric measure compatibility, approved relationship
paths, accent-insensitive term lookup, ambiguity preservation, blocked-catalog
resolution, idempotency, input preservation, and non-overwrite behavior:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\analytics_semantic_catalog_test.py
```

The focused tests do not read table rows, approve semantics, or invoke an AI
model. Do not point this command at EDS or benchmark data without separate data
authorization.

## Semantic Review And Approval

The semantic governance tests use synthetic compiled metadata only. They cover
hash-bound pending review generation, complete human-decision validation,
catalog drift, rejection and ambiguity blockers, dry-run behavior, idempotent
apply, state-conflict refusal, and versioned replacement backup:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\analytics_semantic_approval_test.py
```

The test applies state only inside pytest temporary directories. It does not
read EDS or benchmark data, connect to DuckDB or SQL Server, or write the real
`config/analytics/` directory.

## Semantic Intent Adapter

Stage 5D tests use a synthetic approved semantic registry, structured intent,
and a schema-only temporary DuckDB database. They verify approved resolution,
human ambiguity resolution, clarification preservation, raw-SQL and physical-
join rejection, approval enforcement, relationship-path expansion, filter and
order validation, exact reuse, source preservation, and compatibility with the
Stage 5A planner:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\analytics_semantic_adapter_test.py
```

The adapter test never calls a model or external service, reads table rows, or
writes the real semantic registry. The temporary Stage 5A integration opens
only the test DuckDB catalog in read-only mode.

## Natural-Language Translation Boundary

The default provider-boundary tests use recorded responses, injected providers,
and a mocked loopback HTTP transport. They verify prompt minimization, question
authority, local evidence privacy, explicit socket opt-in, loopback-only endpoint
validation, proxy exclusion, bounded structured output, timeout/error
sanitization, provider SQL/join rejection, ambiguity flow, approval enforcement,
exact reuse, CLI shape, and the complete translation-to-semantic-adapter pipeline:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\analytics_nl_translation_test.py
```

The default suite makes no network request and requires no model, Ollama process,
credential, external endpoint, or provider charge. The live local-provider test
is collected but skipped unless explicitly enabled. To run only that smoke test
against an already installed `gpt-oss:20b` model:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:DATA_OPS_LAB_RUN_OLLAMA_LIVE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\ollama_provider_live_test.py -vv
Remove-Item Env:DATA_OPS_LAB_RUN_OLLAMA_LIVE
```

The live test sends one English Northwind question plus minimized approved
semantic metadata to `http://127.0.0.1:11434`. It does not open DuckDB, read
table rows, execute SQL, call an external provider, or authorize benchmark
expected answers. Its result is availability/contract smoke evidence, not model
accuracy evidence.

## Synthetic Translation Evaluation

The Stage 5D evaluation tests run the versioned synthetic pack through the real
translation boundary with in-memory response, timeout, and failure providers.
They verify exact/equivalent intent acceptance, clarification, hallucination and
unsafe-output rejection, sanitized provider failures, metric reporting,
idempotency, non-overwrite behavior, approval enforcement, and omission of
questions, responses, filter values, and physical mappings from evidence:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\analytics_translation_evaluation_test.py
```

The synthetic pack measures deterministic backend regression behavior only. It
does not call a model or support conclusions about live-model quality, latency,
cost, or privacy.

## Synthetic Expected-Answer Evaluation

Stage 5E tests create temporary DuckDB data from a structured allowlisted pack,
then run the actual recorded translation, semantic adapter, Stage 5A planner,
and Stage 5B executor. They verify exact request gating, grouped/filtered/null
approved joins, no-row results, CSV and control-total comparison, fixed limits, input and
evidence preservation, setup-SQL/type rejection, idempotency, and CLI shape:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\analytics_answer_evaluation_test.py
```

The tests execute analytical SELECT queries only against pytest or harness
temporary synthetic DuckDB files. They do not use EDS, benchmark data, project
databases, SQL Server, a model API, network access, migrations, imports, sync,
or narration.

## Dataset-Backed Benchmark Contract

Stage 5E dataset-contract tests create only temporary synthetic DuckDB files.
The validator hashes each database as an opaque file and never opens it or reads
its catalog, tables, or rows. Tests cover immutable hash bindings, provenance
and license gates, separate human approval, exact and numeric-tolerance policy,
input preservation, idempotency, divergent-evidence refusal, and CLI shape:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\analytics_dataset_benchmark_test.py
```

Do not substitute EDS, AdventureWorks, Northwind, Pubs, or another real dataset
for the temporary test fixture. Validating a real package requires its own
reviewed manifest, semantic state, relationships, pack, and approval; execution
is a later, separate capability.

## Dataset Benchmark Answer Preparation

The focused preparation tests create a temporary synthetic DuckDB package and
compile recorded Stage 5D intents into exact Stage 5A plans. They cover immutable
bindings, provider SQL rejection before database access, output alias/shape
checks, pending aggregate plan review, idempotency, non-overwrite behavior, and
the fixed no-execution CLI boundary:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\analytics_dataset_benchmark_preparation_test.py
```

The tests never call Stage 5B or a live provider. The separately authorized real
Northwind preparation command reads only the DuckDB catalog in read-only mode,
produces exact plans, and stops for aggregate human review. It must not be used
to infer approval of answer collection or of the values that a later reviewed
collection may produce.

## Dataset Benchmark Answer Materialization

The focused materialization tests complete a synthetic exact-plan review, then
verify sequential Stage 5B execution, read-only plan revalidation and query
connections, typed candidate-pack construction, final contract validation,
idempotent reuse, source preservation, prohibited-scope refusal before Stage
5B, prepared-plan drift blocking, and the fixed no-network/no-limit-bypass CLI:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\analytics_dataset_benchmark_materialization_test.py
```

Real materialization is allowed only after a completed human review approves
every exact prepared plan for local read-only collection. It writes candidate
answers, not final benchmark authority. The generated pack must still complete
the separate per-case review and approval workflow before any offline or live
model evaluation.

## Dataset Benchmark Review And Approval

The same focused synthetic fixture verifies hash-bound pending review,
per-case and scope decisions, dry-run approval planning, explicit apply,
approval idempotency, source drift, prohibited scope expansion, missing and
duplicate decisions, divergent-output refusal, and final validator integration:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\analytics_dataset_benchmark_test.py
```

One test replaces `duckdb.connect` with an immediate failure after creating the
temporary fixture, proving that review, approval, and final binding validation
do not connect to the database. No project approval path or real review file is
written.

## Dataset-Backed Offline Evaluation

The dataset-backed executor tests use the same temporary synthetic package and
a temporary generated approval. They cover exact comparison, numeric tolerance
inside and outside bounds, no-row controls, expectation failure versus contract
blocking, read-only connections, approval failure before database access,
pre-query authority drift, idempotency, non-overwrite behavior, evidence
minimization, and CLI limits:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\analytics_dataset_benchmark_test.py
```

The test suite does not run this command against any project, EDS, SQL Server,
or public benchmark database. Real execution requires the exact generated
approval for that package and is not part of the default project state.

## Dataset-Backed Live Ollama Evaluation

The focused synthetic tests use an injected fake live provider and temporary
DuckDB package. They cover offline/idempotent preflight, exact provider and
authority binding, literal-loopback enforcement, separate execution/network
flags, sequential full-pipeline comparison, alias-only normalization, mismatch
isolation, authority drift, conservative network telemetry on unexpected errors,
resource/token evidence, privacy, atomic output publication, and preservation of
unknown or divergent evidence:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\analytics_dataset_benchmark_test.py
```

The real 13-case test is collected but skipped unless explicitly enabled. It is
not part of the offline suite and must be run only with the exact versioned live
authorization, local Northwind artifacts, installed model, and already-running
loopback Ollama service:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:DATA_OPS_LAB_RUN_OLLAMA_BENCHMARK_LIVE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\ollama_dataset_benchmark_live_test.py -vv
Remove-Item Env:DATA_OPS_LAB_RUN_OLLAMA_BENCHMARK_LIVE
```

This test makes 13 sequential local HTTP calls and eligible read-only DuckDB
queries, can consume several minutes and most of an 8 GB GPU, and writes only
sanitized evidence. It does not authorize an external endpoint, upload,
training, narration, publication, or reuse of a changed authorization.

## Local Ollama Overnight Soak

The soak tests use the same temporary synthetic benchmark package and injected
fake live provider. They run no local or hosted model. They cover offline
preflight, two sequential full-pipeline cycles, safe aggregate/case-stability
evidence, per-case resource guards, `STOP` during cooldown, authority drift,
concurrency refusal, content privacy, and a CLI without duration, resource, or
parallelism bypass flags:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\analytics_dataset_benchmark_test.py
```

The real soak is never part of pytest or the default suite. Run its dry-run
first, then start the explicit CLI in a separate process only with the exact
versioned soak authorization. The local process uses no Codex/hosted-model API,
but it consumes electricity and sustained local CPU/GPU resources.

## Benchmark Conversion Validation

Use the restricted converter only for a locally approved SQL sample whose
provenance and license status are recorded. The command never executes source
SQL or connects to a database:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\benchmark_sql_conversion_test.py
.\.venv\Scripts\python.exe -m data_ops_lab benchmark-convert-sql --source "datasets\benchmarks\raw\northwind\instnwnd.sql" --dataset northwind --output "datasets\benchmarks\derived\northwind"
```

A repeated conversion must report `Outputs changed: False`. Validate real
benchmark outputs by comparing manifest counts and SHA-256 values across the
DuckDB database and each Parquet file. Do not run `.bak` restore, external load,
import, migration, or synchronization commands as part of the offline suite.

## Reference Dataset Validation

The focused suite builds two independent restricted conversions from temporary
synthetic SQL. It verifies provenance/license/use preflight, conversion
equivalence, read-only schema profiling, primary-key null/duplicate checks,
foreign-key orphan/target-uniqueness checks, pending versus completed exact
human review, preflight refusal before database access, idempotency,
non-overwrite behavior, input preservation, and CLI shape:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\reference_dataset_validation_test.py
.\.venv\Scripts\python.exe -m data_ops_lab reference-dataset-validate --manifest "datasets\benchmarks\manifests\northwind.reference.yml" --output "outputs\benchmarks\northwind-phase2-validation"
```

The default test suite uses no public dataset, network, external database,
credential, upload, publication, or model training. The real command is an
authorized local Phase 2 validation: it opens only the hash-bound Northwind
DuckDB in read-only mode and does not approve its pending relationships. A
completed-review test also verifies that only accepted decisions enter the
derived registry and that rejected decisions remain explicitly excluded.

## Northwind Semantic Catalog Validation

The ordinary Stage 5C tests remain synthetic and offline. The separately
authorized real catalog check reads only DuckDB metadata and the approved
Northwind relationship projection. The completed review is validated in dry-
run mode before an explicit idempotent apply:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\analytics_semantic_catalog_test.py tests\analytics_semantic_approval_test.py tests\analytics_semantic_adapter_test.py
.\.venv\Scripts\python.exe -m data_ops_lab analytics-semantic-catalog --catalog "datasets\benchmarks\manifests\northwind.semantic-catalog-candidate.yml" --database "datasets\benchmarks\derived\northwind\northwind.duckdb" --relationships "outputs\benchmarks\northwind-phase2-reviewed\approved_relationships.yml" --output "outputs\benchmarks\northwind-phase3-semantic-catalog-v2"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-semantic-review --catalog "outputs\benchmarks\northwind-phase3-semantic-catalog-v2\analytics_semantic_catalog.yml" --output "outputs\benchmarks\northwind-phase3-semantic-review\analytics_semantic_review.yml"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-semantic-approval --catalog "outputs\benchmarks\northwind-phase3-semantic-catalog-v2\analytics_semantic_catalog.yml" --review "datasets\benchmarks\manifests\northwind.semantic-review.yml" --output "outputs\benchmarks\northwind-phase3-semantic-approval-dry-run" --config "config\analytics"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-semantic-approval --catalog "outputs\benchmarks\northwind-phase3-semantic-catalog-v2\analytics_semantic_catalog.yml" --review "datasets\benchmarks\manifests\northwind.semantic-review.yml" --output "outputs\benchmarks\northwind-phase3-semantic-approval-apply" --config "config\analytics" --apply
```

The real compile must report `ready_for_semantic_review`, zero blockers, zero
ambiguities, 13 tables, 60 dimensions, 19 measures, and 18 paths. A repeated
compile, review preparation, and repeated apply must reuse byte-identical
outputs/state. Compilation, review, and approval do not query table rows,
execute an analysis, or use a provider/network. Only the final `--apply` writes
the already approved registry. A separate real smoke intent reached Stage 5A
`ready_for_execution_review` without Stage 5B execution.

## Deterministic Result Presentation And Narration

Result presentation tests create only temporary synthetic DuckDB and Stage 5A/
5B evidence. They verify request/result hash bindings, execution controls,
bounded previews, no-row diagnostics, escaped local Markdown, exact reuse,
input preservation, facts drift, mandatory citations, numeric grounding, SQL
rejection, network blocking, and divergent-output refusal:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\analytics_result_presentation_test.py
```

The focused suite uses a recorded YAML narrator only. It does not use real data,
a live model, network, credentials, external databases, imports, migrations,
sync, upload, or training.

## Local Analytics Session

The session tests use a temporary synthetic DuckDB, approved semantic fixture,
and recorded local translation/narration responses. They cover preparation
idempotency, privacy, clarification stop, pending and hash-mismatched review,
relationship drift, complete resume, checkpoint preservation, grounded
narration failure, and CLI review/network boundaries:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\analytics_session_test.py
```

No real data, live provider, network, external database, import, migration,
sync, upload, or training is used.

## Analytics Module Registry

The registry tests validate the checked-in contract, static entrypoint and
signature inspection, declared test files, dependency cycles, workflow order,
human execution gates, malformed input handling, idempotency, divergent-output
refusal, and CLI safety:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\module_registry_test.py
```

The validator does not import or call declared entrypoints, execute a workflow,
open a database, use a provider, or authorize data and review state.

## Synthetic Performance And Schema Pushdown

The performance harness tests generate small temporary Parquet tables and run
the profiler, cleaner, schema, and relationship validator in isolated child
processes. Schema pushdown tests compare the optimized output exactly with the
legacy Pandas contract, including nulls, NaN, empty tables, repeated line
references, key candidates, and relationship candidates:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\performance_baseline_test.py tests\schema_pushdown_test.py tests\smoke_test.py
```

The harness has no external input/database argument and uses no EDS, benchmark
dataset, provider, network, credential, or approved state. Performance values
are environment-specific evidence; contract assertions, not speed thresholds,
belong in the default suite.

## Validation Levels

1. Unit tests for parsers, transformations, rules, and isolated decisions.
2. Contract tests for inputs, outputs, schemas, errors, and compatibility.
3. Integration tests for module boundaries using temporary local fixtures.
4. Workflow tests for coordinated sequences.
5. Regression tests for previously broken or protected behavior.
6. End-to-end tests from local input to generated output.
7. Reliability/performance checks only after measuring a real bottleneck.

Start with the smallest relevant test. Run the full suite after source, contract, workflow, or shared behavior changes. Documentation-only work requires link/format validation and does not justify invented tests, though running the offline suite is acceptable as a repository checkpoint.

## External Integrations

Default tests must remain offline. Any future API, database, or hosted-service integration needs fixtures or mocks in the main suite. Label and isolate online tests so they never run by default or incur external cost unexpectedly.

## Test Integrity

- Do not change expectations to fit an unapproved modeling decision.
- Separate raw-data findings, approval gaps, model assumptions, and code regressions.
- Never claim a test passed unless its command completed successfully.
- Record skipped checks and their reason in `docs/agent-handoff.md`.
