# AI-Assisted Data Operations Workflow

**A local-first, customer-hosted Data Intelligence platform for operational
data.** It turns raw spreadsheets and local database evidence into validated
analytical datasets, governed semantic context, and evidence-backed analytical
answers. AI may interpret and explain; deterministic software retains authority
over transformations, calculations, SQL planning and execution, approvals, and
lineage.

The repository began as a workflow that converts XLSX/CSV exports into
DuckDB/BI-ready datasets. That pipeline is still here, implemented and used, but
it is now the foundation of a broader system: governed data preparation,
approved semantic context, deterministic analytics with human review, and a
planned Product API and UI for business users. Read this README as a map of what
exists, what is opt-in, and what is still a design.

## Who It Is For

| User | What they get |
| --- | --- |
| Business owners, managers, and operations teams at small and medium-sized businesses | Ask an operational question in plain language and receive a reproducible answer with evidence and caveats, without SQL. This is the intended product user; the user-facing surface (API/UI) is not built yet. |
| Data and operations analysts | Faster profiling, schema and key discovery, relationship evidence, review workbooks, a local DuckDB layer, and BI exports. They remain advanced users and reviewers. |
| Reviewers and administrators | Explicit, hash-bound approval points; local-only data by default; audit evidence for every promoted decision. |

Tableau export is one downstream output the pipeline produces. It is not the
product.

## Core Principles

- **Local-first, customer-controlled data.** Raw inputs, cleaned data, DuckDB,
  prompts, results, and generated artifacts stay inside the customer-controlled
  environment by default. See [Customer Data Boundary](docs/customer-data-boundary.md).
- **Deterministic authority.** A candidate, heuristic, AI suggestion, or model
  output is never itself permission to change data or run an operation. Code
  and approved contracts calculate, plan, execute, and record.
- **Human or exact policy grants authority.** Missing or pending review never
  becomes approval. Every promoted relationship, semantic term, and execution
  plan is bound to a hash of exactly what was reviewed; the governed cleaning
  contract applies the same rule to transformations.
- **Evidence and lineage.** Answers expose their plan, controls, and facts;
  transformations record what changed and under which authority.
- **Provider-neutral AI boundary.** The model interprets intent and narrates
  facts. Its output is schema-bounded and validated; raw model SQL is rejected.
- **Reproducible and offline by default.** The main test suite and every
  default command run without network, credentials, or a live model.

## Architecture Overview

```text
Operational data (XLSX / CSV / local database evidence)
        |
        v
ingestion + profiling                       implemented
        |
        v
governed preparation                        legacy cleaner (default path);
  (candidate -> evidence -> review           governed contract + engine
   -> authority -> apply -> lineage)         implemented, opt-in
        |
        v
schema, key, and relationship evidence      implemented; approvals human-only
        |
        v
semantic governance                         implemented (catalog, review, approval)
        |
        v
structured analytical intent                implemented (AI proposes; code validates)
        |
        v
deterministic planning + read-only execution   implemented (Stage 5A / 5B)
        |
        v
facts, evidence, cited narration            implemented (recorded narration)
        |
        v
Product API / UI                            designed, not implemented
```

The same authority pattern repeats at every layer:

```text
AI or heuristic proposes / interprets
        -> deterministic code measures
        -> human review or exact policy authorizes
        -> deterministic code executes
        -> evidence + lineage prove what happened
```

## Core Data Pipeline

The original workflow, still the default command and still the entry point for
every dataset:

```text
Raw XLSX / CSV
-> controlled conversion (normalized CSV + Parquet)
-> data profiling
-> cleaning (legacy path; see Governed Cleaning below)
-> schema and key detection
-> relationship evidence and validation
-> SQL suggestions
-> local DuckDB analytical layer
-> BI-ready CSV/Parquet export
-> data dictionary and process documentation
```

| Module | Purpose |
|---|---|
| File Converter | Converts CSV/XLSX files into normalized CSV and Parquet staging files. |
| Data Profiler | Reports columns, types, nulls, duplicates, unique counts, and examples. |
| Schema Detector | Infers physical and semantic column types; key inference pushes metadata, null, uniqueness, and overlap work into local DuckDB. |
| Key Identifier | Suggests primary keys and foreign keys as candidates. Candidates are never promoted without evidence and human approval. |
| Data Cleaner (legacy) | Standardizes column names, blanks, text, dates, and numeric strings by heuristic. Behavior is characterized by tests and frozen while the governed path is built beside it. |
| SQL Assistant | Generates starter SQL checks and join queries from detected metadata for a human to read. It is not an execution path. |
| Query Validator | Checks relationship match rates and join fan-out risk. |
| Export Layer | Writes clean CSV/Parquet files and creates a DuckDB database. |
| Documentation Generator | Creates a data dictionary, SQL suggestions, and validation summaries. |

