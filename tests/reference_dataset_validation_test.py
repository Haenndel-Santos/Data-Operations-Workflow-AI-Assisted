from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from data_ops_lab.benchmark_sql_conversion import run_benchmark_sql_conversion
from data_ops_lab.cli import build_parser
from data_ops_lab.reference_dataset_validation import run_reference_dataset_validation


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sample_sql(*, orphan: bool = False, duplicate_order: bool = False) -> str:
    customer_id = 999 if orphan else 1
    duplicate = (
        f"INSERT Orders VALUES (10, {customer_id}, 7.00)\n" if duplicate_order else ""  # noqa: S608 - fixture T-SQL text parsed by the conversion module, not executed
    )
    return f"""
CREATE TABLE Customers
(
    CustomerID int NOT NULL,
    Name nvarchar(40) NOT NULL,
    CONSTRAINT PK_Customers PRIMARY KEY (CustomerID)
)
GO
CREATE TABLE Orders
(
    OrderID int NOT NULL,
    CustomerID int NULL REFERENCES Customers(CustomerID),
    Amount money NULL,
    CONSTRAINT PK_Orders PRIMARY KEY (OrderID)
)
GO
INSERT Customers VALUES (1, 'Alice')
INSERT Customers VALUES (2, 'Bob')
INSERT Orders VALUES (10, {customer_id}, 12.50)
{duplicate}GO
"""  # noqa: S608 - fixture T-SQL text parsed by the conversion module, not executed


def build_reference_package(
    tmp_path: Path,
    *,
    orphan: bool = False,
    duplicate_order: bool = False,
) -> tuple[Path, Path, Path]:
    source = tmp_path / "sample.sql"
    source.write_text(
        sample_sql(orphan=orphan, duplicate_order=duplicate_order),
        encoding="utf-8",
    )
    current = tmp_path / "derived" / "current"
    reproduction = tmp_path / "derived" / "reproduction"
    current_result = run_benchmark_sql_conversion(source, "sample", current)
    reproduction_result = run_benchmark_sql_conversion(source, "sample", reproduction)
    reference = {
        "version": 1,
        "dataset": "sample",
        "source": {
            "local_path": str(source),
            "bytes": source.stat().st_size,
            "sha256": sha256(source),
            "provenance_status": "verified_exact_official_copy",
            "official": {
                "repository": "example/reference-datasets",
                "path": "samples/sample.sql",
                "commit": "1" * 40,
                "blob_sha": "2" * 40,
                "permalink": "https://example.test/example/reference-datasets/blob/commit/samples/sample.sql",
            },
        },
        "license": {
            "status": "verified",
            "spdx": "MIT",
            "commit": "3" * 40,
            "permalink": "https://example.test/example/reference-datasets/blob/commit/LICENSE",
        },
        "conversion": {
            "manifest_path": str(current_result.manifest_path),
            "manifest_sha256": sha256(current_result.manifest_path),
            "reproduction": {
                "manifest_path": str(reproduction_result.manifest_path),
            },
        },
        "schema": {
            "expected_primary_keys": 2,
            "primary_keys": [
                {
                    "table": "customers",
                    "columns": ["customer_id"],
                    "evidence": "source_declared_primary_key",
                },
                {
                    "table": "orders",
                    "columns": ["order_id"],
                    "evidence": "source_declared_primary_key",
                },
            ],
        },
        "relationships": {"expected_candidates": 1},
        "benchmark_use": {
            "status": "approved",
            "approved_by": "test_reviewer",
            "approved_at": "2026-07-15T10:00:00+02:00",
            "authorization_reference": "test_fixture",
            "scopes": {
                "local_conversion": "approved",
                "local_profiling": "approved",
                "local_benchmark_design": "approved",
                "local_offline_evaluation": "approved",
                "external_upload": "not_authorized",
                "model_parameter_training": "not_authorized",
                "publication": "not_authorized",
            },
        },
    }
    reference_path = tmp_path / "sample.reference.yml"
    reference_path.write_text(
        yaml.safe_dump(reference, sort_keys=False),
        encoding="utf-8",
    )
    return reference_path, current_result.database_path, source


