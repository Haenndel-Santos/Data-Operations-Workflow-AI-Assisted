# Analytics Expected-Answer Evaluation Contract

## Module

```yaml
name: analytics_answer_evaluation
version: 1
status: implemented_synthetic_offline
entrypoint: data_ops_lab.analytics_answer_evaluation.run_analytics_answer_evaluation
inputs:
  - versioned_synthetic_answer_pack_yaml
  - applied_approved_semantic_catalog_yaml
outputs:
  - analytics_answer_evaluation.yml
  - analytics_answer_evaluation_cases.csv
  - analytics_answer_evaluation_blockers.csv
  - analytics_answer_evaluation_report.md
dependencies:
  - analytics_nl_translation
  - analytics_semantic_adapter
  - analytics_query_plan
  - analytics_query_execution
failure_policy: validate_before_materialization_and_never_overwrite_different_evidence
```

## Purpose

This Stage 5E foundation measures exact end-to-end answers through the existing
governed analytics pipeline. It creates a temporary synthetic DuckDB database,
replays a recorded semantic response through Stage 5D, requires the generated
physical request to exactly match a versioned expected request, builds a Stage
5A plan, and executes it through Stage 5B before comparing the result and
control totals.

The bundled pack under `tests/fixtures/analytics_answer_evaluation/` is
synthetic contract evidence. It does not approve a real semantic catalog,
relationship, dataset, model provider, or business answer.

## Execution Gates

```text
versioned synthetic pack
  -> strict pack and semantic-state validation
  -> temporary DuckDB materialization from structured allowlisted values
  -> recorded Stage 5D semantic translation
  -> exact expected-request comparison
  -> Stage 5A catalog validation and parameterized plan
  -> Stage 5B exact plan revalidation and read-only execution
  -> exact CSV and control-total comparison
```

Planning and execution do not run when the Stage 5D request differs from the
versioned expected request. The expected request is synthetic test authority,
not human authorization for a real query. Stage 5B still recompiles and exactly
matches the Stage 5A plan before execution.

## Pack Contract

A version-1 pack has a stable ID, description, structured dataset, synthetic
approved relationships, and at most 50 cases. It must cover approved joins,
grouped aggregate, filtered aggregate, no-row, and null-filter behavior.

Database setup accepts at most eight tables, 64 columns per table, and 1,000
rows. Table and column names follow a lowercase identifier grammar. Supported
types are `integer`, `bigint`, `double`, `varchar`, `boolean`, and
`decimal_18_2`. The pack cannot supply setup SQL, expressions, constraints,
files, extensions, or external locations. DDL and parameterized inserts are
generated only from validated identifiers and fixed type mappings.

Each case contains:

- one synthetic question and safe recorded provider response;
- the exact expected Stage 5A request, including the authoritative question;
- expected execution status, columns, ordered rows, row/column counts, and null
  count.

Multi-row exact results require explicit `order_by`. `completed_no_rows` cases
must have an empty expected row list; completed cases require at least one row.

## Status And Metrics

- `passed`: every case matched its request, pipeline status, exact CSV, and
  result controls.
- `failed`: the pack and semantic state were valid, but at least one expected
  request or answer diverged.
- `blocked`: pack or semantic approval validation failed before case execution,
  or the validated synthetic database could not be materialized.

The manifest reports overall, pipeline, request, exact-result, and control
accuracy. The case CSV contains IDs, categories, stage statuses, comparison
booleans, and pass/fail state only.

## Privacy And Storage

The input pack intentionally versions synthetic questions, rows, provider
responses, expected requests, and expected results. Runtime databases, question
files, translation evidence, plans, execution results, and case directories are
temporary and deleted after evaluation.

Persistent evaluator outputs contain source hashes, fixed limits, control
flags, metrics, and case states. They do not reproduce the synthetic case
content. Real or private values must not be placed in a versioned pack.

## Fixed Limits

Stage 5B evaluation uses 1,000 result rows, 1 MB result bytes, 10 seconds, 128
MB memory, one thread, and 64 MB temporary storage. The CLI exposes no database,
SQL, provider, network, or resource-limit override.

## Offline Command

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-answer-evaluate `
  --pack "tests/fixtures/analytics_answer_evaluation/answer_evaluation_pack.yml" `
  --semantic-state "tests/fixtures/analytics_answer_evaluation/approved_semantic_catalog.yml" `
  --output "outputs/<run-id>/analytics_answer_evaluation"
```

The command uses a temporary local DuckDB database and performs read-only
analytical queries against that synthetic database. It uses no live model,
network, external database, production data, migration, import, sync, or result
narration.

Dataset-backed packs require immutable artifact, review, and approval validation
before reusing these execution boundaries. See
[Dataset-Backed Benchmark Validation](analytics-dataset-benchmark.md) and
[Dataset-Backed Offline Benchmark Evaluation](analytics-dataset-benchmark-evaluation.md).
