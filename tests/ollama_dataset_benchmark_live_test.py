from __future__ import annotations

import os
from pathlib import Path

import pytest

from data_ops_lab.analytics_dataset_benchmark_live_evaluation import (
    run_analytics_dataset_benchmark_live_evaluation,
    sample_local_resources,
)
from data_ops_lab.ollama_provider import OllamaSemanticIntentProvider


PROJECT_ROOT = Path(__file__).resolve().parents[1]
pytestmark = [
    pytest.mark.live_provider,
    pytest.mark.skipif(
        os.environ.get("DATA_OPS_LAB_RUN_OLLAMA_BENCHMARK_LIVE") != "1",
        reason="Set DATA_OPS_LAB_RUN_OLLAMA_BENCHMARK_LIVE=1 for the approved 13-case local Ollama benchmark.",
    ),
]


def test_local_ollama_runs_the_authorized_northwind_benchmark(tmp_path: Path) -> None:
    result = run_analytics_dataset_benchmark_live_evaluation(
        PROJECT_ROOT / "datasets" / "benchmarks" / "manifests" / "northwind.dataset-benchmark.yml",
        PROJECT_ROOT / "datasets" / "benchmarks" / "derived" / "northwind" / "northwind.duckdb",
        PROJECT_ROOT / "config" / "analytics" / "approved_semantic_catalog.yml",
        PROJECT_ROOT / "outputs" / "benchmarks" / "northwind-phase2-reviewed" / "approved_relationships.yml",
        PROJECT_ROOT / "datasets" / "benchmarks" / "manifests" / "northwind.answer-benchmark-pack.yml",
        PROJECT_ROOT / "datasets" / "benchmarks" / "manifests" / "northwind.answer-benchmark-approval.yml",
        PROJECT_ROOT / "datasets" / "benchmarks" / "manifests" / "northwind.live-model-evaluation-authorization-v3.yml",
        tmp_path / "live_evaluation",
        OllamaSemanticIntentProvider(),
        timeout_seconds=120,
        execute=True,
        allow_network=True,
        resource_sampler=sample_local_resources,
    )

    assert result.status in {"passed", "failed"}
    assert result.case_count == 13
    assert 1 <= result.provider_call_count <= 13
    assert result.blocker_count == 0