def build_composite_reference_package(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "composite.sql"
    source.write_text(
        """
CREATE TABLE Parents
(
    TenantID int NOT NULL,
    ParentCode nvarchar(20) NOT NULL,
    Name nvarchar(40) NULL,
    CONSTRAINT PK_Parents PRIMARY KEY (TenantID, ParentCode)
)
GO
CREATE TABLE Children
(
    ChildID int NOT NULL,
    TenantID int NULL,
    ParentCode nvarchar(20) NULL,
    CONSTRAINT PK_Children PRIMARY KEY (ChildID),
    CONSTRAINT FK_Children_Parents FOREIGN KEY (TenantID, ParentCode)
        REFERENCES Parents(TenantID, ParentCode)
)
GO
INSERT Parents VALUES (1, 'A', 'Alpha')
INSERT Parents VALUES (2, 'A', 'Beta')
INSERT Children VALUES (10, 1, 'A')
INSERT Children VALUES (11, 2, NULL)
GO
""",
        encoding="utf-8",
    )
    current_result = run_benchmark_sql_conversion(
        source, "composite", tmp_path / "derived" / "current"
    )
    reproduction_result = run_benchmark_sql_conversion(
        source, "composite", tmp_path / "derived" / "reproduction"
    )
    relationship_payload = {
        "version": 2,
        "status": "pending_review",
        "relationship_candidates": [
            {
                "constraint_name": "FK_Children_Parents",
                "source_table": "children",
                "source_columns": ["tenant_id", "parent_code"],
                "target_table": "parents",
                "target_columns": ["tenant_id", "parent_code"],
                "evidence": "source_declared_foreign_key",
                "status": "pending_review",
            }
        ],
    }
    for result in (current_result, reproduction_result):
        result.relationships_path.write_text(
            yaml.safe_dump(relationship_payload, sort_keys=False), encoding="utf-8"
        )
        manifest = yaml.safe_load(result.manifest_path.read_text(encoding="utf-8"))
        manifest["artifacts"]["relationships"]["sha256"] = sha256(
            result.relationships_path
        )
        manifest["counts"]["relationship_candidates"] = 1
        result.manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
        )

    reference = {
        "version": 1,
        "dataset": "composite",
        "source": {
            "local_path": str(source),
            "bytes": source.stat().st_size,
            "sha256": sha256(source),
            "provenance_status": "verified_exact_official_copy",
            "official": {
                "repository": "example/reference-datasets",
                "path": "samples/composite.sql",
                "commit": "1" * 40,
                "blob_sha": "2" * 40,
                "permalink": "https://example.test/example/reference-datasets/blob/commit/samples/composite.sql",
            },
        },
        "license": {
            "status": "verified",
            "spdx": "MIT",
            "commit": "3" * 40,
            "permalink": "https://example.test/example/reference-datasets/blob/commit/LICENSE",
        },
        "conversion": {
            "manifest_path": str(current_result.manifest_path),
            "manifest_sha256": sha256(current_result.manifest_path),
            "reproduction": {
                "manifest_path": str(reproduction_result.manifest_path),
            },
        },
        "schema": {
            "expected_primary_keys": 2,
            "primary_keys": [
                {
                    "table": "parents",
                    "columns": ["tenant_id", "parent_code"],
                    "evidence": "source_declared_primary_key",
                },
                {
                    "table": "children",
                    "columns": ["child_id"],
                    "evidence": "source_declared_primary_key",
                },
            ],
        },
        "relationships": {"expected_candidates": 1},
        "benchmark_use": {
            "status": "approved",
            "approved_by": "test_reviewer",
            "approved_at": "2026-07-22T10:00:00+02:00",
            "authorization_reference": "test_fixture",
            "scopes": {
                "local_conversion": "approved",
                "local_profiling": "approved",
                "local_benchmark_design": "approved",
                "local_offline_evaluation": "approved",
                "external_upload": "not_authorized",
                "model_parameter_training": "not_authorized",
                "publication": "not_authorized",
            },
        },
    }
    reference_path = tmp_path / "composite.reference.yml"
    reference_path.write_text(
        yaml.safe_dump(reference, sort_keys=False), encoding="utf-8"
    )
    return reference_path, current_result.database_path


