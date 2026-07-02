from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .cleaner import clean_parquet_directory
from .converter import convert_directory
from .documentation import write_data_dictionary, write_relationship_validation, write_sql_suggestions
from .exporter import export_for_tableau
from .profiler import profile_parquet_directory
from .schema import write_schema_outputs
from .sql_assistant import generate_starter_queries
from .validator import create_duckdb_database, validate_relationships


@dataclass(frozen=True)
class WorkflowResult:
    output_dir: Path
    database_path: Path
    tables: list[str]
    metadata_dir: Path
    tableau_dir: Path


def run_workflow(input_dir: Path, output_dir: Path) -> WorkflowResult:
    staging_dir = output_dir / "01_converted"
    cleaned_dir = output_dir / "02_cleaned"
    metadata_dir = output_dir / "metadata"
    tableau_dir = output_dir / "tableau"
    database_path = output_dir / "duckdb" / "operations_lab.duckdb"

    converted = convert_directory(input_dir, staging_dir)
    profiles = profile_parquet_directory(staging_dir / "parquet", metadata_dir)
    clean_parquet_directory(staging_dir / "parquet", cleaned_dir)
    schema, keys = write_schema_outputs(cleaned_dir, metadata_dir)
    relationship_results = validate_relationships(cleaned_dir, keys)
    queries = generate_starter_queries(schema, keys)
    create_duckdb_database(cleaned_dir, database_path)
    export_for_tableau(cleaned_dir, tableau_dir)

    write_relationship_validation(relationship_results, metadata_dir)
    write_sql_suggestions(queries, metadata_dir)
    write_data_dictionary(schema, profiles, keys, metadata_dir)

    return WorkflowResult(
        output_dir=output_dir,
        database_path=database_path,
        tables=[table.table_name for table in converted],
        metadata_dir=metadata_dir,
        tableau_dir=tableau_dir,
    )
