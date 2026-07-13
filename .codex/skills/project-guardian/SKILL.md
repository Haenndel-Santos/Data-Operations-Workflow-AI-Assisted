---
name: project-guardian
description: Protect the project's mission, scope, architecture, current stage, durable decisions, and module boundaries. Use at the start of substantial tasks, roadmap or architecture changes, cross-module work, scope disputes, project-state reviews, or whenever a proposed change may conflict with the final objective or active blockers.
---

# Project Guardian

## Inputs

Read `AGENTS.md`, `docs/project-master.md`, `docs/progress.md`, relevant entries in `docs/decisions.md`, the latest handoff, Git state, and affected tests/contracts. Read `.codex/project-context/eds-sql-domain-rules.md` for ERP modeling.

## Workflow

1. State the final objective and active project stage.
2. Compare the request with current capabilities, blockers, and durable decisions.
3. Identify affected module boundaries, contracts, data, approvals, and tests.
4. Select the smallest change that advances the current stage.
5. Reject or defer work that is premature, destructive, duplicative, or unrelated.
6. Define completion evidence and the next logical milestone.

## Output

Provide a short alignment decision: objective, current state, allowed scope, protected boundaries, risks, completion criteria, and next step.

## Hard Rules

- Treat code and tests as stronger evidence than summaries.
- Human approval always wins; never convert missing review into approval.
- Preserve candidate/approved separation and private/generated data boundaries.
- Escalate strategic choices or destructive risk instead of assuming authority.
- Do not use this skill to implement the change; hand implementation to the narrowest relevant skill.