def test_reference_dataset_validation_profiles_without_approving_relationships(
    tmp_path: Path,
) -> None:
    reference_path, database_path, source_path = build_reference_package(tmp_path)
    output = tmp_path / "validation"
    source_before = source_path.read_bytes()
    database_before = database_path.read_bytes()

    first = run_reference_dataset_validation(reference_path, output)
    second = run_reference_dataset_validation(reference_path, output)

    assert first.status == "ready_for_relationship_review"
    assert first.blocker_count == 0
    assert first.table_count == 2
    assert first.row_count == 3
    assert first.primary_key_count == 2
    assert first.relationship_count == 1
    assert first.approved_relationship_count == 0
    assert first.outputs_changed is True
    assert second.outputs_changed is False
    assert source_path.read_bytes() == source_before
    assert database_path.read_bytes() == database_before

    evidence = yaml.safe_load(first.manifest_path.read_text(encoding="utf-8"))
    assert evidence["conversion"]["reproduction"]["equivalent"] is True
    assert evidence["schema"]["valid_primary_keys"] == 2
    assert evidence["relationships"]["valid_candidates"] == 1
    assert evidence["relationships"]["accepted"] == 0
    assert evidence["safety"]["database_opened_read_only"] is True
    assert evidence["safety"]["relationships_automatically_approved"] is False

    review = yaml.safe_load(first.review_path.read_text(encoding="utf-8"))
    assert review["status"] == "pending_review"
    assert review["decisions"][0]["decision"] == "pending"
    assert review["decisions"][0]["technical_validation"]["orphan_rows"] == 0
    assert review["decisions"][0]["technical_validation"]["positive_coverage"] is True
    relationships = yaml.safe_load(
        first.approved_relationships_path.read_text(encoding="utf-8")
    )
    assert relationships["status"] == "pending_review"
    assert relationships["approved_relationships"] == []
    assert relationships["authority"]["automatic_approval"] is False


def test_reference_dataset_validation_supports_pending_composite_relationships(
    tmp_path: Path,
) -> None:
    reference_path, database_path = build_composite_reference_package(tmp_path)
    database_before = database_path.read_bytes()

    result = run_reference_dataset_validation(reference_path, tmp_path / "validation")

    assert result.status == "ready_for_relationship_review"
    assert result.blocker_count == 0
    assert result.relationship_count == 1
    assert result.approved_relationship_count == 0
    assert database_path.read_bytes() == database_before
    evidence = yaml.safe_load(result.manifest_path.read_text(encoding="utf-8"))
    relationship = evidence["relationships"]["technical_evidence"][0]
    assert relationship["source_columns"] == ["tenant_id", "parent_code"]
    assert relationship["target_columns"] == ["tenant_id", "parent_code"]
    assert relationship["nonnull_source_rows"] == 1
    assert relationship["null_source_rows"] == 1
    assert relationship["orphan_rows"] == 0
    assert relationship["target_duplicate_groups"] == 0
    assert relationship["valid"] is True
    review = yaml.safe_load(result.review_path.read_text(encoding="utf-8"))
    assert review["version"] == 2
    assert review["status"] == "pending_review"
    assert review["decisions"][0]["decision"] == "pending"
    registry = yaml.safe_load(
        result.approved_relationships_path.read_text(encoding="utf-8")
    )
    assert registry["version"] == 2
    assert registry["status"] == "pending_review"
    assert registry["approved_relationships"] == []