Beyond the default pipeline, staged ERP modeling commands prepare source
onboarding, serial reference rules, canonical mappings, Product reference
reconciliation, human review workbooks, and hash-bound dry-run promotion plans.
Approved model state (`config/data_model/approved_*.yml`) is written only by an
explicit apply contract after a completed human review; candidates and approvals
are kept mechanically separate.

## Governed Analytics

The analytics backend lets a question become a reproducible answer without
trusting the model with the database:

```text
Natural-language question
  -> AI / provider interprets intent
  -> structured semantic intent (schema-bounded to approved entity IDs)
  -> deterministic semantic resolution against the approved catalog
  -> deterministic query planning (Stage 5A: parameterized SELECT, no execution)
  -> exact human plan review (hash-bound)
  -> read-only, resource-bounded execution (Stage 5B)
  -> deterministic facts and result presentation
  -> optional AI-assisted narration that must cite those facts
```

What holds at each boundary:

- Provider output is a JSON object whose entity IDs are constrained by schema
  to the approved semantic catalog. Provider-generated SQL, physical tables,
  and physical joins are rejected before planning.
- Cross-table plans require human-approved relationships; candidate
  relationships never grant a join.
- Stage 5A compiles but does not execute. Stage 5B rebuilds the plan, compares
  it by SHA-256 with the reviewed plan, opens DuckDB read-only with external
  access and extension autoload disabled, and enforces row, byte, runtime,
  memory, thread, and temp limits.
- Narration is validated against the deterministic facts and is never numeric
  authority.

This is not a generic NL-to-SQL tool and not a SQL generator. Structured
requests, approved semantic context, and deterministic compilation sit between
the model and the database.

## Governed Cleaning

Two paths coexist deliberately.

**Legacy path (`cleaner.py`)** - the cleaner the default pipeline still calls.
It changes data by heuristic: blank sentinels become nulls, numeric-looking text
is coerced when at least 90% parses, and date-named columns are parsed with a
day-first guess. Its behavior is pinned by characterization tests and left
unchanged on purpose while the governed path is built beside it. Two of those
pinned behaviors are the motivation for governance: a single unparseable value
becomes `NA` silently, and a date column whose sample is under 80% ISO can have
valid ISO dates reinterpreted with day and month swapped.

**Governed path (`governed_cleaning.py`, contract complete)** - transformations
belong to one of three classes, each with exactly one authority mechanism:

```text
safe_automatic    structural, name-level only          -> versioned operation table
configured_only   bounded value changes (trim, blanks)  -> exact dataset cleaning policy
governed          semantic coercion (numbers, dates)    -> exact human decision on an approved candidate
```

Confidence is computed from evidence, never accepted from a proposer. States
move only `candidate -> pending_review -> approved | rejected -> applied`;
`approved` is derived from a hash-bound decision, not stored as free-standing
state. Every authority record is self-bound, including which mechanism granted
it, and lineage names that mechanism. See
[Governed Cleaning Contract](docs/governed-cleaning.md).

**Governed engine (`governed_cleaning_engine.py`, implemented, opt-in)** -
`propose -> review -> authorize -> ordered application plan -> verify -> apply
-> atomic publish -> lineage`, reachable only through the three
`governed-cleaning-*` commands. The source hash is derived from the real
Parquet files; the human review binds to the exact proposal artifact; the
application plan is the complete authorized authority set in canonical order,
hash-bound; every authority is re-verified against the current source before
staging is created; a failure anywhere before publish promotes nothing; each
lineage row is the contract's `TransformationLineage` with the real logical
output hash. `run_workflow()` continues to use the legacy cleaner for
compatibility; the governed engine is available only through its explicit
opt-in `governed-cleaning-*` commands, so both paths exist on `main` and the
default workflow does not change. See
[Governed Cleaning Engine](docs/governed-cleaning-engine.md).

## Security and the Customer Data Boundary

Implemented today, at the repository and application level:

- Local model calls are pinned to a loopback HTTP origin with proxies
  disabled, no credentials, and per-invocation opt-in; hosted providers are not
  called. An architecture test fails the suite if a network-capable import
  appears outside a two-module allowlist. This is a tripwire, not a sandbox.
- Analytical execution is read-only with external access disabled and fixed
  resource limits.
