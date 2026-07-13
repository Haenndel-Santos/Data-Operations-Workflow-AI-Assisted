---
name: implementation
description: Implement small, approved, testable, and reversible changes within existing project contracts and architecture. Use after scope and contracts are understood for focused code, test, configuration, or documentation changes; do not use for unresolved strategic design, unapproved data operations, or broad refactoring.
---

# Implementation

## Inputs

Require an approved objective, current Git state, relevant contract, affected files, existing tests, risks, and completion criteria.

## Workflow

1. Locate the narrowest existing implementation and tests.
2. Confirm no overlapping uncommitted work will be overwritten.
3. Implement the smallest additive change that satisfies the contract.
4. Add or update focused tests when behavior changes.
5. Run targeted validation, then broader checks proportional to risk.
6. Review the diff for unrelated churn, secrets, temporary files, and contract drift.
7. Update only the affected state or decision documentation.
8. Append a factual handoff and prepare a small checkpoint commit when authorized.

## Output

Report changed files, preserved/changed contracts, behavior, validation, limitations, project stage, Git state, and next step.

## Hard Rules

- Do not start from implementation before locating contracts and tests.
- Do not mix feature work, broad refactoring, dependency upgrades, migrations, and interface changes in one unit.
- Never modify raw/private data, generated outputs, completed reviews, or approved model files unless explicitly authorized.
- Do not install dependencies when existing tools are sufficient.
- Stop when the implementation requires a strategic decision or destructive authority outside the approved scope.
