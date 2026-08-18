# Project Agent Instructions

These instructions apply to Codex, Claude Code, and any other agent working in this repository.

## Mission

Build a modular, customer-hosted, local-first Data Intelligence platform that turns raw operational spreadsheets and local database evidence into validated analytical datasets, an evidence-backed data model, governed semantic context, and evidence-backed analytical answers. The intended product users are business owners, managers, and operations teams at small and medium-sized businesses who need decision-ready analysis without SQL; data and operations analysts remain advanced users and reviewers. AI may interpret, propose, and explain; deterministic code retains authority over transformations, calculations, permissions, SQL planning/execution, approvals, evidence, and lineage. Its final form should use a central orchestrator, specialized modules, explicit contracts, reproducible offline tests, safe checkpoints, a Product API and UI behind identity and authorization, and enough shared documentation for another agent to continue without private conversation history. `docs/project-master.md` is the authoritative statement of this mission.

## Source Of Truth

Use this authority order when sources disagree:

1. Executable code and versioned contracts.
2. Automated tests.
3. Git history and current diffs.
4. `docs/project-master.md`.
5. `docs/decisions.md`.
6. `docs/progress.md`.
7. `docs/agent-handoff.md`.
8. Previous conversation summaries.

Generated reports are evidence, not authority over versioned approvals. Prefer the newest validated report and record stale-document conflicts.

## Required Start

Before changing anything:

1. Read this file, `docs/progress.md`, and the newest entry in `docs/agent-handoff.md`.
2. Read only the relevant parts of `docs/project-master.md`, `docs/decisions.md`, module contracts, and tests.
3. Check `git status --short --branch`, the current branch, recent commits, and uncommitted diffs.
4. Check for active or incomplete work in the same area.
5. Identify the objective, current stage, next logical gap, affected files, tests, risks, and completion criteria.

Expand context progressively. Do not read the entire repository without a concrete dependency.

## Permanent Safety Rules

- Human approval always wins over automation.
- Never silently change source data, approved YAML files, completed review files, or generated outputs.
- Keep candidates, approved decisions, rejected decisions, blocked items, and assumptions separate.
- Do not invent ERP relationships or promote candidates without evidence.
- Do not connect to external databases, run migrations/imports/sync jobs, or process production data without explicit authorization.
- Do not expose secrets, commit `.env`, overwrite unknown files, or discard another agent's work.
- Treat `originaldatabase/` as private read-only input and `outputs/` as generated artifacts.
- Write every repository artifact in English: code, identifiers, comments,
  commit messages, pull request and issue text, documentation, skills, YAML
  keys, and blocker text. The owner may converse in another language; the
  artifacts do not.

Read `.codex/project-context/eds-sql-domain-rules.md` before ERP modeling work.

## Execution Protocol

Use this sequence:

```text
ORIENT -> LOCATE -> UNDERSTAND -> PLAN -> IMPLEMENT -> TEST
-> CORRECT -> VALIDATE -> DOCUMENT -> SUMMARIZE -> HAND OFF
```

- Work in the smallest unit that produces verifiable value.
- Prefer small, additive, reversible changes that preserve current contracts.
- Reuse an existing module, utility, contract, test, or skill before creating one.
- Keep orchestration in the orchestrator and specialized logic in modules.
- Do not add dependencies without a concrete need, compatibility review, and offline test strategy.
- Continue through implementation, validation, and documentation when the next step is inside the approved stage.
- Stop for strategic choices, missing authority, destructive risk, credentials, or equivalent architectural alternatives with material impact.

## Contracts And Tests

For an orchestrated module, define as applicable: name, version, description, status, entrypoint, inputs, outputs, dependencies, capabilities, workflows, validation, tests, and failure policy.

Do not change a public contract without identifying consumers, adding tests, documenting the change, and preserving compatibility or defining an explicit migration.

Run the smallest relevant test first, then broaden based on risk. The main suite must remain offline. External integrations require mocks/fixtures for default tests and separately labeled online tests.

See `docs/testing.md` for current commands and environment notes.

## Shared Memory

- `docs/project-master.md`: mission, architecture, modules, stages, and global success criteria.
- `docs/progress.md`: current consolidated state only.
- `docs/decisions.md`: durable architectural and modeling decisions.
- `docs/architecture.md`: component and data-flow boundaries.
- `docs/testing.md`: validation strategy and commands.
- `docs/orchestrator.md`: current and target orchestration behavior.
- `docs/ai-implementation-roadmap.md`: ordered implementation phases, exit gates, quality targets, and product-readiness path.
- `docs/agent-handoff.md`: short chronological session history.
- `CHANGELOG.md`: release-relevant or user-visible changes only.

At the end of a session that changes versioned files, append a factual entry to `docs/agent-handoff.md` and update `docs/progress.md`. Update `docs/decisions.md` only for a durable decision and `CHANGELOG.md` only when users or releases are affected. Never rewrite prior handoff entries.

## Reporting To The Owner

Deliver every end-of-task report, status update, or review result to the owner
as one single Markdown block that can be copied in one action: one outer fenced
block, no text before or after it, and no nested fenced code blocks inside it
(use indented text or lists for commands, diagrams, and examples). The report
language follows the conversation; every repository artifact stays in English.

## Completion And Git

A task is complete only when behavior or documentation is finished, contracts are preserved, relevant checks pass, the diff is reviewed, no temporary files or secrets are included, and the next logical step is recorded.

When authorized and practical, finish a logical unit with a small commit using `type(scope): description`. Do not claim a clean worktree without verifying it.
