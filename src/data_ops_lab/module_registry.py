from __future__ import annotations

import ast
import csv
import importlib.util
import io
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from .analytics_query_plan import add_blocker
from .source_onboarding import ensure_dir, file_sha256


MANIFEST_NAME = "analytics_module_registry_validation.yml"
BLOCKERS_NAME = "analytics_module_registry_blockers.csv"
REPORT_NAME = "analytics_module_registry_report.md"
OUTPUT_NAMES = {MANIFEST_NAME, BLOCKERS_NAME, REPORT_NAME}
MAX_REGISTRY_BYTES = 1_000_000
MAX_ENTRYPOINT_SOURCE_BYTES = 2_000_000
MAX_MODULES = 128
MAX_WORKFLOWS = 64
MAX_STAGES_PER_WORKFLOW = 128
MAX_GATES_PER_WORKFLOW = 64
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{1,79}$")
ENTRYPOINT = re.compile(r"^data_ops_lab(?:\.[a-z][a-z0-9_]*)+\.[a-z][a-z0-9_]*$")
MODULE_FIELDS = {
    "name",
    "version",
    "description",
    "status",
    "entrypoint",
    "inputs",
    "outputs",
    "dependencies",
    "capabilities",
    "workflows",
    "validation",
    "tests",
    "failure_policy",
}
WORKFLOW_FIELDS = {
    "name",
    "version",
    "description",
    "coordinator",
    "stages",
    "gates",
    "terminal_statuses",
    "failure_policy",
}
STAGE_FIELDS = {
    "id",
    "module",
    "depends_on",
    "expected_statuses",
    "failure_policy",
}
GATE_FIELDS = {
    "id",
    "before_stage",
    "type",
    "required_decision",
    "auto_approval",
}
REQUIRED_CONTROLS = {
    "dynamic_execution_enabled": False,
    "concurrency_enabled": False,
    "network_enabled": False,
    "review_auto_approval_enabled": False,
}
REVIEW_GATED_CAPABILITIES = {"read_only_execution"}


@dataclass(frozen=True)
class ModuleRegistryValidationResult:
    output_dir: Path
    status: str
    manifest_path: Path
    blockers_path: Path
    report_path: Path
    blocker_count: int
    module_count: int
    workflow_count: int
    stage_count: int
    outputs_changed: bool


def canonical_yaml(payload: dict[str, Any]) -> str:
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False)


def blockers_csv(blockers: list[dict[str, str]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=["blocker_id", "blocker_type", "field", "explanation"],
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(blockers)
    return buffer.getvalue()


def read_registry(path: Path, blockers: list[dict[str, str]]) -> dict[str, Any]:
    if not path.is_file():
        add_blocker(blockers, "registry_missing", "The module registry is missing.", field="registry")
        return {}
    try:
        size = path.stat().st_size
    except OSError:
        add_blocker(blockers, "registry_unreadable", "The module registry cannot be read.", field="registry")
        return {}
    if size > MAX_REGISTRY_BYTES:
        add_blocker(
            blockers,
            "registry_too_large",
            f"The module registry must be at most {MAX_REGISTRY_BYTES} bytes.",
            field="registry",
        )
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError):
        add_blocker(blockers, "invalid_registry_yaml", "Registry must be UTF-8 YAML.", field="registry")
        return {}
    if not isinstance(payload, dict):
        add_blocker(blockers, "invalid_registry_mapping", "Registry must be a mapping.", field="registry")
        return {}
    return payload


def valid_text(value: Any, *, maximum: int = 1_000) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= maximum


def validate_string_list(
    value: Any,
    blockers: list[dict[str, str]],
    field: str,
    *,
    allow_empty: bool = False,
) -> list[str]:
    if (
        not isinstance(value, list)
        or (not allow_empty and not value)
        or not all(valid_text(item, maximum=200) for item in value)
        or len(set(value)) != len(value)
    ):
        add_blocker(
            blockers,
            "invalid_string_list",
            "Field must be a unique bounded list of text values.",
            field=field,
        )
        return []
    return list(value)


def validate_identifier_list(
    value: Any,
    blockers: list[dict[str, str]],
    field: str,
    *,
    allow_empty: bool = False,
) -> list[str]:
    values = validate_string_list(value, blockers, field, allow_empty=allow_empty)
    if values and not all(IDENTIFIER.fullmatch(item) for item in values):
        add_blocker(
            blockers,
            "invalid_identifier_list",
            "Field values must be lower-case identifiers.",
            field=field,
        )
        return []
    return values


def entrypoint_parameter_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str] | None:
    if node.args.vararg is not None or node.args.kwarg is not None:
        return None
    positional = [*node.args.posonlyargs, *node.args.args]
    return [argument.arg for argument in positional] + [
        argument.arg for argument in node.args.kwonlyargs
    ]


