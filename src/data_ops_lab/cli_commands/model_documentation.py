from __future__ import annotations

import argparse
from pathlib import Path


def register_model_documentation_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register conceptual schema and business-flow documentation commands."""

    schema_overview = subparsers.add_parser(
        "schema-overview",
        help="Generate conceptual main database schema overview documentation and SQL.",
    )
    schema_overview.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/schema_overview"),
        help="Directory for conceptual schema overview outputs.",
    )

    business_flow_mapping = subparsers.add_parser(
        "business-flow-mapping",
        help="Register confirmed business-flow mapping as pending validation config and documentation.",
    )
    business_flow_mapping.add_argument(
        "--config",
        type=Path,
        default=Path("config/data_model"),
        help="Data model config directory. Approved files are not modified.",
    )
    business_flow_mapping.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/originaldatabase_analysis/schema_overview"),
        help="Directory for business-flow mapping outputs.",
    )
