# Dataset-Backed Offline Benchmark Evaluation Contract

## Module

```yaml
name: analytics_dataset_benchmark_evaluation
version: 1
status: implemented_offline_approved_dataset_execution
entrypoint: data_ops_lab.analytics_dataset_benchmark_evaluation.run_analytics_dataset_benchmark_evaluation
inputs:
  - verified_dataset_manifest_yaml
  - local_immutable_duckdb_artifact
  - applied_approved_semantic_catalog_yaml
  - approved_relationship_registry_yaml
  - reviewed_benchmark_pack_yaml
  - generated_benchmark_approval_yaml
outputs:
  - analytics_dataset_benchmark_evaluation.yml
  - analytics_dataset_benchmark_evaluation_cases.csv
  - analytics_dataset_benchmark_evaluation_blockers.csv
  - analytics_dataset_benchmark_evaluation_report.md
failure_policy: validate_all_authority_before_read_only_execution_and_never_overwrite_evidence
```

## Purpose

This Stage 5E executor measures expected answers against an already approved
local dataset package. It consumes the approval produced by
[Dataset Benchmark Review And Approval](analytics-dataset-benchmark-review.md)
and reuses the existing Stage 5D, Stage 5A, and Stage 5B boundaries.

No EDS or public benchmark was executed during implementation. Tests create
only temporary synthetic DuckDB files and temporary human-review authority.

## Execution Gates

```text
verified package + generated approval
  -> complete dataset-backed authority validation
  -> exact SHA-256 recheck of all six inputs
  -> recorded offline Stage 5D translation
  -> exact expected Stage 5A request match
  -> Stage 5A read-only catalog planning
  -> exact SHA-256 recheck immediately before each Stage 5B call
  -> Stage 5B plan revalidation and bounded read-only execution
  -> exact or reviewed numeric expected-result comparison
  -> final SHA-256 recheck before accepting evidence
```

Planning does not start when initial authority is blocked. Stage 5B does not
start when translation, exact request matching, planning, or the pre-query hash
recheck fails. Stage 5B independently recompiles the request, compares the
reviewed plan, checks database drift, disables external access and extension
autoload, and opens DuckDB in read-only mode.

## Comparison

`exact` compares the complete ordered CSV representation, column names, row and
column counts, null count, no-row state, and execution status.

`numeric_tolerance` keeps every undeclared column exact. For each reviewed
numeric column, the comparison accepts a value when:

```text
absolute_difference <= max(absolute_tolerance,
                           relative_tolerance * abs(expected_value))
```

Null expectations remain exact. Tolerances are accepted only because the pack
validator and human review already restricted them to declared numeric columns,
finite non-negative bounds, and at least one non-zero bound.

## Status And Metrics

- `passed`: every case passed request, pipeline, result, and control checks.
- `failed`: authority was valid and execution was controlled, but at least one
  reviewed expectation did not match.
- `blocked`: authority, immutable inputs, or a prerequisite execution gate
  failed; drifted case evidence is discarded.

Metrics report overall, pipeline, request, result, control, exact-result, and
numeric-tolerance accuracy. A failed expectation is not mislabeled as a
contract blocker.

## Fixed Limits

- 10,000 result rows;
- 10 MB result bytes;
- 30 seconds per query;
- 512 MB DuckDB memory;
- one execution thread;
- 256 MB temporary storage.

The CLI exposes no overrides for SQL, provider, network, limits, extensions, or
database mode.

## Evidence And Privacy

Persistent evidence contains safe dataset/pack IDs, source hashes, fixed
limits, case IDs, comparison modes, stage statuses, booleans, metrics, and
blockers. It omits questions, provider responses, expected and actual rows,
review notes, generated SQL, parameters, temporary paths, and narration.

Runtime question, response, translation, request, plan, result, and case files
exist only inside an automatically deleted temporary directory. Byte-identical
reruns reuse evidence; different evidence is never overwritten.

## Boundaries

- Recorded local provider responses only; no model API or network.
- Local approved DuckDB only; no SQL Server or external database connector.
- Read-only analytical queries only; no migration, import, export, or sync.
- No external upload, model training, publication, or narration authority.
- `passed` proves the reviewed offline cases, not live-model quality or general
  business correctness.

## Command

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-dataset-benchmark-evaluate `
  --dataset-manifest "<verified-dataset-manifest.yml>" `
  --database "<immutable-dataset.duckdb>" `
  --semantic-state "<approved-semantic-catalog.yml>" `
  --relationships "<approved-relationships.yml>" `
  --pack "<reviewed-benchmark-pack.yml>" `
  --approval "<generated-benchmark-approval.yml>" `
  --output "outputs/<run-id>/analytics_dataset_benchmark_evaluation"
```

Do not point this command at EDS, AdventureWorks, Northwind, Pubs, or another
real dataset until that exact package has completed all existing provenance,
license, semantic, relationship, expected-answer, review, and approval gates.
