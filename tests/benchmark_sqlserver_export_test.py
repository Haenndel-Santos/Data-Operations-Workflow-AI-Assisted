from __future__ import annotations

import sys
from collections.abc import Iterator, Sequence
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import duckdb
import pyarrow as pa
import pytest
import yaml

from data_ops_lab.benchmark_sqlserver_export import (
    SqlServerColumn,
    SqlServerRelationship,
    SqlServerTable,
    PyodbcSqlServerSource,
    run_benchmark_sqlserver_export,
)
from data_ops_lab.cli import build_parser


def column(
    source_name: str,
    name: str,
    duckdb_type: str,
    arrow_type: pa.DataType,
    *,
    nullable: bool = False,
) -> SqlServerColumn:
    return SqlServerColumn(
        source_name=source_name,
        name=name,
        source_type=duckdb_type.casefold(),
        system_type=duckdb_type.casefold(),
        duckdb_type=duckdb_type,
        arrow_type=arrow_type,
        nullable=nullable,
        identity=False,
        identity_start=None,
        identity_increment=None,
    )


PARENT = SqlServerTable(
    source_schema="Sales",
    source_name="Parent",
    name="sales_parent",
    columns=(
        column("TenantID", "tenant_id", "INTEGER", pa.int32()),
        column("Code", "code", "VARCHAR", pa.string()),
        column("Label", "label", "VARCHAR", pa.string(), nullable=True),
    ),
    primary_key=("tenant_id", "code"),
)
CHILD = SqlServerTable(
    source_schema="Sales",
    source_name="Child",
    name="sales_child",
    columns=(
        column("ChildID", "child_id", "INTEGER", pa.int32()),
        column("TenantID", "tenant_id", "INTEGER", pa.int32(), nullable=True),
        column("ParentCode", "parent_code", "VARCHAR", pa.string(), nullable=True),
        column("Amount", "amount", "DECIMAL(10,2)", pa.decimal128(10, 2)),
    ),
    primary_key=("child_id",),
)
RELATIONSHIP = SqlServerRelationship(
    constraint_name="FK_Child_Parent",
    source_table="sales_child",
    source_columns=("tenant_id", "parent_code"),
    target_table="sales_parent",
    target_columns=("tenant_id", "code"),
)


class FakeSqlServerSource:
    def __init__(self, *, read_only: bool = True) -> None:
        self.read_only = read_only
        self.closed = False
        self.rows = {
            "sales_parent": [(1, "A", "Alpha"), (2, "A", "Beta")],
            "sales_child": [
                (10, 1, "A", Decimal("12.50")),
                (11, 2, None, Decimal("7.25")),
            ],
        }

    def database_evidence(self) -> dict[str, Any]:
        return {
            "server": "localhost",
            "database": "AdventureWorks2025",
            "state": "ONLINE",
            "read_only": self.read_only,
            "compatibility_level": 170,
            "server_edition": "Developer Edition",
            "server_version": "17.0.test",
            "odbc_driver": "ODBC Driver 18 for SQL Server",
            "pyodbc_version": "test-double",
            "integrated_authentication": True,
            "application_intent": "ReadOnly",
        }

    def tables(self) -> list[SqlServerTable]:
        return [CHILD, PARENT]

    def relationships(
        self, tables: Sequence[SqlServerTable]
    ) -> list[SqlServerRelationship]:
        assert tables == [CHILD, PARENT]
        return [RELATIONSHIP]

    def iter_batches(
        self, table: SqlServerTable, batch_size: int
    ) -> Iterator[Sequence[Sequence[Any]]]:
        rows = self.rows[table.name]
        for start in range(0, len(rows), batch_size):
            yield rows[start : start + batch_size]

    def close(self) -> None:
        self.closed = True


