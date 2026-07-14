# Dataset Benchmark Review And Approval Contract

## Modules

```yaml
review:
  name: analytics_dataset_benchmark_review
  version: 1
  entrypoint: data_ops_lab.analytics_dataset_benchmark_review.run_analytics_dataset_benchmark_review
  output: analytics_dataset_benchmark_review.yml
approval:
  name: analytics_dataset_benchmark_approval
  version: 1
  entrypoint: data_ops_lab.analytics_dataset_benchmark_review.run_analytics_dataset_benchmark_approval
  outputs:
    - analytics_dataset_benchmark_approval_plan.yml
    - analytics_dataset_benchmark_approval_blockers.csv
    - analytics_dataset_benchmark_approval_report.md
  applied_output: explicit_user_supplied_approval_path
failure_policy: fail_closed_and_preserve_review_approval_and_evidence
```

## Purpose

This Stage 5E governance contract creates the human authority required by the
[dataset-backed validation contract](analytics-dataset-benchmark.md). It keeps
review preparation, human decisions, approval generation, and future benchmark
execution as separate operations.

No real dataset review or approval was created during implementation. Tests use
only temporary synthetic DuckDB files, and the workflow never opens or queries
them.

## Workflow

1. Validate the candidate dataset manifest, opaque DuckDB hash, applied semantic
   state, approved relationships, and candidate pack.
2. Generate a pending review bound to all five sources by SHA-256.
3. A human inspects the exact bound pack and records identity, time, notes,
   scope decisions, and decisions for every case.
4. Run approval in dry-run mode and inspect the proposed approval and blockers.
5. Run again with `--apply` only after accepting the dry-run evidence.
6. Supply the generated approval to `analytics-dataset-benchmark-validate`.

Review preparation fails if the candidate contract already has blockers. Any
source change after preparation blocks approval.

## Review Decisions

The review file lists case IDs but does not duplicate questions, provider
responses, expected requests, expected rows, comparison values, or notes into
approval evidence. The candidate pack hash binds that content.

Every case must explicitly approve:

- the recorded provider response;
- the expected Stage 5A request;
- the typed expected result;
- the exact or numeric-tolerance comparison policy;
- non-empty human notes.

Every expected case ID must appear exactly once. Pending, rejected, missing,
duplicate, unknown, or incomplete case decisions block approval.

## Scope Decisions

The local offline evaluation scope must be `approved`. The following scopes
must be explicitly `not_authorized`:

- live provider use;
- external upload;
- model training.

Every scope decision requires human notes. Version 1 refuses attempts to expand
a dataset benchmark approval into provider, disclosure, or training authority.

## Approval Output

The generated approval contains:

- exact dataset and pack IDs;
- SHA-256 bindings for the manifest, database, semantic state, relationships,
  and pack;
- the completed review SHA-256 and normalized decision digest;
- the bounded approval booleans consumed by the final validator;
- human reviewer identity and timezone-aware ISO-8601 time.

Dry-run is the default and does not write the approval file. `--apply` writes
only the explicit `--approval-output` path. An identical approval is reused; a
different existing file is never overwritten, and no replacement flag exists.

## Evidence And Safety

- The DuckDB file is hashed as an opaque artifact and never connected to.
- No SQL, catalog, table, row, query, result, provider, network, upload,
  training, import, migration, synchronization, or narration is used.
- Review preparation never approves anything.
- Approval does not execute benchmark cases or establish answer correctness.
- Questions, provider responses, expected rows, and review notes are omitted
  from approval evidence.
- Existing review, approval, and generated evidence are protected from
  divergent overwrite.

## Commands

Prepare the pending review:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-dataset-benchmark-review `
  --dataset-manifest "<verified-dataset-manifest.yml>" `
  --database "<immutable-dataset.duckdb>" `
  --semantic-state "<approved-semantic-catalog.yml>" `
  --relationships "<approved-relationships.yml>" `
  --pack "<candidate-benchmark-pack.yml>" `
  --output "<benchmark-review.yml>"
```

Validate a completed review without writing approval:

```powershell
.\.venv\Scripts\python.exe -m data_ops_lab analytics-dataset-benchmark-approval `
  --dataset-manifest "<verified-dataset-manifest.yml>" `
  --database "<immutable-dataset.duckdb>" `
  --semantic-state "<approved-semantic-catalog.yml>" `
  --relationships "<approved-relationships.yml>" `
  --pack "<candidate-benchmark-pack.yml>" `
  --review "<completed-benchmark-review.yml>" `
  --approval-output "<benchmark-approval.yml>" `
  --output "outputs/<run-id>/analytics_dataset_benchmark_approval"
```

The apply form adds `--apply`. Do not use real EDS or public benchmark files to
exercise this workflow before their provenance, license, semantic,
relationship, expected-answer, and use reviews are complete.
