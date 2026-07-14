# Analytics Module Registry

## Purpose

`config/orchestrator/analytics_module_registry.yml` is the first versioned
declarative registry for the governed analytics session. It records current
Python entrypoints, exact parameter names, outputs, dependencies, capabilities,
workflow membership, validation responsibilities, test files, stage order,
terminal states, failure policies, and the execution-review gate.

The registry is descriptive and validation-only. The existing CLI and Python
entrypoints remain the only execution paths.

## Version 1 Boundary

The top-level contract contains exactly:

```yaml
version: 1
status: active
controls:
  dynamic_execution_enabled: false
  concurrency_enabled: false
  network_enabled: false
  review_auto_approval_enabled: false
modules: []
workflows: []
```

Each module uses the fields defined in [Orchestrator](orchestrator.md): name,
version, description, status, entrypoint, inputs, outputs, dependencies,
capabilities, workflows, validation, tests, and failure policy. Version 1
accepts implemented modules only and requires declared inputs to match the
entrypoint parameter names and order exactly.

The initial fixture describes the two immutable recorded-session phases:

| Workflow | Coordinator | Ordered stages | Gate |
| --- | --- | --- | --- |
| `recorded_local_prepare` | `analytics_session_prepare` | translate, plan | Stops before execution |
| `exact_reviewed_local_resume` | `analytics_session_resume` | execute, present, narrate | Separate exact human approval before execute |

## Dry-Run Validation

Run from the project root:

```powershell
$env:PYTHONPATH = "src"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -m data_ops_lab analytics-module-registry-validate --output "outputs\<run-id>\analytics_module_registry_validation"
```

The validator:

- enforces exact versioned fields, bounded counts, identifiers, and safe
  disabled controls;
- locates entrypoint source and inspects its AST without importing or calling
  the target module;
- requires exact declared parameter names and existing declared test files;
- validates module dependencies, missing references, cycles, workflow
  membership, stage dependencies, and deterministic earlier-stage order;
- requires `stop` for every initial stage failure policy;
- requires a separate non-automatic human review gate before any stage with
  `read_only_execution` capability;
- hashes the registry before and after validation and reports drift;
- writes immutable, byte-reusable evidence and refuses divergent overwrite.

## Evidence

The output directory contains:

| File | Meaning |
| --- | --- |
| `analytics_module_registry_validation.yml` | Source SHA-256, counts, status, and disabled-control evidence |
| `analytics_module_registry_blockers.csv` | Structured contract, dependency, workflow, or safety blockers |
| `analytics_module_registry_report.md` | Concise human-readable boundary and result |

`valid` means the declarative contract is internally consistent with the local
source tree. `blocked` means one or more checks failed. Neither status approves
data, semantics, relationships, a plan, execution, provider use, network use,
external disclosure, upload, or training.

## Compatibility And Non-Authorizations

- No existing analytics entrypoint signature or session behavior changed.
- No dynamic import, dispatch, execution, partial-run engine, or generic resume
  engine is enabled.
- No review can be completed or approved by this validator.
- No DuckDB, dataset, provider, credential, or external service is accessed.
- Future execution from the registry requires a separate reviewed contract and
  compatibility tests.
