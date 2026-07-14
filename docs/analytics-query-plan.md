# Structured Analytics Query Plan Contract

## Module

```yaml
name: analytics_query_plan
version: 1
status: dry_run_only
entrypoint: data_ops_lab.analytics_query_plan.run_analytics_query_plan
inputs:
  - structured_request_yaml
  - local_duckdb_database
  - approved_relationship_registry
outputs:
  - analytics_query_plan.yml
  - analytics_query_blockers.csv
  - analytics_query_report.md
failure_policy: fail_closed_and_preserve_existing_outputs
```

## Contract Boundary

The module compiles a limited structured request into a parameterized analytical `SELECT` plan. It does not accept raw SQL, execute the compiled query, write to the database, connect to an external system, or expose filter values in generated artifacts.

The returned Python result retains parameters in memory so a future separately authorized executor can use the exact validated plan. The CLI prints only status and artifact paths.

The plan source also records the DuckDB file size and nanosecond modification
time. Stage 5B uses these values with the catalog and input hashes to reject
ordinary database drift between review and execution without hashing an entire
large database file.

## Inputs

- A version-1 YAML request following [the AI analytics backend contract](ai-analytics-backend.md).
- An existing local DuckDB file opened with `read_only=True`.
- A YAML mapping containing `approved_relationships`. Cross-table joins fail closed unless their exact table/column pair is present in that list.

## Statuses

- `ready_for_execution_review`: catalog resolution, relationship governance, operations, limits, aliases, and parameter types are valid.
- `blocked`: at least one input, catalog, relationship, or request-contract check failed; SQL is omitted.

Neither status authorizes execution by itself. Stage 5B is a separate explicit
command and contract; see [Controlled Analytics Query Execution](analytics-query-execution.md).

## Command

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-query-plan `
  --request "outputs/<run-id>/analytics_request.yml" `
  --database "outputs/<run-id>/duckdb/operations_lab.duckdb" `
  --relationships "config/data_model/approved_relationships.yml" `
  --output "outputs/<run-id>/analytics_query_plan"
```

Outputs are deterministic. A byte-identical rerun does not rewrite them, and different existing plan evidence is never overwritten.
