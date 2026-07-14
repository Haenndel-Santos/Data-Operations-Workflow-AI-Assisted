# Controlled Analytics Query Execution Contract

## Module

```yaml
name: analytics_query_execution
version: 1
status: implemented
entrypoint: data_ops_lab.analytics_query_execution.run_analytics_query_execution
inputs:
  - structured_request_yaml
  - local_duckdb_database
  - approved_relationship_registry
  - exact_reviewed_stage_5a_plan
  - execution_limits
outputs:
  - analytics_query_execution.yml
  - analytics_query_execution_blockers.csv
  - analytics_query_execution_report.md
  - analytics_query_result.csv_when_successful
failure_policy: fail_closed_without_partial_result_and_preserve_existing_evidence
```

## Contract Boundary

Stage 5B executes only a query recompiled from the Stage 5A structured request.
It does not accept raw SQL. Before execution, the module rebuilds the plan from
the current request, DuckDB catalog, database file fingerprint, and approved
relationships, then requires an exact match with the reviewed plan artifact.

The database is opened with `read_only=True`. DuckDB external access, extension
installation, and extension autoload are disabled. Temporary spill is isolated
in a disposable system directory and bounded separately from the database.

## Limits

| Limit | Default | Accepted range |
| --- | ---: | ---: |
| Result rows | 10,000 | 1-10,000 |
| Result bytes | 10,000,000 | 1,024-50,000,000 |
| Runtime | 30 seconds | 1-300 seconds |
| DuckDB memory | 512 MB | 64-8,192 MB |
| DuckDB threads | 2 | 1-16 |
| Temporary spill | 1,024 MB | 64-8,192 MB |

Timeout uses DuckDB interruption. Results are fetched in bounded batches and
serialized only while they remain inside the row and byte budgets. A breached
limit produces blockers and no result CSV.

## Statuses

- `completed`: execution succeeded with at least one result row.
- `completed_no_rows`: execution succeeded and writes a header-only result plus
  an explicit no-result diagnostic.
- `blocked`: validation, plan matching, execution, drift, or a resource limit
  failed; no result artifact is written.

## Evidence And Privacy

The manifest records plan/request/relationship/catalog fingerprints, the
database size and modification timestamp, SQL hash, parameter types, resource
budgets, result hash, row/column/null control totals, and blocker state. It does
not copy the question or parameter values. The result CSV necessarily contains
the selected data and must stay under ignored `outputs/` storage when private.

Database size and nanosecond modification time provide a cheap plan-to-execution
drift guard. This is not a cryptographic content identity. Dataset package hashes
remain a future evidence enhancement for immutable published snapshots.

## Command

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-query-execute `
  --request "outputs/<run-id>/analytics_request.yml" `
  --database "outputs/<run-id>/duckdb/operations_lab.duckdb" `
  --relationships "config/data_model/approved_relationships.yml" `
  --plan "outputs/<run-id>/analytics_query_plan/analytics_query_plan.yml" `
  --output "outputs/<run-id>/analytics_query_execution"
```

Existing byte-identical evidence is reused without rewriting. Different
existing execution evidence is never overwritten. Requests whose row order is
significant must include explicit `order_by`; otherwise order follows normal SQL
semantics and is not guaranteed across executions.
