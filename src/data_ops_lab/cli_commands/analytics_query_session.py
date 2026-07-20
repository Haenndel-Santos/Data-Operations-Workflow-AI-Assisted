from __future__ import annotations

import argparse
from pathlib import Path


def register_analytics_query_session_commands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register governed query, presentation, narration, and session commands."""

    analytics_query_plan = subparsers.add_parser(
        "analytics-query-plan",
        help="Compile a structured analytics request into a safe read-only SQL dry-run plan.",
    )
    analytics_query_plan.add_argument(
        "--request",
        type=Path,
        required=True,
        help="Local version-1 structured analytics request YAML.",
    )
    analytics_query_plan.add_argument(
        "--database",
        type=Path,
        required=True,
        help="Local DuckDB database inspected in read-only mode.",
    )
    analytics_query_plan.add_argument(
        "--relationships",
        type=Path,
        default=Path("config/data_model/approved_relationships.yml"),
        help="Human-approved relationship YAML required for cross-table joins.",
    )
    analytics_query_plan.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/analytics_query_plan"),
        help="New or byte-identical directory for local dry-run query-plan artifacts.",
    )

    analytics_query_execute = subparsers.add_parser(
        "analytics-query-execute",
        help="Execute an exact reviewed analytics plan against local DuckDB with hard limits.",
    )
    analytics_query_execute.add_argument("--request", type=Path, required=True)
    analytics_query_execute.add_argument("--database", type=Path, required=True)
    analytics_query_execute.add_argument(
        "--relationships",
        type=Path,
        default=Path("config/data_model/approved_relationships.yml"),
    )
    analytics_query_execute.add_argument("--plan", type=Path, required=True)
    analytics_query_execute.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/analytics_query_execution"),
    )
    analytics_query_execute.add_argument("--max-rows", type=int, default=10_000)
    analytics_query_execute.add_argument(
        "--max-result-bytes", type=int, default=10_000_000
    )
    analytics_query_execute.add_argument(
        "--max-runtime-seconds", type=int, default=30
    )
    analytics_query_execute.add_argument(
        "--memory-limit-mb", type=int, default=512
    )
    analytics_query_execute.add_argument("--threads", type=int, default=2)
    analytics_query_execute.add_argument("--max-temp-mb", type=int, default=1_024)

    analytics_result_present = subparsers.add_parser(
        "analytics-result-present",
        help="Render validated Stage 5B evidence as a bounded deterministic local result.",
    )
    analytics_result_present.add_argument("--request", type=Path, required=True)
    analytics_result_present.add_argument(
        "--execution-manifest", type=Path, required=True
    )
    analytics_result_present.add_argument("--result", type=Path, required=True)
    analytics_result_present.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/analytics_result_presentation"),
    )

    analytics_result_narrate_recorded = subparsers.add_parser(
        "analytics-result-narrate-recorded",
        help="Validate a cited result narrative from an offline recorded response.",
    )
    analytics_result_narrate_recorded.add_argument(
        "--presentation-manifest",
        type=Path,
        required=True,
    )
    analytics_result_narrate_recorded.add_argument(
        "--facts", type=Path, required=True
    )
    analytics_result_narrate_recorded.add_argument(
        "--provider-response",
        type=Path,
        required=True,
    )
    analytics_result_narrate_recorded.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/analytics_result_narration"),
    )
    analytics_result_narrate_recorded.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
    )

    analytics_session_prepare = subparsers.add_parser(
        "analytics-session-prepare-recorded",
        help="Prepare a recorded local analytics session and stop for plan review.",
    )
    analytics_session_prepare.add_argument(
        "--question-file", type=Path, required=True
    )
    analytics_session_prepare.add_argument(
        "--semantic-state", type=Path, required=True
    )
    analytics_session_prepare.add_argument(
        "--translation-response",
        type=Path,
        required=True,
    )
    analytics_session_prepare.add_argument("--database", type=Path, required=True)
    analytics_session_prepare.add_argument(
        "--relationships", type=Path, required=True
    )
    analytics_session_prepare.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/analytics_session_prepare"),
    )

    analytics_session_resume = subparsers.add_parser(
        "analytics-session-resume-recorded",
        help="Resume an exact reviewed session through execution and recorded narration.",
    )
    analytics_session_resume.add_argument(
        "--prepare-manifest", type=Path, required=True
    )
    analytics_session_resume.add_argument("--review", type=Path, required=True)
    analytics_session_resume.add_argument("--database", type=Path, required=True)
    analytics_session_resume.add_argument(
        "--relationships", type=Path, required=True
    )
    analytics_session_resume.add_argument(
        "--narration-response",
        type=Path,
        required=True,
    )
    analytics_session_resume.add_argument(
        "--output",
        type=Path,
        default=Path("outputs/analytics_session_resume"),
    )
