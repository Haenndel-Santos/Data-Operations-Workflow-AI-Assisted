# Dataset Benchmark Answer Materialization Contract

## Module

```yaml
name: analytics_dataset_benchmark_materialization
version: 1
status: implemented_awaiting_final_review
entrypoint: data_ops_lab.analytics_dataset_benchmark_materialization.run_analytics_dataset_benchmark_materialization
inputs:
  - versioned_answer_design_yaml
  - verified_dataset_manifest_yaml
  - exact_preparation_manifest_yaml
  - completed_execution_review_yaml
  - immutable_local_duckdb_artifact
  - applied_approved_semantic_catalog_yaml
  - approved_relationship_registry_yaml
  - explicit_candidate_pack_output_path
  - new_evidence_output_directory
outputs:
  - candidate_expected_answer_pack_yaml_when_ready
  - analytics_dataset_benchmark_materialization.yml
  - analytics_dataset_benchmark_materialization_cases.csv
  - analytics_dataset_benchmark_materialization_blockers.csv
  - analytics_dataset_benchmark_materialization_report.md
  - nested_bounded_stage_5b_execution_evidence
dependencies:
  - analytics_dataset_benchmark_preparation
  - analytics_query_execution
  - analytics_dataset_benchmark
capabilities:
  - validate_completed_exact_plan_review
  - execute_reviewed_plans_sequentially
  - materialize_typed_candidate_answers
  - stop_for_separate_final_human_review
workflows:
  - dataset_benchmark_answer_materialization
validation:
  - exact_source_and_preparation_hashes
  - completed_human_scope_and_case_decisions
  - prepared_request_and_plan_hashes
  - immutable_recheck_before_and_after_each_query
  - bounded_result_schema_types_hashes_and_control_totals
  - persistent_companion_evidence_hashes
  - complete_candidate_pack_contract
tests:
  - tests/analytics_dataset_benchmark_materialization_test.py
failure_policy: fail_closed_without_candidate_pack_and_never_overwrite_evidence
```

## Purpose

This module is the controlled bridge between the exact-plan review and the
separate expected-answer review. It accepts only a completed, hash-bound human
decision that approves every prepared Stage 5A plan for local read-only answer
collection. It does not infer approval from a pending template or from the fact
that a plan can execute.

Cases run in design order and one at a time. Before and after every Stage 5B
query, the module rechecks the answer design, dataset manifest, DuckDB artifact,
semantic state, relationship registry, preparation manifest, completed review,
request, and reviewed plan. Stage 5B then independently recompiles the request
and requires the reviewed plan to match before opening DuckDB read-only.

The resulting values are converted to the benchmark pack's explicit comparison
types and checked against the execution manifest, CSV hash, column order,
DuckDB types, row count, column count, null count, no-row status, and truncation
flag. Ambiguous CSV serialization of mixed empty strings and null strings fails
closed.

## Authority Boundary

The execution review must set these scopes exactly:

- `local_read_only_answer_collection: approved`;
- `live_provider_use: not_authorized`;
- `external_upload: not_authorized`;
- `model_training: not_authorized`;
- `publication: not_authorized`.

Every prepared case ID and exact plan SHA-256 must also be approved with human
notes. Materialization does not call Ollama, another model, narration, an
external service, or a production database. Limits are fixed at one thread,
10,000 rows, 10 MB result bytes, 30 seconds, 512 MB memory, and 256 MB temporary
storage per case; the CLI exposes no bypass.

Successful output remains `candidate_for_review`. It must pass the separate
[Dataset Benchmark Review And Approval](analytics-dataset-benchmark-review.md)
workflow before
[Dataset-Backed Offline Benchmark Evaluation](analytics-dataset-benchmark-evaluation.md)
can use it.

## Command

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-dataset-benchmark-answer-materialize `
  --design "datasets\benchmarks\manifests\northwind.answer-benchmark-design.yml" `
  --dataset-manifest "datasets\benchmarks\manifests\northwind.dataset-benchmark.yml" `
  --preparation-manifest "outputs\benchmarks\northwind-phase5-answer-preparation-v1\analytics_dataset_benchmark_preparation.yml" `
  --execution-review "datasets\benchmarks\manifests\northwind.answer-execution-review.yml" `
  --database "datasets\benchmarks\derived\northwind\northwind.duckdb" `
  --semantic-state "config\analytics\approved_semantic_catalog.yml" `
  --relationships "outputs\benchmarks\northwind-phase2-reviewed\approved_relationships.yml" `
  --pack-output "datasets\benchmarks\manifests\northwind.answer-benchmark-pack.yml" `
  --output "outputs\benchmarks\northwind-phase5-answer-materialization-v3"
```

Successful evidence and a byte-identical pack are reusable only while the
case CSV, blocker CSV, and report still match the hashes in the root manifest.
A partial, different, or previously blocked run is never overwritten; use a
new evidence directory after correcting a blocker, and a new pack path only if
the candidate content changes.
