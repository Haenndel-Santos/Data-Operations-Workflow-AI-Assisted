from __future__ import annotations

import argparse
from pathlib import Path

from ..ollama_provider import (
    DEFAULT_CONTEXT_TOKENS,
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_OLLAMA_ENDPOINT,
    DEFAULT_OLLAMA_MODEL,
)


def register_analytics_semantic_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register semantic, translation, and offline evaluation commands."""

    analytics_semantic_catalog = subparsers.add_parser(
        "analytics-semantic-catalog",
        help="Validate business terms, measures, dimensions, and approved relationship paths.",
    )
    analytics_semantic_catalog.add_argument("--catalog", type=Path, required=True)
    analytics_semantic_catalog.add_argument("--database", type=Path, required=True)
    analytics_semantic_catalog.add_argument(
        "--relationships",
        type=Path,
        default=Path("config/data_model/approved_relationships.yml"),
    )
    analytics_semantic_catalog.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/analytics_semantic_catalog"),
    )

    analytics_semantic_review = subparsers.add_parser(
        "analytics-semantic-review",
        help="Prepare a hash-bound pending human review for a compiled semantic catalog.",
    )
    analytics_semantic_review.add_argument("--catalog", type=Path, required=True)
    analytics_semantic_review.add_argument(
        "--output",
        type=Path,
        default=Path(
            "outputs/analytics_semantic_review/analytics_semantic_review.yml"
        ),
    )

    analytics_semantic_approval = subparsers.add_parser(
        "analytics-semantic-approval",
        help="Validate and explicitly apply a completed human semantic review.",
    )
    analytics_semantic_approval.add_argument("--catalog", type=Path, required=True)
    analytics_semantic_approval.add_argument("--review", type=Path, required=True)
    analytics_semantic_approval.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/analytics_semantic_approval"),
    )
    analytics_semantic_approval.add_argument(
        "--config",
        type=Path,
        default=Path("config/analytics"),
    )
    analytics_semantic_approval.add_argument("--apply", action="store_true")
    analytics_semantic_approval.add_argument(
        "--replace-existing", action="store_true"
    )

    analytics_semantic_adapter = subparsers.add_parser(
        "analytics-semantic-adapter",
        help="Compile structured semantic intent into a governed Stage 5A analytics request.",
    )
    analytics_semantic_adapter.add_argument("--intent", type=Path, required=True)
    analytics_semantic_adapter.add_argument(
        "--semantic-state",
        type=Path,
        default=Path("config/analytics/approved_semantic_catalog.yml"),
    )
    analytics_semantic_adapter.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/analytics_semantic_adapter"),
    )

    analytics_nl_translate_recorded = subparsers.add_parser(
        "analytics-nl-translate-recorded",
        help="Translate a local question through an offline recorded provider response.",
    )
    analytics_nl_translate_recorded.add_argument(
        "--question-file",
        type=Path,
        required=True,
    )
    analytics_nl_translate_recorded.add_argument(
        "--semantic-state",
        type=Path,
        default=Path("config/analytics/approved_semantic_catalog.yml"),
    )
    analytics_nl_translate_recorded.add_argument(
        "--provider-response",
        type=Path,
        required=True,
    )
    analytics_nl_translate_recorded.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/analytics_nl_translation"),
    )
    analytics_nl_translate_recorded.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
    )

    analytics_nl_translate_ollama = subparsers.add_parser(
        "analytics-nl-translate-ollama",
        help="Translate an English local question through an explicitly authorized loopback Ollama model.",
    )
    analytics_nl_translate_ollama.add_argument(
        "--question-file", type=Path, required=True
    )
    analytics_nl_translate_ollama.add_argument(
        "--semantic-state",
        type=Path,
        default=Path("config/analytics/approved_semantic_catalog.yml"),
    )
    analytics_nl_translate_ollama.add_argument(
        "--endpoint",
        default=DEFAULT_OLLAMA_ENDPOINT,
    )
    analytics_nl_translate_ollama.add_argument(
        "--model",
        default=DEFAULT_OLLAMA_MODEL,
    )
    analytics_nl_translate_ollama.add_argument(
        "--context-tokens",
        type=int,
        default=DEFAULT_CONTEXT_TOKENS,
    )
    analytics_nl_translate_ollama.add_argument(
        "--max-output-tokens",
        type=int,
        default=DEFAULT_MAX_OUTPUT_TOKENS,
    )
    analytics_nl_translate_ollama.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/analytics_nl_translation_ollama"),
    )
    analytics_nl_translate_ollama.add_argument(
        "--timeout-seconds", type=int, default=120
    )
    analytics_nl_translate_ollama.add_argument(
        "--allow-network",
        action="store_true",
        help="Authorize this invocation to use loopback HTTP for the local Ollama provider.",
    )

    analytics_translation_evaluate = subparsers.add_parser(
        "analytics-translation-evaluate",
        help="Evaluate the translation boundary with a synthetic offline regression pack.",
    )
    analytics_translation_evaluate.add_argument(
        "--pack",
        type=Path,
        required=True,
    )
    analytics_translation_evaluate.add_argument(
        "--semantic-state",
        type=Path,
        required=True,
    )
    analytics_translation_evaluate.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/analytics_translation_evaluation"),
    )

    analytics_answer_evaluate = subparsers.add_parser(
        "analytics-answer-evaluate",
        help="Run a synthetic offline expected-answer evaluation through Stages 5D, 5A, and 5B.",
    )
    analytics_answer_evaluate.add_argument(
        "--pack",
        type=Path,
        required=True,
    )
    analytics_answer_evaluate.add_argument(
        "--semantic-state",
        type=Path,
        required=True,
    )
    analytics_answer_evaluate.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/analytics_answer_evaluation"),
    )
