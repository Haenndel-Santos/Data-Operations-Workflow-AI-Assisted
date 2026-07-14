# Reference Dataset Validation

## Purpose

`reference-dataset-validate` closes the technical onboarding gates for a local
reference dataset without turning profiling evidence into modeling authority.
It validates exact provenance metadata, license evidence, source and artifact
hashes, an independent conversion, the converted schema, declared primary keys,
declared foreign-key candidates, permitted uses, and an optional separate human
relationship review.

The module is the Phase 2 bridge between safe benchmark conversion and Phase 3
semantic modeling. It does not create a semantic catalog, expected-answer pack,
live-provider request, upload, publication, or model-parameter training scope.

## Inputs

The version-1 reference manifest records:

- a normalized dataset ID and intended role;
- the immutable local source path, byte count, and SHA-256;
- a fixed official repository path, Git commit, blob, and permalink;
- a verified SPDX license and fixed license permalink;
- the exact current conversion-manifest path and SHA-256;
- a separately generated reproduction manifest;
- source-declared primary keys to test technically;
- the expected number of pending source-declared relationships; and
- explicit permitted-use scopes.

Northwind's current versioned input is
[`northwind.reference.yml`](../datasets/benchmarks/manifests/northwind.reference.yml).
Raw, derived, reproduction, and generated validation artifacts remain outside
Git according to the benchmark storage contract.

## Validation Order

```text
reference manifest
  -> provenance, license, source hash, and use-scope preflight
  -> current conversion manifest and every artifact hash
  -> independent conversion equivalence
  -> read-only DuckDB schema and row-count comparison
  -> declared primary-key null and duplicate checks
  -> declared foreign-key orphan and target-uniqueness checks
  -> pending or completed exact relationship review
```

Any provenance, license, source, artifact, reproduction, or use-scope blocker
prevents DuckDB access. When preflight passes, the module opens the bound
database with DuckDB `read_only=True`, issues only generated catalog/count/key/
orphan queries over validated normalized identifiers, and confirms the database
SHA-256 before and after profiling.

## Reproducibility Rule

DuckDB database-file bytes may differ across independent materializations even
when content is equivalent. The current database remains individually bound by
its exact artifact SHA-256. Independent reproduction is established by matching:

- source SHA-256;
- conversion contract and parser version;
- normalized tables, columns, types, and row counts;
- every Zstandard Parquet SHA-256;
- relationship-candidate SHA-256; and
- conversion-report SHA-256.

The independently reproduced DuckDB file must also match its own manifest hash.
Its binary hash is evidence, but it is not required to equal the current
database's binary hash.

## Relationship Authority

Technical validity and human authority remain separate:

| State | Meaning |
| --- | --- |
| `ready_for_relationship_review` | All technical gates passed; every relationship is still pending. |
| `ready_for_semantic_modeling` | A separate exact completed review accepted or rejected every candidate. |
| `blocked` | At least one provenance, license, artifact, schema, key, relationship, scope, or review contract failed. |

Without `--review`, the output includes `relationship_review.yml` with every
decision set to `pending`, exact source/candidate hashes, and row-level technical
counts only. A completed review must:

- bind to the exact reference-manifest and candidate hashes;
- contain one decision for every exact candidate;
- set each decision to `accepted` or `rejected`;
- record reviewer, ISO-8601 review time, and notes per decision;
- approve local offline relationship use; and
- leave upload, publication, and model-parameter training not authorized.

Completing a review requires a new validation output directory. Existing
evidence is immutable and divergent content is never overwritten.

## Command

Prepare technical evidence and a pending relationship review:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab reference-dataset-validate `
  --manifest "datasets\benchmarks\manifests\northwind.reference.yml" `
  --output "outputs\benchmarks\northwind-phase2-validation"
```

After a human completes a copy of the generated review, validate the exact
authority into a new directory:

```powershell
.\.venv\Scripts\python.exe -m data_ops_lab reference-dataset-validate `
  --manifest "datasets\benchmarks\manifests\northwind.reference.yml" `
  --review "<completed-relationship-review.yml>" `
  --output "outputs\benchmarks\northwind-phase2-reviewed"
```

## Northwind Evidence

The 2026-07-15 local run produced `ready_for_relationship_review` with zero
blockers:

- 13 tables and 3,308 rows matched the current and reproduced conversions;
- all 13 Parquet artifacts were byte-identical across independent conversion;
- all 13 source-declared primary keys had zero null key rows and zero duplicate
  key groups;
- all 13 source-declared foreign keys had zero orphan rows and unique targets;
- 11 relationships had positive non-null source-row coverage; and
- the two `customer_customer_demo` relationships had no positive row coverage
  because both involved candidate source/target tables contain zero rows.

The project owner explicitly approved local conversion, profiling, benchmark
design, and offline evaluation. The 13 relationship decisions remain pending;
external upload, publication, and model-parameter training remain not
authorized.