def inspect_entrypoint(
    value: Any,
    declared_inputs: list[str],
    blockers: list[dict[str, str]],
    field: str,
) -> bool:
    if not isinstance(value, str) or not ENTRYPOINT.fullmatch(value):
        add_blocker(
            blockers,
            "invalid_entrypoint",
            "Entrypoint must be a data_ops_lab dotted function path.",
            field=field,
        )
        return False
    module_name, function_name = value.rsplit(".", 1)
    try:
        spec = importlib.util.find_spec(module_name)
    except (ImportError, AttributeError, ModuleNotFoundError, ValueError):
        spec = None
    if spec is None or not spec.origin or spec.origin in {"built-in", "frozen"}:
        add_blocker(
            blockers,
            "entrypoint_not_resolvable",
            "Declared entrypoint module cannot be located without importing it.",
            field=field,
        )
        return False
    source_path = Path(spec.origin)
    try:
        if not source_path.is_file() or source_path.stat().st_size > MAX_ENTRYPOINT_SOURCE_BYTES:
            raise OSError
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    except (OSError, UnicodeError, SyntaxError):
        add_blocker(
            blockers,
            "entrypoint_source_unreadable",
            "Declared entrypoint source cannot be inspected safely.",
            field=field,
        )
        return False
    target = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == function_name
        ),
        None,
    )
    if target is None:
        add_blocker(
            blockers,
            "entrypoint_not_resolvable",
            "Declared entrypoint function is not defined in the target module.",
            field=field,
        )
        return False
    parameters = entrypoint_parameter_names(target)
    if parameters is None:
        add_blocker(
            blockers,
            "entrypoint_variadic",
            "Registry entrypoints cannot use variadic positional or keyword parameters.",
            field=field,
        )
        return False
    if parameters != declared_inputs:
        add_blocker(
            blockers,
            "entrypoint_input_mismatch",
            "Declared inputs must exactly match the entrypoint parameter names and order.",
            field=field,
        )
        return False
    return True


def validate_test_path(
    value: str,
    project_root: Path,
    blockers: list[dict[str, str]],
    field: str,
) -> None:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != "tests":
        add_blocker(
            blockers,
            "invalid_test_path",
            "Test paths must be relative files under tests/.",
            field=field,
        )
        return
    if not (project_root / Path(*path.parts)).is_file():
        add_blocker(
            blockers,
            "test_file_missing",
            "Declared module test file does not exist.",
            field=field,
        )


def find_cycles(graph: dict[str, list[str]]) -> set[str]:
    visiting: set[str] = set()
    visited: set[str] = set()
    cyclic: set[str] = set()

    def visit(node: str, trail: list[str]) -> None:
        if node in visiting:
            start = trail.index(node) if node in trail else 0
            cyclic.update(trail[start:])
            return
        if node in visited:
            return
        visiting.add(node)
        trail.append(node)
        for dependency in graph.get(node, []):
            if dependency in graph:
                visit(dependency, trail)
        trail.pop()
        visiting.remove(node)
        visited.add(node)

    for name in graph:
        visit(name, [])
    return cyclic


