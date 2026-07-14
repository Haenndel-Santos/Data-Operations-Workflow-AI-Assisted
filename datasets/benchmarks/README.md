# Public Benchmark Datasets

This area holds public or user-supplied sample databases used for offline,
non-production validation of the analytics workflow.

## Layout

- `raw/`: immutable source downloads. Ignored by Git.
- `derived/`: reproducible DuckDB, Parquet, and conversion reports. Ignored by Git.
- `manifests/`: versioned provenance, checksum, approval, and processing metadata.
- `work/`: disposable conversion workspace. Ignored by Git.

Raw files are never treated as trusted executable SQL. The benchmark converter
materializes only parsed table definitions and insert rows. It ignores database
drops, procedures, views, triggers, credentials, external data access, and other
operational statements.

Dataset presence does not imply approval for model training, publication, or
upload. Those uses require confirmed provenance, licensing, and human approval.

Versioned reference manifests bind verified provenance and licenses to exact
local conversion artifacts and permitted uses. `reference-dataset-validate`
then checks an independent reproduction, profiles DuckDB read-only, and emits a
separate pending relationship review. Technical validity never approves a
relationship.
