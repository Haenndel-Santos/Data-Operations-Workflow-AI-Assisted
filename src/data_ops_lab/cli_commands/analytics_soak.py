from __future__ import annotations

import argparse
from pathlib import Path

from ..ollama_provider import (
    DEFAULT_CONTEXT_TOKENS,
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_OLLAMA_ENDPOINT,
    DEFAULT_OLLAMA_MODEL,
)


def register_analytics_soak_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register the separately authorized bounded local Ollama soak command."""

    analytics_ollama_soak = subparsers.add_parser(
        "analytics-ollama-soak",
        help="Preflight or run a separately authorized bounded local Ollama overnight soak.",
    )
    analytics_ollama_soak.add_argument("--dataset-manifest", type=Path, required=True)
    analytics_ollama_soak.add_argument("--database", type=Path, required=True)
    analytics_ollama_soak.add_argument("--semantic-state", type=Path, required=True)
    analytics_ollama_soak.add_argument("--relationships", type=Path, required=True)
    analytics_ollama_soak.add_argument("--pack", type=Path, required=True)
    analytics_ollama_soak.add_argument("--approval", type=Path, required=True)
    analytics_ollama_soak.add_argument("--live-authorization", type=Path, required=True)
    analytics_ollama_soak.add_argument("--soak-authorization", type=Path, required=True)
    analytics_ollama_soak.add_argument("--endpoint", default=DEFAULT_OLLAMA_ENDPOINT)
    analytics_ollama_soak.add_argument("--model", default=DEFAULT_OLLAMA_MODEL)
    analytics_ollama_soak.add_argument(
        "--context-tokens", type=int, default=DEFAULT_CONTEXT_TOKENS
    )
    analytics_ollama_soak.add_argument(
        "--max-output-tokens", type=int, default=DEFAULT_MAX_OUTPUT_TOKENS
    )
    analytics_ollama_soak.add_argument("--timeout-seconds", type=int, default=120)
    analytics_ollama_soak.add_argument("--output", type=Path, required=True)
    analytics_ollama_soak.add_argument(
        "--execute",
        action="store_true",
        help="Run the authorized bounded soak after successful offline preflight.",
    )
    analytics_ollama_soak.add_argument(
        "--allow-network",
        action="store_true",
        help="Authorize literal-loopback Ollama HTTP for this invocation only.",
    )