def validate_modules(
    rows: Any,
    project_root: Path,
    blockers: list[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list) or not rows:
        add_blocker(blockers, "modules_missing", "Registry requires a non-empty modules list.", field="modules")
        return {}
    if len(rows) > MAX_MODULES:
        add_blocker(
            blockers,
            "too_many_modules",
            f"Registry may declare at most {MAX_MODULES} modules.",
            field="modules",
        )
        rows = rows[:MAX_MODULES]
    modules: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        field = f"modules[{index}]"
        if not isinstance(row, dict) or set(row) != MODULE_FIELDS:
            add_blocker(
                blockers,
                "invalid_module_contract",
                "Module contract fields are incomplete or unsupported.",
                field=field,
            )
            continue
        name = row.get("name")
        if not isinstance(name, str) or not IDENTIFIER.fullmatch(name) or name in modules:
            add_blocker(
                blockers,
                "invalid_module_name",
                "Module names must be unique lower-case identifiers.",
                field=f"{field}.name",
            )
            continue
        if row.get("version") != 1 or row.get("status") != "implemented":
            add_blocker(
                blockers,
                "unsupported_module_state",
                "Initial registry modules must be version 1 and implemented.",
                field=field,
            )
        if not valid_text(row.get("description")):
            add_blocker(
                blockers,
                "invalid_module_text",
                "Module descriptions must be bounded text.",
                field=f"{field}.description",
            )
        if not isinstance(row.get("failure_policy"), str) or not IDENTIFIER.fullmatch(
            row["failure_policy"]
        ):
            add_blocker(
                blockers,
                "invalid_module_failure_policy",
                "Module failure policy must be a lower-case identifier.",
                field=f"{field}.failure_policy",
            )
        normalized = dict(row)
        for list_field in (
            "inputs",
            "outputs",
            "dependencies",
            "capabilities",
            "workflows",
            "validation",
        ):
            normalized[list_field] = validate_identifier_list(
                row.get(list_field),
                blockers,
                f"{field}.{list_field}",
                allow_empty=list_field == "dependencies",
            )
        tests = validate_string_list(row.get("tests"), blockers, f"{field}.tests")
        normalized["tests"] = tests
        for test_index, value in enumerate(tests):
            validate_test_path(value, project_root, blockers, f"{field}.tests[{test_index}]")
        inspect_entrypoint(
            row.get("entrypoint"),
            normalized["inputs"],
            blockers,
            f"{field}.entrypoint",
        )
        modules[name] = normalized
    names = set(modules)
    graph: dict[str, list[str]] = {}
    for name, row in modules.items():
        dependencies = row.get("dependencies", [])
        graph[name] = dependencies if isinstance(dependencies, list) else []
        for dependency in graph[name]:
            if dependency == name or dependency not in names:
                add_blocker(
                    blockers,
                    "invalid_module_dependency",
                    "Module dependencies must reference another declared module.",
                    field=f"modules.{name}.dependencies",
                )
    cyclic = find_cycles(graph)
    if cyclic:
        add_blocker(
            blockers,
            "module_dependency_cycle",
            "Module dependency graph contains a cycle.",
            field="modules.dependencies",
        )
    return modules


def dependency_closure(
    direct_modules: set[str],
    modules: dict[str, dict[str, Any]],
) -> set[str]:
    closure = set(direct_modules)
    pending = list(direct_modules)
    while pending:
        module_name = pending.pop()
        for dependency in modules.get(module_name, {}).get("dependencies", []):
            if dependency in modules and dependency not in closure:
                closure.add(dependency)
                pending.append(dependency)
    return closure


def validate_workflows(
    rows: Any,
    modules: dict[str, dict[str, Any]],
    blockers: list[dict[str, str]],
) -> tuple[dict[str, set[str]], int]:
    if not isinstance(rows, list) or not rows:
        add_blocker(
            blockers,
            "workflows_missing",
            "Registry requires a non-empty workflows list.",
            field="workflows",
        )
        return {}, 0
    if len(rows) > MAX_WORKFLOWS:
        add_blocker(
            blockers,
            "too_many_workflows",
            f"Registry may declare at most {MAX_WORKFLOWS} workflows.",
            field="workflows",
        )
        rows = rows[:MAX_WORKFLOWS]
    workflow_modules: dict[str, set[str]] = {}
    stage_count = 0
    for workflow_index, workflow in enumerate(rows):
        field = f"workflows[{workflow_index}]"
        if not isinstance(workflow, dict) or set(workflow) != WORKFLOW_FIELDS:
            add_blocker(
                blockers,
                "invalid_workflow_contract",
                "Workflow fields are incomplete or unsupported.",
                field=field,
            )
            continue
        name = workflow.get("name")
        if not isinstance(name, str) or not IDENTIFIER.fullmatch(name) or name in workflow_modules:
            add_blocker(
                blockers,
                "invalid_workflow_name",
                "Workflow names must be unique lower-case identifiers.",
                field=f"{field}.name",
            )
            continue
        workflow_modules[name] = set()
        if workflow.get("version") != 1 or not valid_text(workflow.get("description")):
            add_blocker(
                blockers,
                "invalid_workflow_metadata",
                "Workflow must have version 1 and a bounded description.",
                field=field,
            )
        coordinator = workflow.get("coordinator")
        if not isinstance(coordinator, str) or coordinator not in modules:
            add_blocker(
                blockers,
                "invalid_workflow_coordinator",
                "Workflow coordinator must be a declared module assigned to the workflow.",
                field=f"{field}.coordinator",
            )
        elif name not in modules[coordinator].get("workflows", []):
            add_blocker(
                blockers,
                "invalid_workflow_coordinator",
                "Workflow coordinator must declare membership in this workflow.",
                field=f"{field}.coordinator",
            )
        else:
            workflow_modules[name].add(coordinator)
        stages = workflow.get("stages")
        if not isinstance(stages, list) or not stages:
            add_blocker(blockers, "workflow_stages_missing", "Workflow requires stages.", field=f"{field}.stages")
            continue
        if len(stages) > MAX_STAGES_PER_WORKFLOW:
            add_blocker(
                blockers,
                "too_many_workflow_stages",
                f"Workflow may declare at most {MAX_STAGES_PER_WORKFLOW} stages.",
                field=f"{field}.stages",
            )
            stages = stages[:MAX_STAGES_PER_WORKFLOW]
        stage_ids: set[str] = set()
        stage_modules: dict[str, str] = {}
        for stage_index, stage in enumerate(stages):
            stage_field = f"{field}.stages[{stage_index}]"
            if not isinstance(stage, dict) or set(stage) != STAGE_FIELDS:
                add_blocker(
                    blockers,
                    "invalid_workflow_stage",
                    "Workflow stage fields are incomplete or unsupported.",
                    field=stage_field,
                )
                continue
            stage_id = stage.get("id")
            module_name = stage.get("module")
            if not isinstance(stage_id, str) or not IDENTIFIER.fullmatch(stage_id) or stage_id in stage_ids:
                add_blocker(
                    blockers,
                    "invalid_stage_id",
                    "Stage IDs must be unique lower-case identifiers.",
                    field=f"{stage_field}.id",
                )
                continue
            dependencies = validate_identifier_list(
                stage.get("depends_on"), blockers, f"{stage_field}.depends_on", allow_empty=True
            )
            if any(dependency not in stage_ids for dependency in dependencies):
                add_blocker(
                    blockers,
                    "invalid_stage_order",
                    "Stage dependencies must reference earlier stages in the same workflow.",
                    field=f"{stage_field}.depends_on",
                )
            stage_ids.add(stage_id)
            stage_count += 1
            if not isinstance(module_name, str) or module_name not in modules:
                add_blocker(
                    blockers,
                    "invalid_stage_module",
                    "Stage module must be declared and assigned to this workflow.",
                    field=f"{stage_field}.module",
                )
            elif name not in modules[module_name].get("workflows", []):
                add_blocker(
                    blockers,
                    "invalid_stage_module",
                    "Stage module must declare membership in this workflow.",
                    field=f"{stage_field}.module",
                )
            else:
                stage_modules[stage_id] = module_name
                workflow_modules[name].add(module_name)
            validate_identifier_list(
                stage.get("expected_statuses"), blockers, f"{stage_field}.expected_statuses"
            )
            if stage.get("failure_policy") != "stop":
                add_blocker(
                    blockers,
                    "unsafe_stage_failure_policy",
                    "Initial workflow stages must stop on failure.",
                    field=f"{stage_field}.failure_policy",
                )
        gates = workflow.get("gates")
        safely_gated_stages: set[str] = set()
        if not isinstance(gates, list):
            add_blocker(blockers, "invalid_workflow_gates", "Workflow gates must be a list.", field=f"{field}.gates")
        else:
            if len(gates) > MAX_GATES_PER_WORKFLOW:
                add_blocker(
                    blockers,
                    "too_many_workflow_gates",
                    f"Workflow may declare at most {MAX_GATES_PER_WORKFLOW} gates.",
                    field=f"{field}.gates",
                )
                gates = gates[:MAX_GATES_PER_WORKFLOW]
            gate_ids: set[str] = set()
            for gate_index, gate in enumerate(gates):
                gate_field = f"{field}.gates[{gate_index}]"
                if not isinstance(gate, dict) or set(gate) != GATE_FIELDS:
                    add_blocker(blockers, "invalid_workflow_gate", "Workflow gate fields are invalid.", field=gate_field)
                    continue
                gate_id = gate.get("id")
                before_stage = gate.get("before_stage")
                if (
                    not isinstance(gate_id, str)
                    or not IDENTIFIER.fullmatch(gate_id)
                    or gate_id in gate_ids
                    or not isinstance(before_stage, str)
                    or before_stage not in stage_ids
                    or gate.get("type") != "human_review"
                    or gate.get("required_decision") != "approved"
                    or gate.get("auto_approval") is not False
                ):
                    add_blocker(
                        blockers,
                        "unsafe_workflow_gate",
                        "Initial gates must require non-automatic human approval before a known stage.",
                        field=gate_field,
                    )
                else:
                    gate_ids.add(gate_id)
                    safely_gated_stages.add(before_stage)
        for stage_id, module_name in stage_modules.items():
            capabilities = set(modules[module_name].get("capabilities", []))
            if capabilities & REVIEW_GATED_CAPABILITIES and stage_id not in safely_gated_stages:
                add_blocker(
                    blockers,
                    "missing_human_review_gate",
                    "Execution-capable stages require an explicit non-automatic human review gate.",
                    field=f"{field}.stages.{stage_id}",
                )
        validate_identifier_list(
            workflow.get("terminal_statuses"), blockers, f"{field}.terminal_statuses"
        )
        if not isinstance(workflow.get("failure_policy"), str) or not IDENTIFIER.fullmatch(
            workflow["failure_policy"]
        ):
            add_blocker(
                blockers,
                "invalid_workflow_failure_policy",
                "Workflow failure policy must be a lower-case identifier.",
                field=f"{field}.failure_policy",
            )
        workflow_modules[name] = dependency_closure(workflow_modules[name], modules)
    return workflow_modules, stage_count


def validate_workflow_membership(
    modules: dict[str, dict[str, Any]],
    workflow_modules: dict[str, set[str]],
    blockers: list[dict[str, str]],
) -> None:
    known_workflows = set(workflow_modules)
    for module_name, module in modules.items():
        declared = set(module.get("workflows", []))
        for workflow_name in declared - known_workflows:
            add_blocker(
                blockers,
                "unknown_module_workflow",
                "Module references an unknown workflow.",
                field=f"modules.{module_name}.workflows.{workflow_name}",
            )
        for workflow_name in declared & known_workflows:
            if module_name not in workflow_modules[workflow_name]:
                add_blocker(
                    blockers,
                    "unused_module_workflow",
                    "Module declares workflow membership but is not used by its dependency closure.",
                    field=f"modules.{module_name}.workflows.{workflow_name}",
                )
    for workflow_name, used_modules in workflow_modules.items():
        for module_name in used_modules:
            if workflow_name not in modules[module_name].get("workflows", []):
                add_blocker(
                    blockers,
                    "missing_module_workflow",
                    "Every module used by a workflow dependency closure must declare that workflow.",
                    field=f"modules.{module_name}.workflows",
                )


def render_report(status: str, modules: int, workflows: int, stages: int, blockers: int) -> str:
    return "\n".join(
        [
            "# Analytics Module Registry Validation Report",
            "",
            f"- Status: `{status}`",
            f"- Modules: {modules}",
            f"- Workflows: {workflows}",
            f"- Stages: {stages}",
            f"- Blockers: {blockers}",
            "",
            "## Boundary",
            "",
            "- Validation inspects declared entrypoint source and signatures without importing or calling them.",
            "- No workflow, query, provider, database, or external operation is executed.",
            "- Dynamic execution, concurrency, network, and review auto-approval remain disabled.",
            "- Registry validity is not data, semantic, relationship, plan, or execution approval.",
        ]
    ) + "\n"


def write_outputs(output_dir: Path, contents: dict[str, str]) -> bool:
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"Module registry validation output is not a directory: {output_dir}")
    existing = (
        {path.name: path for path in output_dir.iterdir() if path.is_file() and path.name in OUTPUT_NAMES}
        if output_dir.exists()
        else {}
    )
    if existing:
        exact = set(existing) == set(contents) and all(
            existing[name].read_text(encoding="utf-8") == content for name, content in contents.items()
        )
        if exact:
            return False
        raise ValueError(
            f"Different module registry evidence already exists in {output_dir}. "
            "Use a new output directory; existing generated evidence was not overwritten."
        )
    ensure_dir(output_dir)
    for name, content in contents.items():
        (output_dir / name).write_text(content, encoding="utf-8", newline="")
    return True


