from __future__ import annotations

from pathlib import Path

import duckdb
import yaml

from data_ops_lab.benchmark_sql_conversion import run_benchmark_sql_conversion
from data_ops_lab.cli import build_parser


SAMPLE_SQL = """
DROP DATABASE production_name
GO

CREATE TABLE [dbo].[Customers]
(
    [CustomerID] [int] IDENTITY(1,1) NOT NULL,
    [Customer Name] [nvarchar](40) NOT NULL,
    [CreatedAt] [datetime] NULL,
    CONSTRAINT [PK_Customers] PRIMARY KEY CLUSTERED ([CustomerID])
)
GO

CREATE TABLE [dbo].[Orders]
(
    [OrderID] [int] NOT NULL,
    [CustomerID] [int] NULL REFERENCES [dbo].[Customers]([CustomerID]),
    [Amount] [money] NULL
)
GO

INSERT Customers VALUES ('Alice', '01/02/2024')
INSERT Customers VALUES ('Bob', '02/03/2024')
GO
INSERT Orders VALUES (10, 1, $12.50)
INSERT Orders VALUES (11, 2, $7.25)
GO

CREATE VIEW UnsafeView AS SELECT * FROM Orders
GO
"""


def test_benchmark_sql_conversion_materializes_safe_normalized_outputs(tmp_path: Path) -> None:
    source_path = tmp_path / "sample.sql"
    output_dir = tmp_path / "derived" / "sample"
    source_path.write_text(SAMPLE_SQL, encoding="utf-8")
    source_bytes = source_path.read_bytes()

    first = run_benchmark_sql_conversion(source_path, "Sample Dataset", output_dir)
    second = run_benchmark_sql_conversion(source_path, "Sample Dataset", output_dir)

    assert first.status == "ready_for_local_benchmark"
    assert first.table_count == 2
    assert first.row_count == 4
    assert first.relationship_count == 1
    assert first.outputs_changed is True
    assert second.outputs_changed is False
    assert source_path.read_bytes() == source_bytes
    assert sorted(path.name for path in (output_dir / "parquet").glob("*.parquet")) == [
        "customers.parquet",
        "orders.parquet",
    ]

    with duckdb.connect(str(first.database_path), read_only=True) as connection:
        customers = connection.execute(
            "select customer_id, customer_name, created_at from customers order by customer_id"
        ).fetchall()
        orders = connection.execute(
            "select order_id, customer_id, amount from orders order by order_id"
        ).fetchall()
    assert [row[:2] for row in customers] == [(1, "Alice"), (2, "Bob")]
    assert str(customers[0][2]).startswith("2024-01-02")
    assert [(row[0], row[1], str(row[2])) for row in orders] == [
        (10, 1, "12.5000"),
        (11, 2, "7.2500"),
    ]

    manifest = yaml.safe_load(first.manifest_path.read_text(encoding="utf-8"))
    assert manifest["dataset"] == "sample_dataset"
    assert manifest["conversion"]["converter_version"] == 1
    assert manifest["conversion"]["ignored_statement_classes"] == [
        "drop",
        "alter_execution",
        "view",
        "procedure",
        "trigger",
        "credential",
        "external_operation",
    ]
    assert manifest["approval"]["model_training_approved"] is False
    assert manifest["counts"] == {
        "tables": 2,
        "rows": 4,
        "relationship_candidates": 1,
    }
    relationships = yaml.safe_load(first.relationships_path.read_text(encoding="utf-8"))
    assert relationships["relationship_candidates"] == [
        {
            "source_table": "orders",
            "source_column": "customer_id",
            "target_table": "customers",
            "target_column": "customer_id",
            "evidence": "source_declared_foreign_key",
            "status": "pending_review",
        }
    ]


def test_benchmark_sql_conversion_generates_listed_identity_columns(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "identities.sql"
    output_dir = tmp_path / "derived" / "identities"
    source_path.write_text(
        """
CREATE TABLE Items (ItemID int IDENTITY(10,2), Name nvarchar(20))
GO
INSERT Items (ItemID, Name) VALUES (20, 'explicit')
INSERT Items (Name) VALUES ('generated')
GO
""",
        encoding="utf-8",
    )

    result = run_benchmark_sql_conversion(source_path, "identities", output_dir)

    with duckdb.connect(str(result.database_path), read_only=True) as connection:
        rows = connection.execute(
            "select item_id, name from items order by item_id"
        ).fetchall()
    assert rows == [(20, "explicit"), (22, "generated")]


def test_benchmark_sql_conversion_cleans_partial_output_on_failure(tmp_path: Path) -> None:
    source_path = tmp_path / "broken.sql"
    output_dir = tmp_path / "derived" / "broken"
    source_path.write_text(
        "CREATE TABLE Known (id int)\nGO\nINSERT Missing VALUES (1)\nGO\n",
        encoding="utf-8",
    )

    try:
        run_benchmark_sql_conversion(source_path, "broken", output_dir)
    except ValueError as error:
        assert "unknown table" in str(error)
    else:
        raise AssertionError("Unknown INSERT targets must fail closed.")

    assert not output_dir.exists()
    assert not output_dir.with_name("broken.building").exists()


def test_benchmark_sql_conversion_refuses_changed_source_in_existing_output(
    tmp_path: Path,
) -> None:
    source_path = tmp_path / "sample.sql"
    output_dir = tmp_path / "derived" / "sample"
    source_path.write_text(SAMPLE_SQL, encoding="utf-8")
    run_benchmark_sql_conversion(source_path, "sample", output_dir)
    source_path.write_text(SAMPLE_SQL.replace("Alice", "Changed"), encoding="utf-8")

    try:
        run_benchmark_sql_conversion(source_path, "sample", output_dir)
    except ValueError as error:
        assert "existing derived data was not overwritten" in str(error)
    else:
        raise AssertionError("Changed sources must not overwrite an existing conversion.")


def test_benchmark_sql_conversion_cli_contract() -> None:
    args = build_parser().parse_args(
        [
            "benchmark-convert-sql",
            "--source",
            "sample.sql",
            "--dataset",
            "sample",
            "--output",
            "derived/sample",
        ]
    )

    assert args.command == "benchmark-convert-sql"
    assert args.source == Path("sample.sql")
    assert args.dataset == "sample"
    assert args.output == Path("derived/sample")
