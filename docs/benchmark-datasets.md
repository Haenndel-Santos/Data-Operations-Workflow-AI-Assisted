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
| Northwind | Converted: 13 tables, 3,308 rows | DuckDB, Parquet, 13 relationship candidates | Confirm exact source/license and review schema/relationships. |
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

## Approval Boundary

The user authorized relocation and efficient local conversion. The following
remain unapproved: benchmark acceptance, relationship promotion, external
upload, publication, and model-parameter training. Future evaluation should
first define expected questions, approved plans/results, control totals, and
privacy/licensing evidence.

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
