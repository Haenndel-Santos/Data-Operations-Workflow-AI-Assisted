# Synthetic Pipeline Performance Baseline

## Purpose

`pipeline-performance-baseline` measures four known Pandas-heavy stages with a
generated local Parquet workload before an optimization is selected:

1. profiling;
2. cleaning;
3. schema and candidate-key inference;
4. candidate-relationship validation.

The harness creates deterministic synthetic tables, runs each stage in a fresh
child process, records bounded local evidence, and deletes the synthetic rows
after measurement. It accepts no external input or database path.

## Command

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab pipeline-performance-baseline `
  --rows-per-table 50000 `
  --table-count 3 `
  --output "outputs\<run-id>\pipeline_performance_baseline"
```

The workload is bounded to 100-1,000,000 rows per table and 2-12 tables. Each
stage has a bounded 10-900 second timeout. Run-specific evidence is never
overwritten or silently reused.

## Metrics

| Metric | Definition |
| --- | --- |
| Runtime | Wall-clock seconds inside the isolated worker stage |
| Peak process memory | Windows Peak Working Set or POSIX `ru_maxrss`, including the worker runtime |
| Peak Python allocation | `tracemalloc` peak for Python-managed allocations during the stage |
| Input bytes | Total bytes of the generated Parquet files |
| Scanned bytes | Unique full-input footprint inspected; repeated physical reads are not counted |
| Output bytes | Files produced by the measured stage |
| Temporary storage | Bytes left in the worker-specific temporary directory |

Compare runs only on the same machine and software environment. OS cache,
allocator, and scheduler variation make these engineering measurements rather
than production service-level guarantees.

## Phase 1 Measured Result

Both runs used Python 3.13.6, Pandas 3.0.3, PyArrow 24.0.0, Windows Peak
Working Set, 3 synthetic tables, 50,000 rows per table, 6 columns per table,
and the same 1,461,441-byte input with identical per-file SHA-256 values.

| Schema stage | Before | After | Change |
| --- | ---: | ---: | ---: |
| Peak process memory | 184,971,264 bytes | 134,606,848 bytes | -50,364,416 bytes (-27.23%) |
| Peak Python allocation | 16,773,488 bytes | 2,256,049 bytes | -86.55% |
| Runtime | 35.096404 s | 0.353394 s | -98.99% (99.31x faster) |
| Output | 7,282 bytes | 7,282 bytes | unchanged |

Before the change, schema inference loaded every Parquet table into Pandas and
built Python value sets across columns and tables. The optimized path:

- reads Arrow schema metadata without loading full DataFrames;
- computes row, null, uniqueness, and distinct-value evidence with local
  DuckDB aggregations over parameterized Parquet paths;
- evaluates candidate overlap with a DuckDB semi join only for name-eligible
  pairs;
- keeps legacy `detect_schema` and `identify_keys` functions available while
  routing `write_schema_outputs` through the bounded path;
- preserves the exact `schema.json` and `keys.json` contract in equivalence
  tests covering nulls, NaN, empty tables, repeated line references, primary
  key candidates, and foreign-key candidates.

Cleaning is now the largest measured stage in this workload. It remains a
future optimization candidate and must receive its own before/after contract
tests before any implementation change.

## Evidence And Safety Boundary

Each output directory contains:

- `pipeline_performance_baseline.yml` with workload hashes, environment,
  ranking, and disabled external-access controls;
- `pipeline_performance_metrics.csv` with one row per isolated stage;
- `pipeline_performance_report.md` with the local ranking.

The harness and optimization do not use EDS, public benchmark data, SQL Server,
a live provider, network access, credentials, approved state, upload, or
training. Key and relationship outputs remain automated candidates. They are
not promoted to approved model state, and repeated line-table references remain
non-unique unless evidence proves otherwise.