- Private inputs (`originaldatabase/`), generated artifacts (`outputs/`), and
  benchmark raw/derived data are excluded from Git and from agent worktrees.
- Agent execution is constrained by permission rules (deny-by-default for
  destructive git operations, edits to approved state, private inputs, and
  secrets), role-restricted read-only reviewer agents, and a worktree
  convention. Guidance files orient; code, tests, and CI enforce.
- CI runs Ruff correctness and security rules, secret scanning, dependency
  vulnerability auditing, the offline test suite, internal-link validation,
  and pull-request diff checks.

Designed, documented, and **not implemented**: runtime authentication, RBAC,
tenant isolation, row-level security, deployment-level egress denial, secret
manager integration, central audit logging, WAF/TLS/HSTS, backup and restore,
and the error-reporting workflow. See
[Security Architecture Baseline](docs/security-architecture.md),
[Product Threat Model](docs/threat-model.md), and
[RBAC Matrix](docs/rbac-matrix.md). A documented target is not an implemented
control.

## Testing and CI

The repository has a broad contract- and regression-oriented offline suite:
477 tests pass and 2 opt-in live-provider tests are skipped by default. Tests
protect workflow behavior, preservation of source and approved files, every
analytics stage's blockers and authority gates, the governed cleaning contract's
invariants, the governed engine's on-disk behavior (tamper, drift, omission,
partial failure, determinism), the legacy cleaner's characterized behavior and
its fixed logical golden baseline, the error-taxonomy registry, and the network
boundary. CI runs on every pull request and push to
`main`: Ruff, pip-audit, Gitleaks, pytest, internal links, and `git diff
--check`.

Remaining major testing work belongs to surfaces that do not exist yet: the
Product API and UI, runtime authentication and RBAC, tenant isolation,
deployment controls, and end-to-end product workflows. See
[Testing](docs/testing.md).

## Benchmarking

Northwind is the development benchmark: exact provenance and MIT license,
independently reproduced conversion, 13 human-accepted relationships, an
approved 111-entity semantic catalog, and a 13-case expected-answer pack with a
separate immutable approval.

- Recorded offline evaluation: **13/13** - deterministic regression evidence.
- Separately authorized local `gpt-oss:20b` development comparison: **9/13**
  end to end; the four mismatches were blocked before any query executed. This
  is development evidence, not holdout evidence and not provider selection.

AdventureWorks 2025 is the selected fresh holdout. Its read-only local export
contract is implemented; the export itself, relationship review, semantic
approval, answer packs, and any live evaluation remain pending. No provider has
been selected. See [Benchmark datasets](docs/benchmark-datasets.md) and the
[Phase 5 provider-selection scope](docs/ai-phase-5-provider-selection-scope.md).

## Local Model Provider

Ollama (`gpt-oss:20b`) is the local provider used for controlled development
evaluation. It is not a product dependency: the provider boundary is neutral,
the recorded provider is the offline default for every regression test, live
calls require an explicit `--allow-network` on a loopback origin, and no core
deterministic functionality needs a model installed. Installing Ollama is
required only to run the opt-in live tests and the live evaluation commands.

## Current Project Status

| State | Items |
| --- | --- |
| Implemented | Core pipeline (conversion, profiling, legacy cleaning, schema/key detection, relationship validation, DuckDB, BI/Parquet/CSV export, documentation); staged ERP modeling and human review workflows with hash-bound dry-run promotion; analytics Stage 5A planning, Stage 5B read-only execution, semantic catalog/review/approval, provider-neutral translation with recorded and loopback Ollama providers, deterministic presentation, cited recorded narration, two-phase session coordinator, static module registry; Northwind development benchmark; CI security and correctness gates; repository-level Customer Data Boundary enforcement; agent permission and worktree controls; Governed Cleaning D1 contract; pandas reproducibility baseline (`>=3.0.3,<3.1`); Governed Cleaning D2 engine (`governed-cleaning-propose` / `-authorize` / `-apply`, ordered hash-bound plan, atomic publish, contract lineage) as an opt-in route. |
| Designed, not implemented | Generic dataset readiness over the governed route; Product API; UI; runtime authentication and RBAC; tenant isolation; deployment security; customer onboarding; end-to-end product workflows; richer connectors and BI artifacts. AdventureWorks holdout evaluation and provider selection remain gated. |

## Known Limitations