def test_sqlserver_export_materializes_reproducible_read_only_outputs(
    tmp_path: Path,
) -> None:
    backup = tmp_path / "AdventureWorks2025.bak"
    backup.write_bytes(b"immutable test backup")
    backup_before = backup.read_bytes()
    current_source = FakeSqlServerSource()
    output = tmp_path / "derived" / "current"

    first = run_benchmark_sqlserver_export(
        backup,
        "AdventureWorks 2025",
        "AdventureWorks2025",
        output,
        batch_size=1,
        execute=True,
        source_factory=lambda _server, _database, _driver: current_source,
    )
    second = run_benchmark_sqlserver_export(
        backup,
        "AdventureWorks 2025",
        "AdventureWorks2025",
        output,
        batch_size=1,
        source_factory=lambda *_args: pytest.fail(
            "An exact existing export must not reconnect to SQL Server."
        ),
    )
    reproduction = run_benchmark_sqlserver_export(
        backup,
        "AdventureWorks 2025",
        "AdventureWorks2025",
        tmp_path / "derived" / "reproduction",
        batch_size=1,
        execute=True,
        source_factory=lambda _server, _database, _driver: FakeSqlServerSource(),
    )

    assert first.status == "ready_for_local_benchmark"
    assert first.table_count == 2
    assert first.row_count == 4
    assert first.relationship_count == 1
    assert first.outputs_changed is True
    assert second.outputs_changed is False
    assert current_source.closed is True
    assert backup.read_bytes() == backup_before

    with duckdb.connect(str(first.database_path), read_only=True) as connection:
        assert connection.execute(
            "select child_id, tenant_id, parent_code, amount from sales_child order by child_id"
        ).fetchall() == [
            (10, 1, "A", Decimal("12.50")),
            (11, 2, None, Decimal("7.25")),
        ]

    manifest = yaml.safe_load(first.manifest_path.read_text(encoding="utf-8"))
    reproduction_manifest = yaml.safe_load(
        reproduction.manifest_path.read_text(encoding="utf-8")
    )
    assert manifest["approval"] == {
        "local_export_approved": True,
        "benchmark_use_approved": False,
        "relationship_candidates_approved": False,
        "model_training_approved": False,
        "external_upload_approved": False,
        "publication_approved": False,
    }
    assert manifest["conversion"]["database_read_only_required"] is True
    assert manifest["conversion"]["integrated_authentication_required"] is True
    assert manifest["artifacts"]["parquet"] == reproduction_manifest["artifacts"][
        "parquet"
    ]
    assert manifest["artifacts"]["relationships"] == reproduction_manifest[
        "artifacts"
    ]["relationships"]
    relationships = yaml.safe_load(first.relationships_path.read_text(encoding="utf-8"))
    assert relationships == {
        "version": 2,
        "status": "pending_review",
        "relationship_candidates": [
            {
                "constraint_name": "FK_Child_Parent",
                "source_table": "sales_child",
                "source_columns": ["tenant_id", "parent_code"],
                "target_table": "sales_parent",
                "target_columns": ["tenant_id", "code"],
                "evidence": "source_declared_foreign_key",
                "status": "pending_review",
            }
        ],
    }
    schema = yaml.safe_load(first.schema_path.read_text(encoding="utf-8"))
    assert schema["status"] == "pending_review"
    assert schema["primary_keys"][0]["status"] == "pending_review"


def test_sqlserver_export_requires_execute_and_read_only_database(tmp_path: Path) -> None:
    backup = tmp_path / "source.bak"
    backup.write_bytes(b"backup")
    factory_called = False

    def forbidden_factory(*_args: str) -> FakeSqlServerSource:
        nonlocal factory_called
        factory_called = True
        return FakeSqlServerSource()

    with pytest.raises(ValueError, match="explicit execute=True"):
        run_benchmark_sqlserver_export(
            backup,
            "sample",
            "AdventureWorks2025",
            tmp_path / "not-authorized",
            source_factory=forbidden_factory,
        )
    assert factory_called is False

    writable_source = FakeSqlServerSource(read_only=False)
    output = tmp_path / "writable"
    with pytest.raises(ValueError, match="not READ_ONLY"):
        run_benchmark_sqlserver_export(
            backup,
            "sample",
            "AdventureWorks2025",
            output,
            execute=True,
            source_factory=lambda *_args: writable_source,
        )
    assert writable_source.closed is True
    assert not output.exists()
    assert not output.with_name("writable.building").exists()


