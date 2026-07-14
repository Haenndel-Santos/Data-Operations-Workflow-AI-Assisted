# Orchestrator

## Current State

`src/data_ops_lab/workflow.py` contains the fixed default analytical sequence. It converts inputs, profiles and cleans staging data, infers schema/keys, validates relationships, generates SQL, builds DuckDB, exports Tableau files, writes documentation, and returns `WorkflowResult`.

`src/data_ops_lab/cli.py` separately dispatches ERP modeling and human-review commands. These commands are explicit and testable, but they do not yet share dependency resolution, checkpoint state, or resume behavior. Step 3E.4 provides a command-local decision digest; Step 3E.5 adds a deterministic ready/blocked materialization checkpoint; Step 3E.6 binds that complete snapshot to applied state in a dry-run promotion plan. None is yet shared orchestrator infrastructure.

Stage 5A separately introduces a dry-run analytics query planner. Stage 5B adds
an explicit controlled executor that requires exact plan revalidation and
produces bounded local result evidence. Stage 5C adds metadata-only semantic
catalog validation with explicit ambiguity and human-review state. None of the
analytics modules performs an AI call or is yet coordinated by `workflow.py`.

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

No orchestrator feature may treat `pending_review`, a valid-but-blocked workbook, or `ready_for_canonical_state_review` as approval. Product Step 3E.4 contains the explicitly replaced 15-approved/13-rejected state, Step 3E.5 produced a complete validated local preview, and Step 3E.6 produced only a hash-bound dry-run promotion plan. No downstream stage may bypass the applied digest, restore excluded identities, consume stale blocked outputs, apply canonical state, or import/synchronize the preview without a separate authorized contract.

No future AI adapter may submit raw model-generated SQL. It must produce the versioned structured analytics request, and cross-table plans must continue to require approved relationships. `ready_for_execution_review` is not execution authorization; Stage 5B runs only through its separate explicit entrypoint after exact plan revalidation.

`ready_for_semantic_review` is also not semantic approval. Future orchestration
must require a separate approved semantic representation before Stage 5D may
resolve business terms operationally.
