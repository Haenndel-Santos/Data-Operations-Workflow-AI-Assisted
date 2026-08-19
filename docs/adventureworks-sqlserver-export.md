# AdventureWorks Read-Only SQL Server Export

## Purpose And Authority

`benchmark-export-sqlserver` is the Phase 5.2 compatibility bridge for the
selected AdventureWorks 2025 holdout. The project owner authorized this exact
local operation on 2026-07-22: read the already restored, read-only
`AdventureWorks2025` database on the default local SQL Server Developer
instance and create local DuckDB/Parquet evidence.

The command does not approve schema candidates, relationships, benchmark use,
semantic definitions, a provider call, upload, publication, or model-parameter
training. It never restores a backup, changes a database option, executes
source SQL, or connects to a remote or named SQL Server instance.

## Module Contract

| Field | Contract |
| --- | --- |
| Name | `benchmark-export-sqlserver` |
| Version | `1` |
| Status on success | `ready_for_local_benchmark` |
| Entrypoint | `data_ops_lab.benchmark_sqlserver_export.run_benchmark_sqlserver_export` |
| Required inputs | Exact local `.bak` path, dataset name, database name, new output directory |
| Explicit gate | `--execute` after separate local-export authority |
| Optional inputs | Local server alias, Microsoft ODBC Driver 17/18, batch size `1-50000` |
| Runtime dependency | Optional `pyodbc>=5.2,<6`; base/offline installs do not require it |
| Outputs | DuckDB, one Zstandard Parquet per table, conversion manifest, schema candidates, relationship candidates, Markdown report |
| Failure policy | Fail closed, roll back/close the connection, remove partial staging, never overwrite divergent output |

The source backup remains provenance evidence and is hashed before and after
export. The connection uses Windows integrated authentication,
`ApplicationIntent=ReadOnly`, the ODBC read-only access attribute, manual
transactions, and a serializable read transaction. Export proceeds only when
SQL Server reports the exact database as `ONLINE` and `READ_ONLY`.

Only `localhost`, `127.0.0.1`, `.`, and `(local)` are accepted, all referring to
the default local instance. Driver selection is allowlisted to Microsoft's ODBC
Driver 17 or 18, preventing connection-string field injection. No credentials
are accepted by the command.

## Deterministic Materialization

The exporter reads ordinary user tables in normalized schema/table order. Each
table must have a source-declared primary key; rows are ordered by that exact
key and fetched in bounded batches. Unsupported SQL Server types, normalized
identifier collisions, missing keys, malformed foreign keys, unexpected nulls,
source drift, or output drift stop the run.

PyArrow writes fixed-schema Parquet version 2.6 with Zstandard compression,
disabled dictionaries, and bounded row groups. DuckDB tables are then created
only from those generated Parquet files. A repeated call reuses an existing
output only when source hash, dataset, exporter version, database, local server,
ODBC driver, batch size, and every artifact hash still match.

## Schema And Relationship Boundary

`schema_candidates.yml` preserves source-declared primary keys as
`pending_review`. `relationship_candidates.yml` version 2 preserves each
source foreign-key constraint as one ordered pair of `source_columns` and
`target_columns`, including composite keys. Technical declarations are
evidence, not approval.

`reference-dataset-validate` version 3 accepts both the existing relationship
artifact v1 (single `source_column`/`target_column`) and v2. For v2 it profiles
null coverage, orphan rows, and target uniqueness over the full ordered column
set. The generated relationship review and approved-registry projection remain
version 2 and pending until a separate complete human review is supplied.
Northwind's version-1 artifacts and review shape remain supported.

## Local Prerequisites (Phase 5.2 stop state)

Phase 5.2 has been stopped on local prerequisites, not on contract work. Before
resuming, from an **elevated** PowerShell session on the workstation that holds
the ignored raw artifact:

    Get-Service MSSQLSERVER, SQLBrowser, SQLWriter          # confirm the default instance is installed
    Start-Service MSSQLSERVER                                # requires local administrator authority
    Test-Path "datasets\benchmarks\raw\adventureworks\AdventureWorks2025.bak"

Expected: `MSSQLSERVER` reports `Running`, and the `.bak` exists at the exact
path the versioned inventory names (its SHA-256 is recorded in
`datasets/benchmarks/manifests/datasets.yml`). If either check fails, do not
substitute another instance or another backup: the export contract binds the
default instance and the exact source hash. Starting the service and restoring
the ignored artifact are local-administrator actions and are not performed by
agents.

## Usage

Install the optional local adapter without changing the default offline suite:

```powershell
.\.venv\Scripts\python.exe -m pip install ".[sqlserver]"
```

Then, only while the authorized default service is running:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab benchmark-export-sqlserver `
  --source-backup "datasets\benchmarks\raw\adventureworks\AdventureWorks2025.bak" `
  --dataset adventureworks_2025 `
  --database AdventureWorks2025 `
  --output "datasets\benchmarks\derived\adventureworks-2025" `
  --execute
```

The real Phase 5.2 gate additionally requires an independent second export,
hash/equivalence validation, a versioned reference manifest, and
`reference-dataset-validate` stopping at `ready_for_relationship_review`.

## Tests

The offline test double covers the explicit execution gate, read-only database
preflight, source preservation, bounded Parquet/DuckDB materialization,
independent artifact reproducibility, idempotent reuse, configuration drift,
connection-string allowlists, ODBC access-mode binding, composite relationships,
staging cleanup, and CLI shape. Reference validation separately covers v1
compatibility and v2 composite technical evidence without auto-approval.

The default suite never connects to SQL Server. A real export is operational
evidence and must be reported separately from offline test results.
