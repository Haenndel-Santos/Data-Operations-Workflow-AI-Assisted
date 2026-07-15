# Benchmark Datasets

## Purpose

Provide reproducible, local datasets for evaluating schema discovery, query
planning, relationship validation, and future natural-language analysis across
domains other than EDS. This is an evaluation and retrieval foundation, not
authorization for model-parameter training.

## Storage Contract

| Area | Git | Rule |
| --- | --- | --- |
| `datasets/benchmarks/raw/` | Ignored | Immutable user-supplied downloads; never execute in place. |
| `datasets/benchmarks/derived/` | Ignored | Reproducible DuckDB, Parquet, manifests, and reports. |
| `datasets/benchmarks/manifests/` | Versioned | Checksums, provenance status, processing status, and approval boundaries. |
| `datasets/benchmarks/work/` | Ignored | Disposable conversion workspace only. |

The authoritative local inventory is
[`datasets.yml`](../datasets/benchmarks/manifests/datasets.yml). The storage
layout is summarized in the [benchmark README](../datasets/benchmarks/README.md).
The provenance, reproduction, schema, relationship, and permitted-use gate is
defined in [Reference Dataset Validation](reference-dataset-validation.md).

## Safe SQL Conversion

`benchmark-convert-sql` accepts a local `.sql` file containing SQL Server
`CREATE TABLE` and `INSERT` statements. SQLGlot parses the T-SQL syntax and the
module materializes normalized tables in DuckDB before exporting one
Zstandard-compressed Parquet file per table.

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab benchmark-convert-sql `
  --source "datasets\benchmarks\raw\northwind\instnwnd.sql" `
  --dataset northwind `
  --output "datasets\benchmarks\derived\northwind"
```

The command does not execute source SQL. It ignores drops, operational alters,
views, procedures, triggers, credentials, and external operations. Declared
foreign keys become unapproved relationship candidates. Existing derived
outputs are accepted only when source and artifact hashes still match;
otherwise the command fails without overwriting them.

## Current Inventory

| Dataset | Local state | Evidence | Remaining gate |
| --- | --- | --- | --- |
| Northwind | `semantic_candidate_ready_for_human_review` | Phase 2 passed; candidate has 13 tables, 60 dimensions, 19 measures, 18 approved paths, zero blockers/ambiguities | Complete the separate 111-entity semantic review; do not apply before approval. |
| Pubs | Converted: 11 tables, 255 rows | DuckDB, Parquet, 10 relationship candidates | Confirm source/license; assess two replacement characters; review schema/relationships. |
| AdventureWorks 2025 | Official backup restored locally as `READ_ONLY` | Exact release hash; `RESTORE VERIFYONLY` and `DBCC CHECKDB` passed; 71 tables, 20 views, 90 declared foreign keys, 760,167 aggregate rows | Implement a reproducible read-only DuckDB/Parquet export, then review schema, relationships, and benchmark use. |
| Contoso warehouse recipe | Raw SQL/Markdown retained | Schema/load recipe only | Confirm source/license; acquire an authorized local data package without external execution. |

The local AdventureWorks backup exactly matches Microsoft's official
`AdventureWorks2025.bak` release (50,229,248 bytes; SHA-256
`fa6a2a5d431ad88123f89b36b1f2c7e42ca4bdf6b293269a44df80f6de3738a5`).
It is restored only in the local SQL Server 2025 Developer instance, database
`AdventureWorks2025`, and was set to `READ_ONLY` immediately after restoration.
The SQL Server restore is a temporary compatibility bridge; no derived export
or relationship approval has been produced from it yet.

## Northwind Phase 2 And 3 Boundary

Both local Northwind scripts are byte-identical to their official Microsoft
`sql-server-samples` files at commit
`2f85f3724ee45776a5183ed34d064488a6e1dc53`, and the repository license is MIT.
The canonical source remains unchanged at SHA-256
`3cc62b3fca6d244a47dbde698b809331e4f85988a0685b2b370717d431e94871`.

An independent restricted conversion reproduced the exact schema, 13 table
counts, all 13 Parquet hashes, all 13 relationship candidates, and the report.
Read-only profiling found zero null/duplicate violations across 13 declared
primary keys and zero orphans/non-unique targets across all 13 declared foreign
keys. Eleven relationships have positive source-row coverage. The two
`customer_customer_demo` relations remain evidence-limited because their source
table is empty.

The project owner authorized local conversion, profiling, benchmark design, and
offline evaluation on 2026-07-15, then accepted all 13 exact relationships with
explicit notes for the two empty-table bridges and the employee hierarchy. The
completed review revalidated as `ready_for_semantic_modeling`; its generated
approved-relationship registry remains a reproducible projection rather than a
replacement for human authority. External upload, publication, and model-
parameter training remain not authorized. The exact versioned dataset authority is
[`northwind.reference.yml`](../datasets/benchmarks/manifests/northwind.reference.yml),
the relationship authority is
[`northwind.relationship-review.yml`](../datasets/benchmarks/manifests/northwind.relationship-review.yml),
and generated technical evidence remains under ignored `outputs/benchmarks/`.

Phase 3 now has a versioned
[`Northwind semantic candidate`](../datasets/benchmarks/manifests/northwind.semantic-catalog-candidate.yml)
and a focused [semantic review guide](northwind-semantic-review.md). Metadata-only
compilation found 13 semantic tables, 60 dimensions, 19 measures, 18 paths over
approved relationships, 339 normalized terms, zero ambiguities, and zero
blockers. The separate 111-entity review remains pending; no semantic registry
or adapter authority has been applied.

The downstream
[dataset-backed benchmark contract](analytics-dataset-benchmark.md) is a strict
gate, not an approval shortcut. It requires a verified immutable dataset
manifest, approved semantic and relationship hashes, a candidate expected-answer
pack, and a separate hash-bound human approval. The validator hashes the DuckDB
artifact as an opaque file and does not open it, query it, or grant benchmark,
upload, provider, publication, or training authority.

## Validation

Focused converter tests use temporary synthetic scripts and verify restricted
statement handling, identity generation, idempotency, source-change refusal,
and cleanup after failure. The real Northwind/Pubs conversion was additionally
checked by comparing every manifest count and SHA-256 across DuckDB and Parquet.
Reference-dataset tests use synthetic temporary databases and cover valid
pending review, completed exact review, orphan and duplicate-key blockers,
preflight refusal before database access, immutable evidence, and CLI shape.