def test_completed_composite_review_preserves_constraint_shape(tmp_path: Path) -> None:
    reference_path, _ = build_composite_reference_package(tmp_path)
    pending = run_reference_dataset_validation(reference_path, tmp_path / "pending")
    review = yaml.safe_load(pending.review_path.read_text(encoding="utf-8"))
    review["status"] = "completed"
    review["scope"]["local_offline_relationship_use"] = "approved"
    decision = review["decisions"][0]
    decision["decision"] = "accepted"
    decision["reviewer"] = "synthetic_test_reviewer"
    decision["reviewed_at"] = "2026-07-22T10:30:00+02:00"
    decision["notes"] = "Synthetic completed-review contract coverage."
    completed_review = tmp_path / "completed.yml"
    completed_review.write_text(
        yaml.safe_dump(review, sort_keys=False), encoding="utf-8"
    )

    result = run_reference_dataset_validation(
        reference_path,
        tmp_path / "approved",
        review_path=completed_review,
    )

    assert result.status == "ready_for_semantic_modeling"
    registry = yaml.safe_load(
        result.approved_relationships_path.read_text(encoding="utf-8")
    )
    assert registry["version"] == 2
    assert registry["approved_relationships"] == [
        {
            "constraint_name": "FK_Children_Parents",
            "source_table": "children",
            "source_columns": ["tenant_id", "parent_code"],
            "target_table": "parents",
            "target_columns": ["tenant_id", "parent_code"],
        }
    ]


def test_completed_exact_review_opens_semantic_modeling_gate(tmp_path: Path) -> None:
    reference_path, _, _ = build_reference_package(tmp_path)
    pending = run_reference_dataset_validation(reference_path, tmp_path / "pending")
    review = yaml.safe_load(pending.review_path.read_text(encoding="utf-8"))
    review["status"] = "completed"
    review["scope"]["local_offline_relationship_use"] = "approved"
    for decision in review["decisions"]:
        decision["decision"] = "accepted"
        decision["reviewer"] = "human_reviewer"
        decision["reviewed_at"] = "2026-07-15T10:30:00+02:00"
        decision["notes"] = "Accepted after reviewing source declaration and technical evidence."
    completed_review = tmp_path / "completed_relationship_review.yml"
    completed_review.write_text(
        yaml.safe_dump(review, sort_keys=False),
        encoding="utf-8",
    )

    result = run_reference_dataset_validation(
        reference_path,
        tmp_path / "approved",
        review_path=completed_review,
    )

    assert result.status == "ready_for_semantic_modeling"
    assert result.blocker_count == 0
    assert result.approved_relationship_count == 1
    evidence = yaml.safe_load(result.manifest_path.read_text(encoding="utf-8"))
    assert evidence["relationships"]["review_status"] == "completed"
    assert evidence["relationships"]["accepted"] == 1
    assert evidence["relationships"]["pending"] == 0
    relationships = yaml.safe_load(
        result.approved_relationships_path.read_text(encoding="utf-8")
    )
    assert relationships["status"] == "approved"
    assert relationships["authority"]["completed_review_sha256"] == sha256(
        completed_review
    )
    assert relationships["authority"]["automatic_approval"] is False
    assert relationships["approved_relationships"] == [
        {
            "source_table": "orders",
            "source_column": "customer_id",
            "target_table": "customers",
            "target_column": "customer_id",
        }
    ]


