# Architecture

## Runtime Layers

```text
CLI
  -> default workflow coordinator
     -> conversion -> profiling -> cleaning -> schema/key inference
     -> relationship validation -> SQL suggestions -> DuckDB/Tableau export
     -> generated documentation

  -> staged ERP modeling commands
     -> source onboarding -> serial rules -> review preparation
     -> canonical/Product reconciliation -> final review validation
     -> explicitly approved Product reconciliation state
     -> read-only Product materialization preview or blocker checkpoint
     -> hash-bound dry-run canonical Product promotion plan
     -> schema and business-flow documentation

  -> AI-assisted analytics backend
     -> natural-language adapter (target)
     -> structured analytics request
     -> local catalog and approved-relationship validation
     -> review-ready semantic catalog and ambiguity index
     -> parameterized SELECT dry-run plan
     -> exact plan revalidation
     -> controlled read-only execution and result evidence

  -> public benchmark onboarding
     -> ignored immutable raw source
     -> restricted T-SQL parsing
     -> local DuckDB and Parquet artifacts
     -> versioned checksums and pending relationship candidates
```

## Boundaries

| Area | Responsibility | Important boundary |
| --- | --- | --- |
| `src/data_ops_lab/cli.py` | Parse commands and dispatch entrypoints | Do not absorb module business logic. |
| `src/data_ops_lab/workflow.py` | Coordinate the default analytical pipeline | Preserve `run_workflow` and `WorkflowResult` compatibility. |
| Conversion/profile/clean/schema modules | Transform and describe local data | Never modify raw input files. |
| Validation/SQL/export/documentation modules | Validate and publish analytical artifacts | Generated output is not approval evidence by itself. |
| ERP modeling/review modules | Produce candidates, review workbooks, and validation reports | Do not write approved model files unless an apply contract is explicitly authorized. |
| Product materialization module | Validate applied Product decisions and generate local preview/lineage artifacts | Fail closed without partial preview when approved source evidence is missing. |
| Product canonical promotion module | Validate the complete Product snapshot and produce a hash-bound dry-run plan | Report readiness only; never apply canonical state or copy private row values. |
| Analytics query-plan module | Compile a bounded structured request against a local DuckDB catalog | Never accept raw SQL, execute queries, expose filter values, or use unapproved joins. |
| Analytics query-execution module | Revalidate and execute an exact reviewed plan with bounded local resources | Read-only DuckDB only; disable external access; fail closed without partial results. |
| Analytics semantic-catalog module | Validate business terms, fields, measures, paths, and ambiguity against physical metadata | Metadata only; approved relationships only; never self-approve semantics or resolve ambiguity silently. |
| Benchmark SQL conversion module | Parse local sample T-SQL table definitions and rows into DuckDB and Parquet | Never execute source SQL or external operations; output remains unapproved benchmark evidence. |
| `datasets/benchmarks/` | Separate ignored raw/derived data from versioned inventories and contracts | Dataset presence or conversion is not approval for training, upload, or relationship promotion. |
| `config/data_model/` | Version candidate state, domain mappings, and approvals | Keep candidate and approved files separate. |
| `originaldatabase/` | Private source exports | Read only; excluded from Git. |
| `outputs/` | Reproducible generated artifacts | Excluded from Git; do not hand-edit. |
| `.codex/` | Domain guidance, skills, and agent profiles | Guidance only; cannot override code, tests, or human approvals. |

## Data Contracts

The default workflow accepts an input directory and output directory and returns `WorkflowResult` with output, database, table, metadata, and Tableau locations. Staged commands use explicit paths and return summaries or artifact locations from their module entrypoints.

Formal module manifests are not yet implemented. Before adding dynamic orchestration, define contracts for inputs, outputs, dependencies, validation, and failure policy without breaking current Python entrypoints or CLI commands.

## State Model

Modeling decisions use distinct states such as candidate, pending review, approved, rejected, blocked, and conflicting. Key and relationship approvals live in `approved_keys.yml` and `approved_relationships.yml`; both are currently empty. Product-specific reconciliation state lives separately in `product_reconciliation_state.yml`. Human review and promotion-plan reports can establish readiness but must not silently apply state.

## Current Gaps

- No common module discovery or manifest registry.
- No shared dependency graph, checkpoint, resume, or dry-run engine.
- CLI stage dispatch and the default workflow are not yet unified under one orchestration contract.
- Some generated summaries become stale when later review steps run; consolidated state must cite the newest validation evidence.
- Semantic catalog validation and explicit human review/application contracts exist. No real semantic registry is approved yet; the natural-language adapter, result narration, and benchmark question/answer harness are not implemented.
