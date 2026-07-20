from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from pathlib import Path


BLOCKER_FUNCTIONS = {"add_blocker", "_add_blocker"}


def _literal_strings(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, ast.IfExp):
        return _literal_strings(node.body) | _literal_strings(node.orelse)
    return set()


def _call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def inventory(root: Path) -> tuple[dict[str, set[str]], list[str]]:
    labels: dict[str, set[str]] = defaultdict(set)
    dynamic_calls: list[str] = []

    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root.parent.parent)
        relative_label = relative.as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative_label)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or _call_name(node) not in BLOCKER_FUNCTIONS:
                continue
            if len(node.args) < 2:
                dynamic_calls.append(f"{relative_label}:{node.lineno}")
                continue
            values = _literal_strings(node.args[1])
            if not values:
                dynamic_calls.append(f"{relative_label}:{node.lineno}")
                continue
            location = f"{relative_label}:{node.lineno}"
            for value in values:
                labels[value].add(location)

    return dict(labels), dynamic_calls


def inventory_direct_blocker_reuses(root: Path) -> list[str]:
    reuses: list[str] = []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root.parent.parent).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if not any(
                isinstance(target, ast.Name) and target.id == "blockers"
                for target in node.targets
            ):
                continue
            value = node.value
            if (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id == "list"
                and len(value.args) == 1
                and isinstance(value.args[0], ast.Attribute)
                and value.args[0].attr == "blockers"
            ):
                reuses.append(f"{relative}:{node.lineno}")
    return reuses


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inventory literal persisted blocker labels without importing project modules."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("src/data_ops_lab"),
        help="Python source tree to inspect (default: src/data_ops_lab)",
    )
    args = parser.parse_args()
    labels, dynamic_calls = inventory(args.source)
    direct_reuses = inventory_direct_blocker_reuses(args.source)

    print("label\tlocations")
    for label in sorted(labels):
        print(f"{label}\t{','.join(sorted(labels[label]))}")
    print(f"\nLiteral labels: {len(labels)}")
    print(f"Dynamic call sites: {len(dynamic_calls)}")
    for location in dynamic_calls:
        print(f"DYNAMIC\t{location}")
    print(f"Direct blocker-record reuses: {len(direct_reuses)}")
    for location in direct_reuses:
        print(f"DIRECT_REUSE\t{location}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
