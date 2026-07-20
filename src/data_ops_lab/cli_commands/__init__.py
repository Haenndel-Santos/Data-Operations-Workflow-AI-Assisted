"""Domain-grouped CLI command registration."""

from .analytics_dataset_benchmark import (
    register_analytics_dataset_benchmark_commands,
)
from .analytics_query_session import register_analytics_query_session_commands
from .analytics_semantic import register_analytics_semantic_commands
from .erp_modeling import register_erp_modeling_commands
from .model_documentation import register_model_documentation_commands
from .product_publication import register_product_publication_commands
from .product_reference import register_product_reference_commands
from .reference_dataset import register_reference_dataset_commands

__all__ = [
    "register_analytics_dataset_benchmark_commands",
    "register_analytics_query_session_commands",
    "register_analytics_semantic_commands",
    "register_erp_modeling_commands",
    "register_model_documentation_commands",
    "register_product_publication_commands",
    "register_product_reference_commands",
    "register_reference_dataset_commands",
]