def test_sqlserver_export_rejects_unsafe_connection_and_contract_drift(
    tmp_path: Path,
) -> None:
    backup = tmp_path / "source.bak"
    backup.write_bytes(b"backup")
    output = tmp_path / "current"

    with pytest.raises(ValueError, match="local default instance"):
        run_benchmark_sqlserver_export(
            backup,
            "sample",
            "AdventureWorks2025",
            output,
            server="remote.example.test",
        )
    with pytest.raises(ValueError, match="explicitly allowed"):
        run_benchmark_sqlserver_export(
            backup,
            "sample",
            "AdventureWorks2025",
            output,
            driver="ODBC Driver 18 for SQL Server};PWD=unsafe",
        )

    run_benchmark_sqlserver_export(
        backup,
        "sample",
        "AdventureWorks2025",
        output,
        batch_size=1,
        execute=True,
        source_factory=lambda *_args: FakeSqlServerSource(),
    )
    with pytest.raises(ValueError, match="existing derived data was not overwritten"):
        run_benchmark_sqlserver_export(
            backup,
            "sample",
            "AdventureWorks2025",
            output,
            batch_size=2,
        )

    manifest_path = output / "conversion_manifest.yml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["report"] = {
        "path": "../source.bak",
        "sha256": "0" * 64,
    }
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    with pytest.raises(ValueError, match="escapes its output directory"):
        run_benchmark_sqlserver_export(
            backup,
            "sample",
            "AdventureWorks2025",
            output,
            batch_size=1,
        )


def test_sqlserver_export_rejects_invalid_composite_relationship(tmp_path: Path) -> None:
    backup = tmp_path / "source.bak"
    backup.write_bytes(b"backup")
    source = FakeSqlServerSource()
    invalid = replace(RELATIONSHIP, target_columns=("tenant_id",))
    source.relationships = lambda _tables: [invalid]  # type: ignore[method-assign]

    with pytest.raises(ValueError, match="invalid column cardinality"):
        run_benchmark_sqlserver_export(
            backup,
            "sample",
            "AdventureWorks2025",
            tmp_path / "invalid",
            execute=True,
            source_factory=lambda *_args: source,
        )
    assert source.closed is True
    assert not (tmp_path / "invalid").exists()


def test_sqlserver_export_cli_contract() -> None:
    args = build_parser().parse_args(
        [
            "benchmark-export-sqlserver",
            "--source-backup",
            "AdventureWorks2025.bak",
            "--dataset",
            "adventureworks_2025",
            "--database",
            "AdventureWorks2025",
            "--batch-size",
            "5000",
            "--output",
            "derived/adventureworks",
            "--execute",
        ]
    )

    assert args.command == "benchmark-export-sqlserver"
    assert args.source_backup == Path("AdventureWorks2025.bak")
    assert args.database == "AdventureWorks2025"
    assert args.server == "localhost"
    assert args.driver == "ODBC Driver 18 for SQL Server"
    assert args.batch_size == 5000
    assert args.execute is True


def test_pyodbc_source_sets_advisory_read_only_mode_before_connect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, Any] = {}

    class Cursor:
        def execute(self, query: str) -> None:
            calls["query"] = query

        def close(self) -> None:
            calls["cursor_closed"] = True

    class Connection:
        def cursor(self) -> Cursor:
            return Cursor()

        def rollback(self) -> None:
            calls["rolled_back"] = True

        def close(self) -> None:
            calls["connection_closed"] = True

    def connect(connection_string: str, **kwargs: Any) -> Connection:
        calls["connection_string"] = connection_string
        calls["kwargs"] = kwargs
        return Connection()

    fake_pyodbc = SimpleNamespace(
        SQL_ATTR_ACCESS_MODE=101,
        Error=RuntimeError,
        version="test",
        connect=connect,
    )
    monkeypatch.setitem(sys.modules, "pyodbc", fake_pyodbc)

    source = PyodbcSqlServerSource(
        "localhost", "AdventureWorks2025", "ODBC Driver 18 for SQL Server"
    )
    source.close()

    assert calls["kwargs"] == {
        "autocommit": False,
        "attrs_before": {101: 1},
        "timeout": 10,
    }
    assert "ApplicationIntent=ReadOnly" in calls["connection_string"]
    assert calls["query"] == "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"
    assert calls["rolled_back"] is True
    assert calls["connection_closed"] is True
