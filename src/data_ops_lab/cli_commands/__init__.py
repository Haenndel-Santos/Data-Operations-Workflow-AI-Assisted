"""Domain-grouped CLI command registration."""

from .analytics_dataset_benchmark import (
    register_analytics_dataset_benchmark_commands,
)
from .analytics_query_session import register_analytics_query_session_commands
from .analytics_semantic import register_analytics_semantic_commands
from .erp_modeling import register_erp_modeling_commands
from .reference_dataset import register_reference_dataset_commands

__all__ = [
    "register_analytics_dataset_benchmark_commands",
    "register_analytics_query_session_commands",
    "register_analytics_semantic_commands",
    "register_erp_modeling_commands",
    "register_reference_dataset_commands",
]