- **Backend CLI complexity.** The CLI exposes 51 commands. They are backend
  and internal primitives - each stage's contract is a command so it can be
  run, reviewed, and tested in isolation. They are not the intended end-user
  experience. The Product API and UI, when built, should present something
  closer to: connect or upload data -> review detected issues -> approve
  governed corrections -> ask a business question -> receive answer plus
  evidence.
- **Performance is measured, not proven at scale.** Pandas-heavy stages remain
  in the default pipeline. A synthetic isolated-process baseline exists;
  schema/key inference moved metadata, null, uniqueness, and overlap work into
  DuckDB (measured 27% peak-memory and 99% runtime reduction on the fixed
  3-table workload); analytical execution has fixed resource limits. Large
  production datasets have not been exercised.
- **Legacy cleaner behavior depends on the pandas major**, which is why pandas
  is pinned to `>=3.0.3,<3.1`; the legacy path is frozen and pinned by a static
  golden baseline while the governed engine is the route for new work.
- **Governed engine v1 scope.** Five operations (`normalize_column_name`,
  `trim_whitespace`, `normalize_blank_sentinel`, `parse_number`, `parse_date`
  with explicit format), one value-changing operation per column, logical
  determinism promised and physical Parquet bytes recorded but not promised
  across writer versions.

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

Run the offline suite and the same gates CI runs:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pip_audit --skip-editable
.\.venv\Scripts\python.exe scripts\check_internal_links.py
```

## Backend CLI Reference

The commands below expose each backend stage as a separately runnable,
reviewable contract. Most stop at a human review or dry-run boundary by design.
Paths written as `outputs\<run-id>\...` are placeholders.

To run the opt-in governed cleaning route over a directory of Parquet files
(propose changes no value; authorize turns the completed review and an optional
dataset cleaning policy into an ordered, hash-bound plan; apply re-verifies
everything against the current source and publishes output with lineage
atomically):

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m data_ops_lab governed-cleaning-propose --parquet-dir "outputs\<run-id>\01_converted\parquet" --output "outputs\<run-id>\governed_cleaning\proposal"
# complete outputs\<run-id>\governed_cleaning\proposal\review_template.yml, then:
.\.venv\Scripts\python.exe -m data_ops_lab governed-cleaning-authorize --proposal "outputs\<run-id>\governed_cleaning\proposal" --parquet-dir "outputs\<run-id>\01_converted\parquet" --review "outputs\<run-id>\governed_cleaning\review.yml" --policy "config\cleaning_policy.yml" --output "outputs\<run-id>\governed_cleaning\authority"
.\.venv\Scripts\python.exe -m data_ops_lab governed-cleaning-apply --authority "outputs\<run-id>\governed_cleaning\authority" --parquet-dir "outputs\<run-id>\01_converted\parquet" --output "outputs\<run-id>\governed_cleaning\output"
```

Every governed candidate needs an explicit disposition before an apply-ready
plan exists; a missing decision leaves the authorization incomplete rather than
blocked. Nothing in this route is invoked by the default workflow.

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

To run the synthetic offline Stage 5D translation regression pack:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-translation-evaluate --pack "tests\fixtures\analytics_translation\translation_evaluation_pack.yml" --semantic-state "tests\fixtures\analytics_translation\approved_semantic_catalog.yml" --output "outputs\<run-id>\analytics_translation_evaluation"
```

This validates deterministic translation safety and acceptance behavior only; it does not call or benchmark a live model.

To run one explicitly authorized English question through the selected local
Ollama `gpt-oss:20b` provider and the same deterministic Stage 5D boundary:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-nl-translate-ollama --question-file "outputs\<run-id>\question.txt" --semantic-state "config\analytics\approved_semantic_catalog.yml" --endpoint "http://127.0.0.1:11434" --model "gpt-oss:20b" --context-tokens 8192 --max-output-tokens 1024 --timeout-seconds 120 --allow-network --output "outputs\<run-id>\analytics_nl_translation_ollama"
```

The adapter accepts only a literal loopback origin, disables proxy routing,
requires no credential, excludes database rows/SQL/physical mappings, and still
stops before query execution. `--allow-network` authorizes only this local HTTP
socket invocation; it does not permit an external provider.

