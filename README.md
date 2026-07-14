# AI-Assisted Data Operations Workflow

Local workflow for turning raw operational spreadsheets into validated analytical datasets for BI.

The project demonstrates how AI can assist data operations without replacing the analyst. The workflow accelerates file conversion, profiling, schema discovery, key detection, SQL generation, validation, documentation, and Tableau-ready export.

## Workflow

```text
Raw XLSX / CSV
-> controlled conversion
-> data profiling
-> cleaning and standardization
-> schema and key detection
-> relationship mapping
-> SQL suggestions
-> relationship validation
-> DuckDB analytical layer
-> Tableau export
-> data dictionary and process documentation
```

## Modules

| Module | Purpose |
|---|---|
| File Converter | Converts CSV/XLSX files into normalized CSV and Parquet staging files. |
| Data Profiler | Reports columns, types, nulls, duplicates, unique counts, and examples. |
| Schema Detector | Infers physical and semantic column types. |
| Key Identifier | Suggests primary keys and foreign keys based on uniqueness, naming, and value coverage. |
| Data Cleaner | Standardizes column names, blanks, text, dates, and numeric strings. |
| SQL Assistant | Generates starter SQL checks and join queries from detected metadata. |
| Query Validator | Checks relationship match rates and join fanout risk. |
| Export Layer | Writes clean CSV/Parquet files for Tableau and creates a DuckDB database. |
| Documentation Generator | Creates a data dictionary, SQL suggestions, and validation summaries. |

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m pip install -e .
.\.venv\Scripts\python -m data_ops_lab --input samples\raw --output outputs\demo
```

Equivalent installed command:

```powershell
.\.venv\Scripts\dataops --input samples\raw --output outputs\demo
```

To run the workflow on the full original export folder:

```powershell
.\.venv\Scripts\python -m data_ops_lab --input originaldatabase --output outputs\originaldatabase_analysis
```

To run Step 3 source onboarding and candidate modeling without exporting to Tableau:

```powershell
.\.venv\Scripts\python -m data_ops_lab source-onboard --input originaldatabase
```

To prepare the Step 3B human review package without applying approvals:

```powershell
.\.venv\Scripts\python -m data_ops_lab human-review
```

To validate the editable approval template without updating approved model files:

```powershell
.\.venv\Scripts\python -m data_ops_lab apply-approvals --input config\data_model\human_approval_template.yml
```

To import serial reference rules from `Serials.xlsx` and validate `ref_nr` patterns:

```powershell
.\.venv\Scripts\python -m data_ops_lab serial-rules --input originaldatabase\Serials.xlsx
```

To prepare serial-aware human review recommendations without applying approvals:

```powershell
.\.venv\Scripts\python -m data_ops_lab serial-aware-review
```

To generate the human approval review spreadsheet:

```powershell
.\.venv\Scripts\python -m data_ops_lab approval-spreadsheet
```

To align the canonical model and validate Product references without applying approvals:

```powershell
.\.venv\Scripts\python -m data_ops_lab canonical-model
```

To audit duplicate and empty Product references without applying approvals:

```powershell
.\.venv\Scripts\python -m data_ops_lab product-reference-audit
```

To generate the internal Product reference human review workbook:

```powershell
.\.venv\Scripts\python -m data_ops_lab product-reference-review-spreadsheet
```

To consolidate completed Product human review decisions into a final report:

```powershell
.\.venv\Scripts\python -m data_ops_lab product-reference-final-decision
```

To reconcile Product references with the authoritative `Product_ref.nr` enrichment file:

```powershell
.\.venv\Scripts\python -m data_ops_lab product-refnr-reconciliation
```

To create the focused Product ref.nr reconciliation exception shortlist:

```powershell
.\.venv\Scripts\python -m data_ops_lab product-refnr-human-review
```

To validate completed Product ref.nr human review decisions without applying them:

```powershell
.\.venv\Scripts\python -m data_ops_lab validate-product-refnr-decisions
```

To generate the Product final review spreadsheet for remaining blocking items:

```powershell
.\.venv\Scripts\python -m data_ops_lab product-refnr-final-review-spreadsheet
```

To revalidate the completed Product final review without applying decisions:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python -m data_ops_lab validate-product-refnr-final-review --workbook "outputs\<run-id>\product_refnr_human_review_shortlist_validated.xlsx"
```

To preview the Step 3E.4 Product application plan without writing approved state:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python -m data_ops_lab apply-product-refnr-decisions --workbook "outputs\<run-id>\product_refnr_human_review_shortlist_validated.xlsx"
```

To validate and generate the local Product materialization preview from applied state:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python -m data_ops_lab product-materialization-preview --workbook "outputs\<run-id>\product_refnr_human_review_shortlist_validated.xlsx" --output "outputs\<run-id>\step3e5_product_materialization"
```

