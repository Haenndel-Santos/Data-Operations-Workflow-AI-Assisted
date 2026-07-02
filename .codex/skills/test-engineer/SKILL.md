# Test Engineer

## Purpose

Define and run validation checks for PK uniqueness, FK consistency, missing references, naming conventions, prefix rules, and regression tests.

## When to use this skill

Use this skill for validation planning, pytest execution guidance, data integrity checks, regression test expectations, interpreting test failures, and recommending tests when modeling logic changes.

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

## Recommended workflow

1. Read the shared domain rules.
2. Determine whether the task changed source code, SQL logic, data, or documentation only.
3. For code or SQL logic changes, run the existing test suite and targeted validation checks.
4. For documentation-only changes, confirm file presence and formatting checks instead of inventing tests.
5. Interpret failures by separating raw data issues, model assumptions, approval gaps, and code defects.
6. Recommend additional tests when new modeling logic is introduced.

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
