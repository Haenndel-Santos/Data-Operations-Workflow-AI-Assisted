from __future__ import annotations

import os
from pathlib import Path

import pytest

from data_ops_lab.analytics_nl_translation import run_analytics_nl_translation
from data_ops_lab.ollama_provider import OllamaSemanticIntentProvider


PROJECT_ROOT = Path(__file__).resolve().parents[1]
pytestmark = [
    pytest.mark.live_provider,
    pytest.mark.skipif(
        os.environ.get("DATA_OPS_LAB_RUN_OLLAMA_LIVE") != "1",
        reason="Set DATA_OPS_LAB_RUN_OLLAMA_LIVE=1 for the isolated local Ollama smoke test.",
    ),
]


def test_local_ollama_translates_one_exact_northwind_question(tmp_path: Path) -> None:
    question_path = tmp_path / "question.txt"
    question_path.write_text(
        "Show order count by order ship-to country.\n",
        encoding="utf-8",
    )
    result = run_analytics_nl_translation(
        question_path,
        PROJECT_ROOT / "config" / "analytics" / "approved_semantic_catalog.yml",
        tmp_path / "translation",
        OllamaSemanticIntentProvider(),
        timeout_seconds=120,
        allow_network=True,
    )

    assert result.provider_called is True
    assert result.status == "ready_for_query_plan"
    assert result.blocker_count == 0
    assert result.clarification_count == 0
    assert result.adapter_result is not None
    assert result.adapter_result.request_path is not None
