# Dataset-Backed Benchmark Validation Contract

## Module

```yaml
name: analytics_dataset_benchmark
version: 1
status: implemented_dry_run_validation
entrypoint: data_ops_lab.analytics_dataset_benchmark.run_analytics_dataset_benchmark_validation
inputs:
  - verified_dataset_manifest_yaml
  - local_immutable_duckdb_artifact
  - applied_approved_semantic_catalog_yaml
  - approved_relationship_registry_yaml
  - candidate_benchmark_pack_yaml
  - separate_benchmark_approval_yaml
outputs:
  - analytics_dataset_benchmark_validation.yml
  - analytics_dataset_benchmark_blockers.csv
  - analytics_dataset_benchmark_report.md
failure_policy: fail_closed_without_opening_dataset_and_preserve_existing_evidence
```

## Purpose

This Stage 5E contract binds a local dataset-backed benchmark before any query
can run. It validates immutable dataset identity, provenance, license, semantic
state, approved relationships, expected requests/results, comparison rules, and
a separate human approval by SHA-256.

The command is a dry-run. It hashes the DuckDB artifact as an opaque local file
but never opens it, reads its catalog or rows, executes a query, invokes a model,
or accesses a network.

Existing Northwind, Pubs, and AdventureWorks inventory or conversion manifests
do not satisfy this contract. Their current governance state explicitly leaves
benchmark use and/or relationships pending.

## Authority Separation

```text
verified dataset manifest
  + immutable DuckDB SHA-256
  + applied semantic-state SHA-256
  + approved-relationship SHA-256
  + candidate expected-answer pack SHA-256
  + separate human benchmark approval
  -> ready_for_offline_evaluation
```

The candidate pack cannot approve itself. The approval file identifies the
dataset and pack, binds every supplied input hash, and separately confirms that
recorded responses, expected requests, expected results, comparison policy, and
local offline evaluation were reviewed.

## Dataset Manifest

The version-1 dataset manifest requires:

- status `verified_dataset_package`;
- a stable dataset ID;
- classification `synthetic` or `public`;
- format `duckdb`;
- exact artifact byte size and SHA-256;
- verified provenance with a source reference;
- verified license with an identifier;
- bindings to the applied semantic state and approved relationships.

Private datasets are outside this version-1 benchmark contract. The artifact is
hashed once with a sequential read. Size and modification time are checked
before and after hashing to detect concurrent changes.

## Benchmark Pack

The pack remains `candidate_for_review` and contains at most 100 cases. Each
case has:

- one bounded question;
- one safe recorded semantic provider response;
- one expected Stage 5A request preserving the exact question;
- expected status, typed columns, ordered rows, and row/column/null controls;
- `exact` or `numeric_tolerance` comparison rules.

Expected result types are `string`, `integer`, `decimal`, `float`, and
`boolean`. Multi-row answers require explicit `order_by`.

Exact comparison cannot declare tolerances. Numeric tolerance must name a
declared numeric column and provide finite non-negative absolute and relative
values, at least one greater than zero. Relative tolerance cannot exceed 1.
Columns without an explicit reviewed tolerance remain exact.

## Separate Approval

The version-1 approval must be `approved`, match the dataset and pack IDs, and
bind the dataset manifest, DuckDB artifact, semantic state, relationships, and
pack by SHA-256. It requires human identity and time plus explicit approval of:

- local offline evaluation;
- recorded provider responses;
- expected requests;
- expected results;
- comparison policy.

The same approval must explicitly leave live-provider use, external upload, and
model training disabled. This prevents a local benchmark decision from silently
expanding into disclosure or training authority.

## Status

- `ready_for_offline_evaluation`: every input and approval matches exactly.
- `blocked`: any identity, hash, provenance, license, semantic, relationship,
  expected-answer, comparison, or approval check failed.

Readiness is evidence for a future separately implemented offline evaluator. It
does not execute or authorize live-provider evaluation.

## Evidence

Persistent outputs contain IDs, hashes, counts, status, and safety controls.
They omit questions, provider responses, expected requests, expected rows,
approval identity, paths, and database content. Byte-identical reruns reuse
evidence; divergent evidence is never overwritten.

## Command

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-dataset-benchmark-validate `
  --dataset-manifest "<verified-dataset-manifest.yml>" `
  --database "<immutable-dataset.duckdb>" `
  --semantic-state "<approved-semantic-catalog.yml>" `
  --relationships "<approved-relationships.yml>" `
  --pack "<candidate-benchmark-pack.yml>" `
  --approval "<benchmark-approval.yml>" `
  --output "outputs/<run-id>/analytics_dataset_benchmark_validation"
```

Do not point this command at EDS or a pending benchmark merely to produce a
ready status. Complete provenance, license, semantic, relationship, expected-
answer, and benchmark-use review first.
