from pathlib import Path
from tempfile import TemporaryDirectory

from data_ops_lab.workflow import run_workflow


def test_sample_workflow_runs() -> None:
    with TemporaryDirectory() as tmpdir:
        result = run_workflow(Path("samples/raw"), Path(tmpdir) / "demo")

        assert result.database_path.exists()
        assert (result.metadata_dir / "data_profile.json").exists()
        assert (result.metadata_dir / "keys.json").exists()
        assert (result.metadata_dir / "relationship_validation.csv").exists()
        assert (result.tableau_dir / "csv" / "orders.csv").exists()
