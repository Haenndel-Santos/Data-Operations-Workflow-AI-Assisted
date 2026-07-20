from __future__ import annotations

import argparse
from pathlib import Path

from ..ollama_provider import (
    DEFAULT_CONTEXT_TOKENS,
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_OLLAMA_ENDPOINT,
    DEFAULT_OLLAMA_MODEL,
)


def register_analytics_dataset_benchmark_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register dataset-backed benchmark commands without owning execution."""

    analytics_dataset_benchmark = subparsers.add_parser(
        "analytics-dataset-benchmark-validate",
        help="Validate immutable dataset and benchmark-pack bindings without opening the database.",
    )
    analytics_dataset_benchmark.add_argument(
        "--dataset-manifest", type=Path, required=True
    )
    analytics_dataset_benchmark.add_argument("--database", type=Path, required=True)
    analytics_dataset_benchmark.add_argument(
        "--semantic-state", type=Path, required=True
    )
    analytics_dataset_benchmark.add_argument(
        "--relationships", type=Path, required=True
    )
    analytics_dataset_benchmark.add_argument("--pack", type=Path, required=True)
    analytics_dataset_benchmark.add_argument("--approval", type=Path, required=True)
    analytics_dataset_benchmark.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/analytics_dataset_benchmark_validation"),
    )

    analytics_dataset_benchmark_prepare = subparsers.add_parser(
        "analytics-dataset-benchmark-answer-prepare",
        help="Compile recorded benchmark intents into exact plans and stop for aggregate review.",
    )
    analytics_dataset_benchmark_prepare.add_argument(
        "--design", type=Path, required=True
    )
    analytics_dataset_benchmark_prepare.add_argument(
        "--dataset-manifest", type=Path, required=True
    )
    analytics_dataset_benchmark_prepare.add_argument(
        "--database", type=Path, required=True
    )
    analytics_dataset_benchmark_prepare.add_argument(
        "--semantic-state", type=Path, required=True
    )
    analytics_dataset_benchmark_prepare.add_argument(
        "--relationships", type=Path, required=True
    )
    analytics_dataset_benchmark_prepare.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/analytics_dataset_benchmark_answer_preparation"),
    )

    analytics_dataset_benchmark_materialize = subparsers.add_parser(
        "analytics-dataset-benchmark-answer-materialize",
        help="Execute approved exact plans sequentially and write a candidate expected-answer pack.",
    )
    analytics_dataset_benchmark_materialize.add_argument(
        "--design", type=Path, required=True
    )
    analytics_dataset_benchmark_materialize.add_argument(
        "--dataset-manifest", type=Path, required=True
    )
    analytics_dataset_benchmark_materialize.add_argument(
        "--preparation-manifest", type=Path, required=True
    )
    analytics_dataset_benchmark_materialize.add_argument(
        "--execution-review", type=Path, required=True
    )
    analytics_dataset_benchmark_materialize.add_argument(
        "--database", type=Path, required=True
    )
    analytics_dataset_benchmark_materialize.add_argument(
        "--semantic-state", type=Path, required=True
    )
    analytics_dataset_benchmark_materialize.add_argument(
        "--relationships", type=Path, required=True
    )
    analytics_dataset_benchmark_materialize.add_argument(
        "--pack-output", type=Path, required=True
    )
    analytics_dataset_benchmark_materialize.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/analytics_dataset_benchmark_answer_materialization"),
    )

    analytics_dataset_benchmark_review = subparsers.add_parser(
        "analytics-dataset-benchmark-review",
        help="Prepare a hash-bound pending human review for a dataset benchmark pack.",
    )
    analytics_dataset_benchmark_review.add_argument(
        "--dataset-manifest", type=Path, required=True
    )
    analytics_dataset_benchmark_review.add_argument(
        "--database", type=Path, required=True
    )
    analytics_dataset_benchmark_review.add_argument(
        "--semantic-state", type=Path, required=True
    )
    analytics_dataset_benchmark_review.add_argument(
        "--relationships", type=Path, required=True
    )
    analytics_dataset_benchmark_review.add_argument("--pack", type=Path, required=True)
    analytics_dataset_benchmark_review.add_argument(
        "--output",
        type=Path,
        default=Path(
            "outputs/analytics_dataset_benchmark_review/analytics_dataset_benchmark_review.yml"
        ),
    )

    analytics_dataset_benchmark_approval = subparsers.add_parser(
        "analytics-dataset-benchmark-approval",
        help="Validate and explicitly write a completed dataset benchmark approval.",
    )
    analytics_dataset_benchmark_approval.add_argument(
        "--dataset-manifest", type=Path, required=True
    )
    analytics_dataset_benchmark_approval.add_argument(
        "--database", type=Path, required=True
    )
    analytics_dataset_benchmark_approval.add_argument(
        "--semantic-state", type=Path, required=True
    )
    analytics_dataset_benchmark_approval.add_argument(
        "--relationships", type=Path, required=True
    )
    analytics_dataset_benchmark_approval.add_argument(
        "--pack", type=Path, required=True
    )
    analytics_dataset_benchmark_approval.add_argument(
        "--review", type=Path, required=True
    )
    analytics_dataset_benchmark_approval.add_argument(
        "--approval-output", type=Path, required=True
    )
    analytics_dataset_benchmark_approval.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/analytics_dataset_benchmark_approval"),
    )
    analytics_dataset_benchmark_approval.add_argument("--apply", action="store_true")

    analytics_dataset_benchmark_evaluate = subparsers.add_parser(
        "analytics-dataset-benchmark-evaluate",
        help="Run an approved dataset-backed benchmark through the governed offline pipeline.",
    )
    analytics_dataset_benchmark_evaluate.add_argument(
        "--dataset-manifest", type=Path, required=True
    )
    analytics_dataset_benchmark_evaluate.add_argument(
        "--database", type=Path, required=True
    )
    analytics_dataset_benchmark_evaluate.add_argument(
        "--semantic-state", type=Path, required=True
    )
    analytics_dataset_benchmark_evaluate.add_argument(
        "--relationships", type=Path, required=True
    )
    analytics_dataset_benchmark_evaluate.add_argument(
        "--pack", type=Path, required=True
    )
    analytics_dataset_benchmark_evaluate.add_argument(
        "--approval", type=Path, required=True
    )
    analytics_dataset_benchmark_evaluate.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/analytics_dataset_benchmark_evaluation"),
    )

    analytics_dataset_benchmark_evaluate_ollama = subparsers.add_parser(
        "analytics-dataset-benchmark-evaluate-ollama",
        help="Preflight or execute an explicitly authorized sequential benchmark through loopback Ollama.",
    )
    analytics_dataset_benchmark_evaluate_ollama.add_argument(
        "--dataset-manifest", type=Path, required=True
    )
    analytics_dataset_benchmark_evaluate_ollama.add_argument(
        "--database", type=Path, required=True
    )
    analytics_dataset_benchmark_evaluate_ollama.add_argument(
        "--semantic-state", type=Path, required=True
    )
    analytics_dataset_benchmark_evaluate_ollama.add_argument(
        "--relationships", type=Path, required=True
    )
    analytics_dataset_benchmark_evaluate_ollama.add_argument(
        "--pack", type=Path, required=True
    )
    analytics_dataset_benchmark_evaluate_ollama.add_argument(
        "--approval", type=Path, required=True
    )
    analytics_dataset_benchmark_evaluate_ollama.add_argument(
        "--live-authorization", type=Path, required=True
    )
    analytics_dataset_benchmark_evaluate_ollama.add_argument(
        "--endpoint", default=DEFAULT_OLLAMA_ENDPOINT
    )
    analytics_dataset_benchmark_evaluate_ollama.add_argument(
        "--model", default=DEFAULT_OLLAMA_MODEL
    )
    analytics_dataset_benchmark_evaluate_ollama.add_argument(
        "--context-tokens", type=int, default=DEFAULT_CONTEXT_TOKENS
    )
    analytics_dataset_benchmark_evaluate_ollama.add_argument(
        "--max-output-tokens", type=int, default=DEFAULT_MAX_OUTPUT_TOKENS
    )
    analytics_dataset_benchmark_evaluate_ollama.add_argument(
        "--timeout-seconds", type=int, default=120
    )
    analytics_dataset_benchmark_evaluate_ollama.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/analytics_dataset_benchmark_live_evaluation"),
    )
    analytics_dataset_benchmark_evaluate_ollama.add_argument(
        "--execute",
        action="store_true",
        help="Execute the live comparison after successful preflight; dry-run is the default.",
    )
    analytics_dataset_benchmark_evaluate_ollama.add_argument(
        "--allow-network",
        action="store_true",
        help="Authorize loopback HTTP for this live execution; invalid in dry-run mode.",
    )
