from pathlib import Path

from scripts.check_internal_links import iter_document_links, target_exists


def test_document_links_ignore_local_benchmark_artifacts(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("[missing](missing.md)\n", encoding="utf-8")

    raw = tmp_path / "datasets" / "benchmarks" / "raw" / "sample"
    raw.mkdir(parents=True)
    (raw / "source.md").write_text("[sql_identifier]\n", encoding="utf-8")

    links = list(iter_document_links(tmp_path))

    assert links == [(docs / "guide.md", "missing.md")]
    assert target_exists(*links[0]) is False
