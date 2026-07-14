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
     -> static declarative module-registry validation
     -> two-phase local recorded session coordinator
     -> natural-language translation boundary
     -> synthetic offline translation evaluation
     -> structured analytics request
     -> local catalog and approved-relationship validation
     -> review-ready semantic catalog and ambiguity index
     -> parameterized SELECT dry-run plan
     -> exact plan revalidation
     -> controlled read-only execution and result evidence
     -> deterministic bounded result presentation and facts
     -> cited recorded result narration
     -> synthetic exact-answer and control-total evaluation
     -> hash-bound benchmark human review and approval
     -> immutable dataset-backed benchmark validation (dry-run)
     -> approved dataset-backed offline evaluation

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
| Analytics module registry | Describe and statically validate current session contracts and workflow order | No dynamic import, dispatch, execution, network, concurrency, or auto-approval. |
| Analytics session module | Coordinate the recorded analytics stages through an exact human plan-review checkpoint | Two separate immutable phases; reuse stage entrypoints; never self-approve or bypass blockers. |
| Conversion/profile/clean/schema modules | Transform and describe local data | Never modify raw input files. |
| Synthetic performance harness | Measure selected Pandas-heavy stages in isolated processes over generated Parquet | No external input, production threshold, dataset authority, or persistent synthetic rows. |
| Schema/key inference | Produce schema plus candidate PK/FK evidence from Parquet metadata and local DuckDB aggregates | Preserve candidate status and output compatibility; never promote relationships or keys. |
| Validation/SQL/export/documentation modules | Validate and publish analytical artifacts | Generated output is not approval evidence by itself. |
| ERP modeling/review modules | Produce candidates, review workbooks, and validation reports | Do not write approved model files unless an apply contract is explicitly authorized. |
| Product materialization module | Validate applied Product decisions and generate local preview/lineage artifacts | Fail closed without partial preview when approved source evidence is missing. |
| Product canonical promotion module | Validate the complete Product snapshot and produce a hash-bound dry-run plan | Report readiness only; never apply canonical state or copy private row values. |
| Analytics query-plan module | Compile a bounded structured request against a local DuckDB catalog | Never accept raw SQL, execute queries, expose filter values, or use unapproved joins. |
| Analytics query-execution module | Revalidate and execute an exact reviewed plan with bounded local resources | Read-only DuckDB only; disable external access; fail closed without partial results. |
| Analytics result-presentation module | Revalidate Stage 5B evidence and render bounded local facts and Markdown | Stage 5B remains numeric authority; no query, database connection, recomputation, network, or divergent overwrite. |
| Analytics result-narration module | Validate cited prose against exact deterministic facts | Exact numeric grounding and required controls; narration is non-authoritative and the CLI is recorded/offline only. |
| Analytics semantic-catalog module | Validate business terms, fields, measures, paths, and ambiguity against physical metadata | Metadata only; approved relationships only; never self-approve semantics or resolve ambiguity silently. |
| Analytics translation-evaluation module | Replay synthetic translation, clarification, rejection, timeout, and failure cases through Stage 5D | Offline in-memory providers only; evidence omits questions/responses and is not live-model quality evidence. |
| Analytics answer-evaluation module | Chain synthetic recorded translation through exact request, Stage 5A plan, Stage 5B execution, and expected-result controls | Temporary allowlisted DuckDB only; no setup SQL, real data, narration, or persisted case artifacts. |
| Dataset benchmark review/approval module | Prepare per-case human review and generate an immutable bounded approval | Dry-run by default; never self-approve, overwrite authority, query data, or expand into provider/upload/training permission. |
| Dataset benchmark-validation module | Bind immutable DuckDB, semantics, relationships, expected answers, tolerances, and separate approval by SHA-256 | Hash opaque local files only; never open/query the database or infer approval from conversion manifests. |
| Dataset benchmark-evaluation module | Replay an approved pack through recorded Stage 5D, exact request gating, Stage 5A, Stage 5B, and typed comparison | Recheck every authority hash before each query; fixed read-only limits; no live provider, network, persisted rows, or real dataset by default. |
| Benchmark SQL conversion module | Parse local sample T-SQL table definitions and rows into DuckDB and Parquet | Never execute source SQL or external operations; output remains unapproved benchmark evidence. |
| `datasets/benchmarks/` | Separate ignored raw/derived data from versioned inventories and contracts | Dataset presence or conversion is not approval for training, upload, or relationship promotion. |
| `config/data_model/` | Version candidate state, domain mappings, and approvals | Keep candidate and approved files separate. |
| `originaldatabase/` | Private source exports | Read only; excluded from Git. |
| `outputs/` | Reproducible generated artifacts | Excluded from Git; do not hand-edit. |
| `.codex/` | Domain guidance, skills, and agent profiles | Guidance only; cannot override code, tests, or human approvals. |

## Data Contracts

The default workflow accepts an input directory and output directory and returns `WorkflowResult` with output, database, table, metadata, and Tableau locations. Staged commands use explicit paths and return summaries or artifact locations from their module entrypoints.

The first formal module registry now describes the two recorded analytics
session phases and validates inputs, outputs, dependencies, validation, tests,
failure policy, entrypoint signatures, and review gates without changing current
Python entrypoints or CLI commands. Other pipelines remain outside this
registry, and dynamic orchestration is not implemented.

## State Model

Modeling decisions use distinct states such as candidate, pending review, approved, rejected, blocked, and conflicting. Key and relationship approvals live in `approved_keys.yml` and `approved_relationships.yml`; both are currently empty. Product-specific reconciliation state lives separately in `product_reconciliation_state.yml`. Human review and promotion-plan reports can establish readiness but must not silently apply state.

## Current Gaps

- The analytics-session registry is validation-only; common discovery, dynamic
  dispatch, and a registry covering other pipelines remain pending.
- No generic dependency graph, checkpoint, resume, or dry-run engine; only the recorded analytics session has narrow tested checkpoint/resume semantics.
- CLI stage dispatch and the default workflow are not yet unified under one orchestration contract.
- Some generated summaries become stale when later review steps run; consolidated state must cite the newest validation evidence.
- Semantic governance, Stage 5D translation evaluation, a synthetic Stage 5E exact-answer harness, dataset benchmark review/approval, dry-run binding validation, approved offline dataset-backed execution, deterministic result presentation, and recorded narration validation exist. No real semantic registry or benchmark pack is approved yet; live model-provider integration and a user interface are not implemented.