def run_module_registry_validation(
    registry_path: Path,
    output_dir: Path,
    *,
    project_root: Path | None = None,
) -> ModuleRegistryValidationResult:
    blockers: list[dict[str, str]] = []
    project_root = (project_root or Path.cwd()).resolve()
    try:
        registry_hash = file_sha256(registry_path) if registry_path.is_file() else ""
    except OSError:
        registry_hash = ""
        add_blocker(
            blockers,
            "registry_unreadable",
            "The module registry cannot be hashed.",
            field="registry",
        )
    payload = read_registry(registry_path, blockers)
    if set(payload) != {"version", "status", "controls", "modules", "workflows"}:
        add_blocker(
            blockers,
            "invalid_registry_contract",
            "Registry fields are incomplete or unsupported.",
            field="registry",
        )
    if payload.get("version") != 1 or payload.get("status") != "active":
        add_blocker(
            blockers,
            "unsupported_registry_state",
            "Registry must be version 1 and active.",
            field="registry",
        )
    if payload.get("controls") != REQUIRED_CONTROLS:
        add_blocker(
            blockers,
            "unsafe_registry_controls",
            "Dynamic execution, concurrency, network, and review auto-approval must remain disabled.",
            field="controls",
        )
    modules = validate_modules(payload.get("modules"), project_root, blockers)
    workflow_modules, stage_count = validate_workflows(payload.get("workflows"), modules, blockers)
    validate_workflow_membership(modules, workflow_modules, blockers)
    workflow_count = len(workflow_modules)
    try:
        registry_changed = registry_path.is_file() and file_sha256(registry_path) != registry_hash
    except OSError:
        registry_changed = True
    if registry_changed:
        add_blocker(
            blockers,
            "registry_changed_during_validation",
            "The registry changed during validation.",
            field="registry",
        )
    status = "valid" if not blockers else "blocked"
    manifest = {
        "version": 1,
        "status": status,
        "source": {"registry_sha256": registry_hash},
        "counts": {
            "modules": len(modules),
            "workflows": workflow_count,
            "stages": stage_count,
            "blockers": len(blockers),
        },
        "controls": {
            **REQUIRED_CONTROLS,
            "entrypoints_inspected_statically": True,
            "entrypoint_modules_imported": False,
            "entrypoints_called": False,
            "database_access": False,
        },
    }
    contents = {
        MANIFEST_NAME: canonical_yaml(manifest),
        BLOCKERS_NAME: blockers_csv(blockers),
        REPORT_NAME: render_report(status, len(modules), workflow_count, stage_count, len(blockers)),
    }
    outputs_changed = write_outputs(output_dir, contents)
    return ModuleRegistryValidationResult(
        output_dir=output_dir,
        status=status,
        manifest_path=output_dir / MANIFEST_NAME,
        blockers_path=output_dir / BLOCKERS_NAME,
        report_path=output_dir / REPORT_NAME,
        blocker_count=len(blockers),
        module_count=len(modules),
        workflow_count=workflow_count,
        stage_count=stage_count,
        outputs_changed=outputs_changed,
    )