def test_completed_rejection_is_preserved_outside_approved_registry(
    tmp_path: Path,
) -> None:
    reference_path, _, _ = build_reference_package(tmp_path)
    pending = run_reference_dataset_validation(reference_path, tmp_path / "pending")
    review = yaml.safe_load(pending.review_path.read_text(encoding="utf-8"))
    review["status"] = "completed"
    review["scope"]["local_offline_relationship_use"] = "approved"
    decision = review["decisions"][0]
    decision["decision"] = "rejected"
    decision["reviewer"] = "human_reviewer"
    decision["reviewed_at"] = "2026-07-15T10:30:00+02:00"
    decision["notes"] = "Rejected after reviewing the exact candidate."
    completed_review = tmp_path / "rejected_relationship_review.yml"
    completed_review.write_text(
        yaml.safe_dump(review, sort_keys=False),
        encoding="utf-8",
    )

    result = run_reference_dataset_validation(
        reference_path,
        tmp_path / "reviewed",
        review_path=completed_review,
    )

    assert result.status == "ready_for_semantic_modeling"
    assert result.approved_relationship_count == 0
    relationships = yaml.safe_load(
        result.approved_relationships_path.read_text(encoding="utf-8")
    )
    assert relationships["status"] == "approved"
    assert relationships["approved_relationships"] == []
    assert relationships["rejected_relationship_ids"] == [
        "orders.customer_id->customers.customer_id"
    ]


def test_orphan_relationship_blocks_reference_dataset(tmp_path: Path) -> None:
    reference_path, _, _ = build_reference_package(tmp_path, orphan=True)

    result = run_reference_dataset_validation(reference_path, tmp_path / "blocked")

    assert result.status == "blocked"
    evidence = yaml.safe_load(result.manifest_path.read_text(encoding="utf-8"))
    assert any(row["code"] == "invalid_relationship_data" for row in evidence["blockers"])
    relationship = evidence["relationships"]["technical_evidence"][0]
    assert relationship["orphan_rows"] == 1
    assert relationship["valid"] is False


def test_duplicate_declared_primary_key_blocks_reference_dataset(tmp_path: Path) -> None:
    reference_path, _, _ = build_reference_package(tmp_path, duplicate_order=True)

    result = run_reference_dataset_validation(reference_path, tmp_path / "blocked")

    assert result.status == "blocked"
    evidence = yaml.safe_load(result.manifest_path.read_text(encoding="utf-8"))
    assert any(row["code"] == "invalid_primary_key_data" for row in evidence["blockers"])
    orders_key = next(row for row in evidence["schema"]["evidence"] if row["table"] == "orders")
    assert orders_key["duplicate_key_groups"] == 1
    assert orders_key["valid"] is False


def test_unverified_license_blocks_before_database_access(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reference_path, _, _ = build_reference_package(tmp_path)
    reference = yaml.safe_load(reference_path.read_text(encoding="utf-8"))
    reference["license"]["status"] = "pending"
    reference_path.write_text(yaml.safe_dump(reference, sort_keys=False), encoding="utf-8")

    def forbidden_connect(*args: object, **kwargs: object) -> None:
        raise AssertionError("Preflight blocker must prevent DuckDB access.")

    monkeypatch.setattr(
        "data_ops_lab.reference_dataset_validation.duckdb.connect",
        forbidden_connect,
    )
    result = run_reference_dataset_validation(reference_path, tmp_path / "blocked")

    assert result.status == "blocked"
    evidence = yaml.safe_load(result.manifest_path.read_text(encoding="utf-8"))
    assert any(row["code"] == "unverified_license" for row in evidence["blockers"])
    assert evidence["safety"]["database_opened_read_only"] is False


def test_reference_validation_refuses_divergent_existing_evidence(tmp_path: Path) -> None:
    reference_path, _, _ = build_reference_package(tmp_path)
    output = tmp_path / "validation"
    result = run_reference_dataset_validation(reference_path, output)
    result.report_path.write_text("changed\n", encoding="utf-8")

    with pytest.raises(ValueError, match="existing evidence was not overwritten"):
        run_reference_dataset_validation(reference_path, output)


def test_reference_dataset_validation_cli_contract() -> None:
    args = build_parser().parse_args(
        [
            "reference-dataset-validate",
            "--manifest",
            "northwind.reference.yml",
            "--review",
            "northwind.relationship-review.yml",
            "--output",
            "outputs/northwind",
        ]
    )

    assert args.command == "reference-dataset-validate"
    assert args.manifest == Path("northwind.reference.yml")
    assert args.review == Path("northwind.relationship-review.yml")
    assert args.output == Path("outputs/northwind")