To run the synthetic Stage 5E expected-answer pack through Stages 5D, 5A, and 5B:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-answer-evaluate --pack "tests\fixtures\analytics_answer_evaluation\answer_evaluation_pack.yml" --semantic-state "tests\fixtures\analytics_answer_evaluation\approved_semantic_catalog.yml" --output "outputs\<run-id>\analytics_answer_evaluation"
```

This executes only a temporary synthetic DuckDB database after exact request and plan gates. It does not use a live model or real dataset.

To prepare a bounded real-dataset answer design through recorded Stage 5D and
exact Stage 5A plans while stopping before table-row access:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-dataset-benchmark-answer-prepare --design "datasets\benchmarks\manifests\northwind.answer-benchmark-design.yml" --dataset-manifest "datasets\benchmarks\manifests\northwind.dataset-benchmark.yml" --database "datasets\benchmarks\derived\northwind\northwind.duckdb" --semantic-state "config\analytics\approved_semantic_catalog.yml" --relationships "outputs\benchmarks\northwind-phase2-reviewed\approved_relationships.yml" --output "outputs\benchmarks\northwind-phase5-answer-preparation-v1"
```

This creates one hash-bound pending review for all exact plans. It does not run
Stage 5B, read table rows, use Ollama/network, collect expected answers, or
approve the final benchmark pack.

After every exact plan has a completed hash-bound review approving only local
read-only collection, materialize a candidate pack sequentially with fixed
limits:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-dataset-benchmark-answer-materialize --design "datasets\benchmarks\manifests\northwind.answer-benchmark-design.yml" --dataset-manifest "datasets\benchmarks\manifests\northwind.dataset-benchmark.yml" --preparation-manifest "outputs\benchmarks\northwind-phase5-answer-preparation-v1\analytics_dataset_benchmark_preparation.yml" --execution-review "datasets\benchmarks\manifests\northwind.answer-execution-review.yml" --database "datasets\benchmarks\derived\northwind\northwind.duckdb" --semantic-state "config\analytics\approved_semantic_catalog.yml" --relationships "outputs\benchmarks\northwind-phase2-reviewed\approved_relationships.yml" --pack-output "datasets\benchmarks\manifests\northwind.answer-benchmark-pack.yml" --output "outputs\benchmarks\northwind-phase5-answer-materialization-v3"
```

Northwind now has a reviewed 13-case candidate pack plus a separate immutable
approval. Its recorded offline evaluation passed 13/13 with zero blockers;
the separately authorized local Ollama development comparison subsequently
passed 9/13 end to end and safely blocked four mismatches before query execution.
See the
[expected-answer review record](docs/northwind-expected-answer-review.md).

To validate immutable dataset-backed benchmark bindings without opening or querying the database:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-dataset-benchmark-validate --dataset-manifest "<manifest.yml>" --database "<dataset.duckdb>" --semantic-state "<semantic.yml>" --relationships "<relationships.yml>" --pack "<pack.yml>" --approval "<approval.yml>" --output "outputs\<run-id>\analytics_dataset_benchmark_validation"
```

This is a hash-bound dry-run only. Northwind now meets this contract through its
versioned completed review and generated approval; EDS does not.

To prepare and validate the separate human review required by that contract:

```powershell
.\.venv\Scripts\python.exe -m data_ops_lab analytics-dataset-benchmark-review --dataset-manifest "<manifest.yml>" --database "<dataset.duckdb>" --semantic-state "<semantic.yml>" --relationships "<relationships.yml>" --pack "<pack.yml>" --output "<review.yml>"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-dataset-benchmark-approval --dataset-manifest "<manifest.yml>" --database "<dataset.duckdb>" --semantic-state "<semantic.yml>" --relationships "<relationships.yml>" --pack "<pack.yml>" --review "<completed-review.yml>" --approval-output "<approval.yml>" --output "outputs\<run-id>\analytics_dataset_benchmark_approval"
```

Approval validation is dry-run by default. Writing the approval requires `--apply`; it still does not execute benchmark queries or authorize provider, upload, or training use.

After an exact package and review have produced a valid approval, the offline evaluator is:

```powershell
.\.venv\Scripts\python.exe -m data_ops_lab analytics-dataset-benchmark-evaluate --dataset-manifest "<manifest.yml>" --database "<dataset.duckdb>" --semantic-state "<semantic.yml>" --relationships "<relationships.yml>" --pack "<pack.yml>" --approval "<approval.yml>" --output "outputs\<run-id>\analytics_dataset_benchmark_evaluation"
```

This command runs fixed-limit read-only queries with recorded responses only.
Northwind is the first real project package to meet its prerequisites and passed
13/13; this is not live-model quality evidence.

The separate local live evaluator is dry-run by default and requires a
hash-bound live authorization in addition to the offline answer approval:

