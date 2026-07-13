---
name: module-contract
description: Define and validate module contracts covering entrypoints, inputs, outputs, schemas, dependencies, errors, versioning, validation, tests, and compatibility. Use when adding an orchestrated module, changing a public function or CLI behavior, reviewing cross-module boundaries, or preparing a backward-compatible contract migration.
---

# Module Contract

## Contract Shape

Define these fields when applicable:

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

## Workflow

1. Identify the entrypoint and every current consumer.
2. Describe accepted inputs, required/optional fields, schemas, and preconditions.
3. Describe outputs, side effects, generated paths, and invariants.
4. Define dependency and execution-order requirements.
5. Define typed or structured errors, failure policy, idempotency, and retry/resume semantics.
6. Compare the proposal with existing behavior and tests.
7. Add the smallest contract and regression tests that prove compatibility.
8. Document versioning or an explicit migration when compatibility cannot be preserved.

## Output

Produce a concise contract, compatibility assessment, affected consumers, required tests, migration notes, and unresolved risks.

## Hard Rules

- Prefer structured data models and parsers over ad hoc string contracts.
- Do not change public behavior without consumer analysis and tests.
- Do not hide filesystem or approval side effects.
- Keep candidate generation separate from approval application.
- Never define a contract that permits silent source-data mutation.
