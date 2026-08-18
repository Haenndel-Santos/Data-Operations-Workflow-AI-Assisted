"""Architecture test for the Customer Data Boundary network rule.

The product promise is that customer data does not leave infrastructure the
customer controls. Deployment-level egress denial is a separate future control;
this test enforces the part the application can prove today: only explicitly
sanctioned modules may reach the network at all.

It fails when a new network-capable import appears outside the allowlist, and
it also fails when an allowlist entry goes stale, so the allowlist cannot grow
into a list of things that used to be true.

See docs/customer-data-boundary.md and docs/security-architecture.md.
"""

from __future__ import annotations

import ast
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[1] / "src" / "data_ops_lab"

# Top-level module names whose presence means a component can open a connection.
# urllib.parse is deliberately absent: it only manipulates strings.
NETWORK_CAPABLE_ROOTS = frozenset(
    {
        "aiohttp",
        "asyncio",
        "boto3",
        "ftplib",
        "http",
        "httpx",
        "imaplib",
        "paramiko",
        "poplib",
        "pyodbc",
        "requests",
        "smtplib",
        "socket",
        "socketserver",
        "ssl",
        "telnetlib",
        "urllib3",
        "webbrowser",
        "websockets",
        "xmlrpc",
    }
)

NON_NETWORK_SUBMODULES = frozenset({"urllib.parse"})

# Every entry needs a reason, and the reason has to describe a boundary that
# some other control actually enforces.
ALLOWED_NETWORK_MODULES: dict[str, str] = {
    "ollama_provider.py": (
        "Sole model-provider egress point. validate_loopback_endpoint pins the "
        "endpoint to 127.0.0.1 or ::1 over http with no credentials, no path, "
        "and no query, and the opener disables proxies."
    ),
    "benchmark_sqlserver_export.py": (
        "Local read-only SQL Server bridge for authorized public benchmark "
        "export. Connector use is per-invocation and separately authorized; it "
        "is not a production dependency."
    ),
}


def _module_key(path: Path) -> str:
    return path.relative_to(SOURCE_ROOT).as_posix()


def _is_network_capable(dotted_name: str) -> bool:
    if dotted_name in NON_NETWORK_SUBMODULES:
        return False
    return dotted_name.split(".")[0] in NETWORK_CAPABLE_ROOTS


def _network_imports(tree: ast.AST) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_network_capable(alias.name):
                    found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            # Relative imports stay inside the package and cannot reach the network.
            if node.level == 0 and node.module and _is_network_capable(node.module):
                found.add(node.module)
    return found


def _dynamic_network_imports(tree: ast.AST) -> set[str]:
    """Catch importlib.import_module("socket") and __import__("requests")."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        target = node.func
        name = ""
        if isinstance(target, ast.Attribute) and target.attr == "import_module":
            name = "import_module"
        elif isinstance(target, ast.Name) and target.id == "__import__":
            name = "__import__"
        if not name:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            if _is_network_capable(first.value):
                found.add(f"{name}({first.value!r})")
    return found


def _scan() -> dict[str, set[str]]:
    observed: dict[str, set[str]] = {}
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        hits = _network_imports(tree) | _dynamic_network_imports(tree)
        if hits:
            observed[_module_key(path)] = hits
    return observed


def test_network_access_stays_inside_the_allowlist() -> None:
    unexpected = {
        module: sorted(hits)
        for module, hits in _scan().items()
        if module not in ALLOWED_NETWORK_MODULES
    }
    assert not unexpected, (
        "New network-capable code appeared outside the Customer Data Boundary "
        f"allowlist: {unexpected}. Either remove the dependency or add the "
        "module to ALLOWED_NETWORK_MODULES with a reason describing the "
        "boundary that keeps it safe. See docs/customer-data-boundary.md."
    )


def test_allowlist_has_no_stale_entries() -> None:
    observed = _scan()
    stale = sorted(set(ALLOWED_NETWORK_MODULES) - set(observed))
    assert not stale, (
        f"These modules no longer reach the network: {stale}. Remove them from "
        "ALLOWED_NETWORK_MODULES so the allowlist keeps describing the real "
        "egress surface."
    )


def test_every_allowlist_entry_states_a_reason() -> None:
    missing = sorted(
        module
        for module, reason in ALLOWED_NETWORK_MODULES.items()
        if len(reason.strip()) < 40
    )
    assert not missing, (
        f"These allowlist entries need a real justification: {missing}. An "
        "entry without a stated boundary is an undocumented egress path."
    )


def test_provider_module_pins_the_endpoint_to_loopback() -> None:
    source = (SOURCE_ROOT / "ollama_provider.py").read_text(encoding="utf-8")
    assert "def validate_loopback_endpoint" in source
    assert 'LOOPBACK_HOSTS = {"127.0.0.1", "::1"}' in source
    assert "ProxyHandler({})" in source, (
        "The provider opener must disable proxies so a configured system proxy "
        "cannot turn a loopback call into external egress."
    )