```powershell
.\.venv\Scripts\python.exe -m data_ops_lab analytics-dataset-benchmark-evaluate-ollama --dataset-manifest "<manifest.yml>" --database "<dataset.duckdb>" --semantic-state "<semantic.yml>" --relationships "<relationships.yml>" --pack "<pack.yml>" --approval "<approval.yml>" --live-authorization "<live-authorization.yml>" --endpoint "http://127.0.0.1:11434" --model "gpt-oss:20b" --context-tokens 8192 --max-output-tokens 1024 --timeout-seconds 120 --output "outputs\<new-run-id>"
```

Only a reviewed invocation may add `--execute --allow-network`. The first
Northwind development run passed 9/13, so provider selection remains open and
requires a fresh holdout pack rather than further tuning against these cases.

For an unattended, resource-guarded local stability run over that development
pack, use the separate `analytics-ollama-soak` contract. It repeats sequential
Ollama calls only, records GPU/RAM/latency/quality evidence, supports a `STOP`
file, and uses no Codex or hosted-model API after launch. See
[Local Ollama Overnight Soak](docs/analytics-ollama-soak.md).

To render a completed Stage 5B result deterministically and validate a recorded
cited narrative:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-result-present --request "<request.yml>" --execution-manifest "<analytics_query_execution.yml>" --result "<analytics_query_result.csv>" --output "outputs\<run-id>\analytics_result_presentation"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-result-narrate-recorded --presentation-manifest "outputs\<run-id>\analytics_result_presentation\analytics_result_presentation.yml" --facts "outputs\<run-id>\analytics_result_presentation\analytics_result_facts.yml" --provider-response "<recorded_narration.yml>" --output "outputs\<run-id>\analytics_result_narration"
```

The renderer never reconnects to the database. The narrator is recorded and
offline, requires exact fact citations, cannot execute SQL, and never replaces
the Stage 5B result as numeric authority.

To coordinate those stages while preserving a separate human plan review:

```powershell
.\.venv\Scripts\python.exe -m data_ops_lab analytics-session-prepare-recorded --question-file "<question.txt>" --semantic-state "<approved-semantic.yml>" --translation-response "<recorded-translation.yml>" --database "<database.duckdb>" --relationships "<approved-relationships.yml>" --output "outputs\<run-id>\session_prepare"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-session-resume-recorded --prepare-manifest "outputs\<run-id>\session_prepare\analytics_session_prepare.yml" --review "<completed-review.yml>" --database "<database.duckdb>" --relationships "<approved-relationships.yml>" --narration-response "<recorded-narration.yml>" --output "outputs\<run-id>\session_resume"
```

Preparation cannot execute queries. Resume requires a separate completed review
bound to the exact preparation and plan hashes.

To validate the versioned analytics module registry without executing any
entrypoint:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-module-registry-validate --output "outputs\<run-id>\analytics_module_registry_validation"
```

This inspects entrypoint source and signatures statically, validates
dependencies, workflow order, failure policies, tests, and the human execution
gate, while dynamic execution, concurrency, network, and auto-approval remain
disabled.

To measure the current Pandas-heavy stages with generated synthetic Parquet
only:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab pipeline-performance-baseline --rows-per-table 50000 --table-count 3 --output "outputs\<run-id>\pipeline_performance_baseline"
```

The harness accepts no real input path, runs each stage in an isolated process,
and records runtime, peak process/Python memory, input footprint, outputs, and
temporary storage. See the measured Phase 1 result before using it to select a
refactor.

To convert an approved local T-SQL sample into DuckDB and compressed Parquet
without executing operational SQL:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m data_ops_lab benchmark-convert-sql --source "datasets\benchmarks\raw\northwind\instnwnd.sql" --dataset northwind --output "datasets\benchmarks\derived\northwind"
```

