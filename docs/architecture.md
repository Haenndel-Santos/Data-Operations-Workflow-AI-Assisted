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
     -> schema and business-flow documentation
```

## Boundaries

| Area | Responsibility | Important boundary |
| --- | --- | --- |
| `src/data_ops_lab/cli.py` | Parse commands and dispatch entrypoints | Do not absorb module business logic. |
| `src/data_ops_lab/workflow.py` | Coordinate the default analytical pipeline | Preserve `run_workflow` and `WorkflowResult` compatibility. |
| Conversion/profile/clean/schema modules | Transform and describe local data | Never modify raw input files. |
| Validation/SQL/export/documentation modules | Validate and publish analytical artifacts | Generated output is not approval evidence by itself. |
| ERP modeling/review modules | Produce candidates, review workbooks, and validation reports | Do not write approved model files unless an apply contract is explicitly authorized. |
| `config/data_model/` | Version candidate state, domain mappings, and approvals | Keep candidate and approved files separate. |
| `originaldatabase/` | Private source exports | Read only; excluded from Git. |
| `outputs/` | Reproducible generated artifacts | Excluded from Git; do not hand-edit. |
| `.codex/` | Domain guidance, skills, and agent profiles | Guidance only; cannot override code, tests, or human approvals. |

## Data Contracts

The default workflow accepts an input directory and output directory and returns `WorkflowResult` with output, database, table, metadata, and Tableau locations. Staged commands use explicit paths and return summaries or artifact locations from their module entrypoints.

Formal module manifests are not yet implemented. Before adding dynamic orchestration, define contracts for inputs, outputs, dependencies, validation, and failure policy without breaking current Python entrypoints or CLI commands.

## State Model

Modeling decisions use distinct states such as candidate, pending review, approved, rejected, blocked, and conflicting. Versioned approvals live only in `approved_keys.yml` and `approved_relationships.yml`; both are currently empty. Human review reports can establish readiness but must not silently apply state.

## Current Gaps

- No common module discovery or manifest registry.
- No shared dependency graph, checkpoint, resume, or dry-run engine.
- CLI stage dispatch and the default workflow are not yet unified under one orchestration contract.
- Some generated summaries become stale when later review steps run; consolidated state must cite the newest validation evidence.
