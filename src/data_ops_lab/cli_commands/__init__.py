"""Domain-grouped CLI command registration."""

from .analytics_dataset_benchmark import (
    register_analytics_dataset_benchmark_commands,
)

__all__ = ["register_analytics_dataset_benchmark_commands"]
