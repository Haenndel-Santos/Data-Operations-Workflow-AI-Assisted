# Dataset Benchmark Answer Preparation Contract

## Module

```yaml
name: analytics_dataset_benchmark_preparation
version: 1
status: implemented_pre_execution_review
entrypoint: data_ops_lab.analytics_dataset_benchmark_preparation.run_analytics_dataset_benchmark_preparation
inputs:
  - versioned_answer_design_yaml
  - verified_dataset_manifest_yaml
  - immutable_local_duckdb_artifact
  - applied_approved_semantic_catalog_yaml
  - approved_relationship_registry_yaml
outputs:
  - analytics_dataset_benchmark_preparation.yml
  - analytics_dataset_benchmark_preparation_blockers.csv
  - analytics_dataset_benchmark_preparation_report.md
  - analytics_dataset_benchmark_execution_review.yml_when_ready
  - nested_recorded_translation_and_stage_5a_plan_evidence
dependencies:
  - analytics_nl_translation
  - analytics_semantic_adapter
  - analytics_query_plan
  - analytics_session
capabilities:
  - validate_bounded_answer_design
  - compile_recorded_semantic_intents
  - prepare_exact_stage_5a_plans
  - stop_for_aggregate_human_execution_review
workflows:
  - dataset_benchmark_answer_preparation
validation:
  - immutable_dataset_and_authority_hashes
  - verified_provenance_and_license
  - approved_semantics_and_relationships
  - bounded_english_recorded_intents
  - deterministic_output_aliases_and_order
  - exact_plan_hashes
tests:
  - tests/analytics_dataset_benchmark_preparation_test.py
failure_policy: fail_closed_before_stage_5b_and_never_overwrite_evidence
```

## Purpose

This Phase 5 module closes the authority gap between benchmark design and
expected-answer creation. A deterministic expected result cannot be collected
until its exact query plan exists, but the final dataset benchmark pack cannot
be reviewed until those results exist. Preparation therefore adds a narrower
human checkpoint before Stage 5B:

```text
versioned questions and expected semantic intents
  -> recorded Stage 5D compilation
  -> exact Stage 5A plans
  -> aggregate per-case execution review
  -> later bounded read-only answer collection
  -> candidate expected-answer pack
  -> separate final per-case benchmark review and approval
  -> offline evaluation
```

Preparation never calls Stage 5B. It opens the bound DuckDB artifact read-only
only for Stage 5A catalog validation. It does not read table rows, produce
answers, use Ollama or another live provider, access a network, or expand local
benchmark authority into upload, publication, or training.

## Answer Design

The version-1 design remains `candidate_for_execution_review`, binds the exact
dataset manifest, database, semantic state, and relationship registry by
SHA-256, and contains at most 25 cases. Each case contains:

- a stable case ID and bounded English question;
- explicit capability-coverage labels;
- one safe recorded semantic provider response;
- `single_row` or `ordered_rows` result shape;
- expected output aliases and comparison types;
- exact comparison or bounded per-column numeric tolerance.

The deterministic Stage 5D request must produce the designed aliases in the
same order. A `single_row` case cannot group by dimensions. An `ordered_rows`
case must have at least one dimension and explicit `order_by`. These checks
prevent a future expected-answer pack from silently accepting nondeterministic
row order or a changed semantic request.

## Execution Review

When every case reaches `ready_for_execution_review`, the module writes one
pending aggregate review. It binds the complete preparation manifest plus the
design, dataset manifest, database, semantic state, relationships, and every
exact Stage 5A plan SHA-256.

The human must inspect every case and decide whether its exact plan correctly
implements the question, including table grain, dimensions, measures, filters,
joins, parameter values, ordering, limit, output aliases, and comparison
policy. Approval authorizes only bounded local read-only collection of the
candidate answers. It does not approve the values that will be collected.

After collection, the resulting pack must still complete the separate
[Dataset Benchmark Review And Approval](analytics-dataset-benchmark-review.md)
workflow before
[Dataset-Backed Offline Benchmark Evaluation](analytics-dataset-benchmark-evaluation.md).

## Command

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-dataset-benchmark-answer-prepare `
  --design "datasets\benchmarks\manifests\northwind.answer-benchmark-design.yml" `
  --dataset-manifest "datasets\benchmarks\manifests\northwind.dataset-benchmark.yml" `
  --database "datasets\benchmarks\derived\northwind\northwind.duckdb" `
  --semantic-state "config\analytics\approved_semantic_catalog.yml" `
  --relationships "outputs\benchmarks\northwind-phase2-reviewed\approved_relationships.yml" `
  --output "outputs\benchmarks\northwind-phase5-answer-preparation-v1"
```

Byte-identical reruns reuse all evidence. A changed design, question, semantic
intent, source hash, nested checkpoint, or root output is never overwritten.