Raw and derived benchmark data remain local and outside Git. The versioned
inventory records checksums, provenance, and approval boundaries. To validate
Northwind's exact source/license, independent conversion, schema, declared
keys, relationship evidence, and separate review state:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m data_ops_lab reference-dataset-validate --manifest "datasets\benchmarks\manifests\northwind.reference.yml" --output "outputs\benchmarks\northwind-phase2-validation"
```

This command profiles only the bound local DuckDB in read-only mode. It emits a
pending relationship review and does not approve relationships automatically.
After the separate versioned review is completed, the exact approved projection
is reproduced with:

```powershell
.\.venv\Scripts\python.exe -m data_ops_lab reference-dataset-validate --manifest "datasets\benchmarks\manifests\northwind.reference.yml" --review "datasets\benchmarks\manifests\northwind.relationship-review.yml" --output "outputs\benchmarks\northwind-phase2-reviewed"
```

To compile the Northwind semantic catalog and reproduce its original pending
review template:

```powershell
.\.venv\Scripts\python.exe -m data_ops_lab analytics-semantic-catalog --catalog "datasets\benchmarks\manifests\northwind.semantic-catalog-candidate.yml" --database "datasets\benchmarks\derived\northwind\northwind.duckdb" --relationships "outputs\benchmarks\northwind-phase2-reviewed\approved_relationships.yml" --output "outputs\benchmarks\northwind-phase3-semantic-catalog-v2"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-semantic-review --catalog "outputs\benchmarks\northwind-phase3-semantic-catalog-v2\analytics_semantic_catalog.yml" --output "outputs\benchmarks\northwind-phase3-semantic-review\analytics_semantic_review.yml"
```

The project owner approved all 111 entities in the separate versioned review.
The approval can be revalidated without changing state, or applied idempotently,
with:

```powershell
.\.venv\Scripts\python.exe -m data_ops_lab analytics-semantic-approval --catalog "outputs\benchmarks\northwind-phase3-semantic-catalog-v2\analytics_semantic_catalog.yml" --review "datasets\benchmarks\manifests\northwind.semantic-review.yml" --output "outputs\benchmarks\northwind-phase3-semantic-approval-dry-run" --config "config\analytics"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-semantic-approval --catalog "outputs\benchmarks\northwind-phase3-semantic-catalog-v2\analytics_semantic_catalog.yml" --review "datasets\benchmarks\manifests\northwind.semantic-review.yml" --output "outputs\benchmarks\northwind-phase3-semantic-approval-apply" --config "config\analytics" --apply
```

See the [Northwind semantic review record](docs/northwind-semantic-review.md)
for hashes, modeling caveats, and the remaining provider/benchmark boundaries.

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
| `outputs/demo/02_cleaned/` | Cleaned analytical files (legacy cleaner). |
| `outputs/demo/duckdb/operations_lab.duckdb` | Local DuckDB database for SQL analysis. |
| `outputs/demo/metadata/data_profile.json` | Data profiling output. |
| `outputs/demo/metadata/schema.json` | Inferred schema metadata. |
| `outputs/demo/metadata/keys.json` | Primary and foreign key candidates. |
| `outputs/demo/metadata/relationship_validation.csv` | Join validation and match-rate checks. |
| `outputs/demo/metadata/sql_suggestions.md` | SQL checks and join queries for a human to read. |
| `outputs/demo/metadata/data_dictionary.md` | Human-readable data dictionary. |
| `outputs/demo/tableau/` | Clean CSV/Parquet export layer usable by Tableau or any BI tool. |

Generated outputs are evidence, not authority: nothing under `outputs/`
approves a relationship, a semantic term, or a transformation.

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

> I built a governed, local-first Data Intelligence system for operational
> data. It converts raw spreadsheets into validated Parquet/DuckDB datasets,
> discovers schema, keys, and relationships as evidence for human approval,
> maintains an approved semantic catalog, and turns natural-language questions
> into deterministic, read-only, hash-reviewed query plans. AI proposes intent
> and narrates cited facts; deterministic code owns calculations, execution,
> approvals, and lineage. The same authority pattern governs data cleaning:
> candidates carry computed evidence, humans or exact policies grant authority,
> and every applied change records lineage. The backend is contract-driven,
> offline-testable, and protected by CI security gates and a customer data
> boundary.

Signals a reviewer can verify in the code: data engineering over Parquet and
DuckDB, schema and relationship inference, semantic modeling, contract-driven
module design, hash-bound approvals, deterministic execution with resource
limits, AI safety boundaries (schema-bounded intent, rejected model SQL,
loopback-only provider), benchmark design with holdout discipline, error
taxonomy, CI/security engineering, and local-first product architecture.

## Why DuckDB

DuckDB is a good fit for this project because it supports local analytical workflows over CSV and Parquet without requiring a database server. That makes the project easy to demo, easy to reproduce, and aligned with real operations-analysis work where analysts often start from spreadsheets. It also supports the read-only, resource-bounded execution mode the analytics backend requires.

## Roadmap

High-level and status-accurate; see
[AI platform implementation roadmap](docs/ai-implementation-roadmap.md) for
phases and exit gates.

1. **Generic dataset readiness** over the governed route - designed; next.
2. **Product API** - versioned boundary for datasets, sessions, questions,
   reviews, executions, results, exports; identity and RBAC enforced before
   shared use - designed.
3. **UI** - Simple View and Analytical View backed by the same facts - designed.
4. **Fresh holdout evaluation and provider selection** on AdventureWorks -
   gated on local prerequisites and reviews.
5. **Production readiness** - runtime security, deployment packaging, backup,
   support - designed.

## Project Utilities

- [Demo runner](scripts/run_demo.ps1)
- [Internal link checker](scripts/check_internal_links.py)
- [Sample customers file](samples/raw/customers.csv)

## Documentation Index

Product and security baseline:

- [Product vision](docs/product-vision.md)
- [Customer Data Boundary](docs/customer-data-boundary.md)
- [Security architecture baseline](docs/security-architecture.md)
- [Product threat model](docs/threat-model.md)
- [AI analytical capability matrix](docs/ai-analytical-capability-matrix.md)
- [MVP product requirements](docs/mvp-prd.md)
- [MVP architecture](docs/mvp-architecture.md)
- [RBAC matrix](docs/rbac-matrix.md)
- [Product readiness checklist](docs/product-readiness-checklist.md)
- [Private artifact governance](docs/private-artifact-governance.md)

Governance and project memory:

- [Agent instructions](AGENTS.md) and [Claude notes](CLAUDE.md)
- [Project mission and stages](docs/project-master.md)
- [Current project state](docs/progress.md)
- [Durable decisions](docs/decisions.md)
- [Architecture](docs/architecture.md)
- [Testing](docs/testing.md)
- [Orchestrator](docs/orchestrator.md)
- [Agent handoff history](docs/agent-handoff.md)

Governed cleaning:

- [Governed cleaning contract](docs/governed-cleaning.md)
- [Governed cleaning engine](docs/governed-cleaning-engine.md)

Analytics backend contracts:

- [AI-assisted analytics backend and roadmap](docs/ai-analytics-backend.md)
- [AI platform implementation roadmap](docs/ai-implementation-roadmap.md)
- [Analytics module registry contract](docs/analytics-module-registry.md)
- [Structured analytics query plan contract](docs/analytics-query-plan.md)
- [Analytics query execution contract](docs/analytics-query-execution.md)
- [Analytics semantic catalog contract](docs/analytics-semantic-catalog.md)
- [Analytics semantic review and approval contract](docs/analytics-semantic-approval.md)
- [Analytics semantic adapter contract](docs/analytics-semantic-adapter.md)
- [Analytics natural-language translation contract](docs/analytics-nl-translation.md)
- [Analytics translation evaluation contract](docs/analytics-translation-evaluation.md)
- [Analytics expected-answer evaluation contract](docs/analytics-answer-evaluation.md)
- [Deterministic analytics result presentation contract](docs/analytics-result-presentation.md)
- [Grounded analytics result narration contract](docs/analytics-result-narration.md)
- [Local analytics session contract](docs/analytics-session.md)

Benchmarks and reference datasets:

- [Benchmark dataset onboarding contract](docs/benchmark-datasets.md)
- [Reference dataset validation and relationship-review contract](docs/reference-dataset-validation.md)
- [Northwind semantic catalog review](docs/northwind-semantic-review.md)
- [Northwind expected-answer plan review](docs/northwind-answer-benchmark-review.md)
- [Northwind expected-answer review](docs/northwind-expected-answer-review.md)
- [Dataset benchmark answer preparation contract](docs/analytics-dataset-benchmark-preparation.md)
- [Dataset benchmark answer materialization contract](docs/analytics-dataset-benchmark-materialization.md)
- [Dataset-backed benchmark validation contract](docs/analytics-dataset-benchmark.md)
- [Dataset benchmark review and approval contract](docs/analytics-dataset-benchmark-review.md)
- [Dataset-backed offline benchmark evaluation contract](docs/analytics-dataset-benchmark-evaluation.md)
- [Dataset-backed live Ollama benchmark evaluation contract](docs/analytics-dataset-benchmark-live-evaluation.md)
- [Local Ollama overnight soak contract](docs/analytics-ollama-soak.md)
- [Phase 5 provider-selection scope](docs/ai-phase-5-provider-selection-scope.md)
- [AdventureWorks SQL Server export contract](docs/adventureworks-sqlserver-export.md)

ERP modeling and Product reference contracts:

- [Synthetic pipeline performance baseline](docs/performance-baseline.md)
- [Step 3E.4 Product application contract](docs/product-refnr-application.md)
- [Product materialization preview contract](docs/product-materialization.md)
- [Product canonical promotion plan contract](docs/product-canonical-promotion.md)
- [Backend Phase II internal contracts](docs/backend-phase-2.md)
