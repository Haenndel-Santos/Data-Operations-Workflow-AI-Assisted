# Orchestrator

## Current State

`src/data_ops_lab/workflow.py` contains the fixed default analytical sequence. It converts inputs, profiles and cleans staging data, infers schema/keys, validates relationships, generates SQL, builds DuckDB, exports Tableau files, writes documentation, and returns `WorkflowResult`.

`src/data_ops_lab/cli.py` separately dispatches ERP modeling and human-review commands. These commands are explicit and testable, but they do not yet share dependency resolution, checkpoint state, or resume behavior. Step 3E.4 now provides a command-local dry-run and decision digest; this is not yet shared orchestrator infrastructure.

## Responsibility

The orchestrator may discover, validate, select, order, execute, record, recover, and summarize module work. It must not duplicate specialized module logic, hide failures, mutate inputs, or promote unapproved decisions.

## Target Module Contract

Use these fields when a module becomes orchestratable:

```yaml
name:
version:
description:
status:
entrypoint:
inputs:
outputs:
dependencies:
capabilities:
workflows:
validation:
tests:
failure_policy:
```

## Incremental Evolution

1. Document contracts for existing entrypoints without changing behavior.
2. Validate contracts and dependencies in isolation.
3. Add workflow selection and ordered execution behind current CLI compatibility.
4. Add explicit run state, logs, and failure summaries.
5. Add partial execution and dry-run.
6. Add idempotent checkpoints and safe resume only after state semantics are tested.

Each step requires contract, unit, integration, workflow, and regression coverage proportional to its impact. Do not combine this evolution with data migration, dependency upgrades, or unrelated refactoring.

## Current Safety Gate

No orchestrator feature may treat `pending_review` or a valid-but-blocked review workbook as approval. The Product Step 3E.4 state is now explicitly approved and applied; downstream Product work must verify its digest and consume its actions without silently promoting unrelated pending key or relationship candidates.
