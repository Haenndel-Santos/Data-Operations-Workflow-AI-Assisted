---
name: project-orchestrator
description: Coordinate project workflows, dependencies, execution order, state, validation, failure handling, partial runs, dry-run, checkpoints, and safe resume. Use when selecting or sequencing multiple modules, designing orchestrator behavior, diagnosing stage dependencies, or planning a resumable workflow without moving domain logic into the coordinator.
---

# Project Orchestrator

## Inputs

Read `docs/orchestrator.md`, affected module contracts, dependency evidence, current run state, relevant tests, and approval gates.

## Workflow

1. Inventory available entrypoints and their declared inputs, outputs, dependencies, validation, and failure policy.
2. Select the requested workflow and reject missing or cyclic dependencies.
3. Produce a deterministic execution order and explicit stop conditions.
4. Validate inputs and approvals before execution.
5. Execute only authorized stages, recording status and outputs consistently.
6. On failure, preserve the last valid checkpoint and report recovery options.
7. Support partial execution, dry-run, and resume only when their state semantics are explicit and tested.
8. Summarize completed, skipped, blocked, and failed stages.

## Output

Return a workflow plan or result with ordered stages, contracts, validation gates, state transitions, failures, outputs, and safe resume point.

## Hard Rules

- Coordinate; do not duplicate specialized business logic.
- Never hide failures or mutate inputs silently.
- Never treat candidate or blocked review state as approval.
- Preserve existing CLI and Python entrypoint compatibility unless a migration is approved.
- Do not add concurrency until ordering, consistency, limits, memory, and failure behavior are measured and tested.
