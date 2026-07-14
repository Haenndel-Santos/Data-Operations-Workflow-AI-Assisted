from __future__ import annotations

import csv
from pathlib import Path

import pytest
import yaml

from data_ops_lab.cli import build_parser
from data_ops_lab.performance_baseline import run_performance_baseline
from data_ops_lab.performance_worker import STAGES


def read_metrics(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_synthetic_performance_baseline_measures_isolated_stages(tmp_path: Path) -> None:
    result = run_performance_baseline(
        tmp_path / "baseline",
        rows_per_table=500,
        table_count=2,
        stage_timeout_seconds=60,
    )

    assert result.status == "completed"
    assert result.stage_count == len(STAGES)
    assert result.completed_stage_count == len(STAGES)
    assert result.highest_memory_stage in STAGES
    rows = read_metrics(result.metrics_path)
    assert [row["stage"] for row in rows] == list(STAGES)
    assert all(row["status"] == "completed" for row in rows)
    assert all(int(row["peak_process_memory_bytes"]) > 0 for row in rows)
    assert all(int(row["input_bytes"]) > 0 for row in rows)
    assert all(row["input_bytes"] == row["scanned_bytes"] for row in rows)

    manifest_text = result.manifest_path.read_text(encoding="utf-8")
    manifest = yaml.safe_load(manifest_text)
    assert manifest["workload"]["type"] == "generated_synthetic_parquet"
    assert manifest["workload"]["scanned_bytes_method"] == "unique_full_input_footprint"
    assert manifest["controls"]["synthetic_only"] is True
    assert manifest["controls"]["network_access"] is False
    assert manifest["controls"]["input_rows_persisted"] is False
    assert "synthetic-00-" not in manifest_text


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"rows_per_table": 99}, "rows_per_table"),
        ({"table_count": 1}, "table_count"),
        ({"stage_timeout_seconds": 9}, "stage_timeout_seconds"),
    ],
)
def test_performance_baseline_limits_are_bounded(
    tmp_path: Path,
    kwargs: dict[str, int],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        run_performance_baseline(tmp_path / "baseline", **kwargs)


def test_performance_baseline_never_overwrites_existing_evidence(tmp_path: Path) -> None:
    output = tmp_path / "baseline"
    output.mkdir()
    marker = output / "existing.txt"
    marker.write_text("preserve\n", encoding="utf-8")

    with pytest.raises(ValueError, match="new or empty"):
        run_performance_baseline(output, rows_per_table=100, table_count=2)

    assert marker.read_text(encoding="utf-8") == "preserve\n"


def test_performance_baseline_cli_accepts_no_external_input() -> None:
    args = build_parser().parse_args(["pipeline-performance-baseline"])

    assert args.command == "pipeline-performance-baseline"
    assert args.rows_per_table == 50_000
    assert args.table_count == 3
    assert args.input is None
    assert not hasattr(args, "database")
    assert not hasattr(args, "allow_network")
