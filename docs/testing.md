# Testing

## Safe Offline Validation

The main suite does not require network access, external databases, credentials, migrations, or production data. Tests write generated artifacts under pytest temporary directories and include checks that protected inputs and approved files remain unchanged.

Because the relocated `.venv` still references the previous editable-install path, use this PowerShell sequence. The generated `.venv\Scripts\dataops.exe` launcher also embeds the old environment location and should not be used until the environment is explicitly repaired.

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider
.\.venv\Scripts\python.exe scripts\check_internal_links.py
```

Unset `PYTHONPATH` after the session if needed:

```powershell
Remove-Item Env:PYTHONPATH
```

Repairing the editable install is a separate environment change and should be performed only when explicitly approved.

## Benchmark Conversion Validation

Use the restricted converter only for a locally approved SQL sample whose
provenance and license status are recorded. The command never executes source
SQL or connects to a database:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests\benchmark_sql_conversion_test.py
.\.venv\Scripts\python.exe -m data_ops_lab benchmark-convert-sql --source "datasets\benchmarks\raw\northwind\instnwnd.sql" --dataset northwind --output "datasets\benchmarks\derived\northwind"
```

A repeated conversion must report `Outputs changed: False`. Validate real
benchmark outputs by comparing manifest counts and SHA-256 values across the
DuckDB database and each Parquet file. Do not run `.bak` restore, external load,
import, migration, or synchronization commands as part of the offline suite.

## Validation Levels

1. Unit tests for parsers, transformations, rules, and isolated decisions.
2. Contract tests for inputs, outputs, schemas, errors, and compatibility.
3. Integration tests for module boundaries using temporary local fixtures.
4. Workflow tests for coordinated sequences.
5. Regression tests for previously broken or protected behavior.
6. End-to-end tests from local input to generated output.
7. Reliability/performance checks only after measuring a real bottleneck.

Start with the smallest relevant test. Run the full suite after source, contract, workflow, or shared behavior changes. Documentation-only work requires link/format validation and does not justify invented tests, though running the offline suite is acceptable as a repository checkpoint.

## External Integrations

Default tests must remain offline. Any future API, database, or hosted-service integration needs fixtures or mocks in the main suite. Label and isolate online tests so they never run by default or incur external cost unexpectedly.

## Test Integrity

- Do not change expectations to fit an unapproved modeling decision.
- Separate raw-data findings, approval gaps, model assumptions, and code regressions.
- Never claim a test passed unless its command completed successfully.
- Record skipped checks and their reason in `docs/agent-handoff.md`.
