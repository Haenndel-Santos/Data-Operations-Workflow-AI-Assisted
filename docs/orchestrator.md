# Orchestrator

## Current State

`src/data_ops_lab/workflow.py` contains the fixed default analytical sequence. It converts inputs, profiles and cleans staging data, infers schema/keys, validates relationships, generates SQL, builds DuckDB, exports Tableau files, writes documentation, and returns `WorkflowResult`.

`src/data_ops_lab/cli.py` separately dispatches ERP modeling and human-review commands. These commands are explicit and testable, but they do not yet share dependency resolution, checkpoint state, or resume behavior. Step 3E.4 provides a command-local decision digest; Step 3E.5 adds a deterministic ready/blocked materialization checkpoint; Step 3E.6 binds that complete snapshot to applied state in a dry-run promotion plan. None is yet shared orchestrator infrastructure.

Stage 5A separately introduces a dry-run analytics query planner. Stage 5B adds
an explicit controlled executor that requires exact plan revalidation and
produces bounded local result evidence. Stage 5C adds metadata-only semantic
catalog validation with explicit ambiguity and human-review state. The local
analytics-session service now provides one narrow two-phase coordinator for
recorded Stage 5D through result narration. It stops at an immutable plan-review
checkpoint and resumes only with a separately completed exact human review. It
does not change `workflow.py` or provide general module discovery.

`src/data_ops_lab/module_registry.py` now validates the first versioned
declarative registry at `config/orchestrator/analytics_module_registry.yml`.
It inspects entrypoint source and exact signatures statically, validates module
and workflow dependencies, cycles, capabilities, test files, stage order,
failure policies, and the human execution gate, then writes dry-run evidence.
It cannot dispatch or execute a module.

`reference-dataset-validate` remains a separate explicit Phase 2 entrypoint. It
orders provenance/license/use preflight before any read-only DuckDB profiling
and stops at `ready_for_relationship_review` without an exact completed human
review. With a completed review it may report `ready_for_semantic_modeling` and
derive an approved-relationship registry containing accepted decisions only.
It is not yet part of the declarative analytics-session registry.

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
   Implemented for the recorded analytics session.
2. Validate contracts and dependencies in isolation. Implemented for the
   recorded analytics session with static, non-executing registry validation.
3. Add workflow selection and ordered execution behind current CLI compatibility. Implemented narrowly for the recorded analytics session.
4. Add explicit run state, logs, and failure summaries. Implemented for the recorded analytics session only.
5. Add partial execution and dry-run. The analytics session has an explicit preparation phase; generic partial runs remain pending.
6. Add idempotent checkpoints and safe resume only after state semantics are tested. Implemented for exact analytics plan review; generic resume remains pending.

Each step requires contract, unit, integration, workflow, and regression coverage proportional to its impact. Do not combine this evolution with data migration, dependency upgrades, or unrelated refactoring.

## Current Safety Gate

No orchestrator feature may treat `pending_review`, a valid-but-blocked workbook, or `ready_for_canonical_state_review` as approval. Product Step 3E.4 contains the explicitly replaced 15-approved/13-rejected state, Step 3E.5 produced a complete validated local preview, and Step 3E.6 produced only a hash-bound dry-run promotion plan. No downstream stage may bypass the applied digest, restore excluded identities, consume stale blocked outputs, apply canonical state, or import/synchronize the preview without a separate authorized contract.

No future AI adapter may submit raw model-generated SQL. It must produce the versioned structured analytics request, and cross-table plans must continue to require approved relationships. `ready_for_execution_review` is not execution authorization; Stage 5B runs only through its separate explicit entrypoint after exact plan revalidation.

`ready_for_semantic_review` is also not semantic approval. Future orchestration
must require a separate approved semantic representation before Stage 5D may
resolve business terms operationally.

`awaiting_execution_review` is not execution authority. The analytics-session
resume command requires a separate completed human review bound to the exact
preparation manifest and plan hashes. It cannot auto-approve its own output.

A `valid` module registry is not execution authority. Registry controls require
dynamic execution, concurrency, network, and review auto-approval to remain
disabled, and the validator has no execution or apply mode.

`ready_for_relationship_review` is likewise not relationship authority. A
future semantic-catalog workflow may consume only the accepted subset from a
completed exact relationship review that revalidates as
`ready_for_semantic_modeling`.
