---
name: test-engineer
description: Plan and execute progressive offline validation for units, contracts, integrations, workflows, regressions, end-to-end behavior, and ERP data integrity. Use when behavior or contracts change, when diagnosing failures, at repository checkpoints, or when validating PK/FK, prefix, preservation, and approval-safety rules.
---

# Test Engineer

## Purpose

Define and run proportionate validation from focused unit checks through offline end-to-end workflows, including ERP integrity and preservation rules.

## When to use this skill

Use this skill for validation planning, pytest execution, contract and integration checks, data integrity checks, regression expectations, failure interpretation, and test recommendations when behavior or modeling logic changes.

## Project-specific knowledge

- Use `.codex/project-context/eds-sql-domain-rules.md` as shared context.
- Known prefixes include `CR`, `DE`, `CP`, `OC`, `CQ`, `CI`, `GU`, `GO`, `ON`, `IF`, `RFQ`, `VK`, and `PD`.
- Candidate PK/FK checks should verify uniqueness, nullability, orphan references, malformed prefixes, and expected line-table repetition.
- Documentation-only changes do not require invented tests.

## Hard rules

- Always run the existing test suite when source code changes are made.
- For documentation-only changes, do not invent tests.
- Recommend tests when new modeling logic is introduced.
- Do not change test expectations to fit unapproved modeling decisions.
- Separate data validation failures from code regression failures.
- Keep the main suite offline; isolate and label online tests.
- Add the smallest test that proves the new behavior before broadening coverage.

## Recommended workflow

1. Read the shared domain rules.
2. Determine whether the task changed source code, SQL logic, data, or documentation only.
3. Select the lowest sufficient level: unit, contract, integration, workflow, regression, end-to-end, then reliability/performance.
4. For code or SQL logic changes, run targeted checks before the existing full suite.
5. For documentation-only changes, confirm links and formatting instead of inventing tests.
6. Interpret failures by separating raw data issues, model assumptions, approval gaps, and code defects.
7. Record exact commands, outcomes, skipped online checks, and remaining risk.

## Expected outputs

- Test plan.
- Pytest command summary.
- Validation checklist.
- Failure interpretation.

## Things to never do

- Never skip existing tests after source code changes.
- Never invent test results.
- Never treat documentation-only changes as requiring fake validation logic.
- Never approve a candidate key without uniqueness and nullability checks.
- Never hide test failures or unresolved validation gaps.