To validate the complete preview and generate a dry-run canonical Product promotion plan:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python -m data_ops_lab product-canonical-promotion-plan --materialization "outputs\<run-id>\step3e5_product_materialization" --output "outputs\<run-id>\step3e6_product_canonical_promotion"
```

This command has no apply mode and does not write canonical state or connect to a database.

To compile a structured analytics request into a safe read-only SQL dry-run plan:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python -m data_ops_lab analytics-query-plan --request "outputs\<run-id>\analytics_request.yml" --database "outputs\<run-id>\duckdb\operations_lab.duckdb" --output "outputs\<run-id>\analytics_query_plan"
```

This first AI-backend foundation does not execute the SQL. It validates the local DuckDB catalog, parameterizes filter values, and requires approved relationships for cross-table joins.

To convert an approved local T-SQL sample into DuckDB and compressed Parquet
without executing operational SQL:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m data_ops_lab benchmark-convert-sql --source "datasets\benchmarks\raw\northwind\instnwnd.sql" --dataset northwind --output "datasets\benchmarks\derived\northwind"
```

Raw and derived benchmark data remain local and outside Git. The versioned
inventory records checksums, provenance gaps, and approval boundaries.

To generate the conceptual main database schema overview:

```powershell
.\.venv\Scripts\python -m data_ops_lab schema-overview
```

To verify repository documentation links:

```powershell
.\.venv\Scripts\python scripts\check_internal_links.py
```

## Generated Outputs

After running the demo, inspect:

| Path | Description |
|---|---|
| `outputs/demo/01_converted/` | Controlled CSV and Parquet conversion layer. |
| `outputs/demo/02_cleaned/` | Cleaned analytical files. |
| `outputs/demo/duckdb/operations_lab.duckdb` | Local DuckDB database for SQL analysis. |
| `outputs/demo/metadata/data_profile.json` | Data profiling output. |
| `outputs/demo/metadata/schema.json` | Inferred schema metadata. |
| `outputs/demo/metadata/keys.json` | Primary and foreign key suggestions. |
| `outputs/demo/metadata/relationship_validation.csv` | Join validation and match-rate checks. |
| `outputs/demo/metadata/sql_suggestions.md` | SQL checks and join queries. |
| `outputs/demo/metadata/data_dictionary.md` | Human-readable data dictionary. |
| `outputs/demo/tableau/` | Clean CSV/Parquet export layer for Tableau. |

## Demo Dataset

The sample data models a small operations dataset:

- `customers.csv`
- `orders.csv`
- `order_items.csv`

The workflow detects:

- `customers.customer_id` as a primary key.
- `orders.order_id` as a primary key.
- `order_items.order_item_id` as a primary key.
- `orders.customer_id -> customers.customer_id`.
- `order_items.order_id -> orders.order_id`.

## Portfolio Explanation

Use this concise explanation in interviews:

> I built an AI-assisted workflow to convert raw operational spreadsheets into structured analytical datasets. The system profiles files, detects key relationships, prepares SQL joins, validates relationship quality, creates a local DuckDB analytical layer, and exports clean data for Tableau dashboards.

## Why DuckDB

DuckDB is a good fit for this project because it supports local analytical workflows over CSV and Parquet without requiring a database server. That makes the project easy to demo, easy to reproduce, and aligned with real operations-analysis work where analysts often start from spreadsheets.

## Next Extensions

- Add an optional OpenAI-powered natural-language SQL assistant.
- Add a Streamlit UI for upload, profiling, and validation review.
- Add Tableau workbook screenshots as a final portfolio artifact.
- Add richer validation checks for totals before and after joins.
- Add pytest coverage for each module.

## Project Utilities

- [Demo runner](scripts/run_demo.ps1)
- [Internal link checker](scripts/check_internal_links.py)
- [Sample customers file](samples/raw/customers.csv)

## Project Governance

- [Agent instructions](AGENTS.md)
- [Project mission and stages](docs/project-master.md)
- [Current project state](docs/progress.md)
- [Architecture](docs/architecture.md)
- [Testing](docs/testing.md)
- [Orchestrator](docs/orchestrator.md)
- [Step 3E.4 Product application contract](docs/product-refnr-application.md)
- [Product materialization preview contract](docs/product-materialization.md)
- [Product canonical promotion plan contract](docs/product-canonical-promotion.md)
- [AI-assisted analytics backend and roadmap](docs/ai-analytics-backend.md)
- [Structured analytics query plan contract](docs/analytics-query-plan.md)
- [Analytics semantic catalog contract](docs/analytics-semantic-catalog.md)
- [Analytics semantic review and approval contract](docs/analytics-semantic-approval.md)
- [Analytics semantic adapter contract](docs/analytics-semantic-adapter.md)
- [Benchmark dataset onboarding contract](docs/benchmark-datasets.md)
- [Agent handoff history](docs/agent-handoff.md)
