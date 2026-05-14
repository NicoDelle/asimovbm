import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAPER_ROOT = ROOT / "paper"
NOTEBOOK_ROOT = PAPER_ROOT / "notebooks"
SURVEY_ROOT = PAPER_ROOT / "data" / "human-survey"


def notebook_sources(path: Path) -> str:
    notebook = json.loads(path.read_text())
    return "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook.get("cells", [])
    )


def test_paper_notebooks_exist() -> None:
    assert (NOTEBOOK_ROOT / "survey_results.ipynb").is_file()
    assert (NOTEBOOK_ROOT / "simulation_results.ipynb").is_file()
    assert (NOTEBOOK_ROOT / "paper_results.ipynb").is_file()


def test_human_survey_assets_exist_and_have_rows() -> None:
    csv_path = SURVEY_ROOT / "raw-responses.csv"
    output_root = SURVEY_ROOT / "analysis_outputs"

    assert csv_path.is_file()
    assert output_root.is_dir()
    assert sorted(path.name for path in output_root.glob("*.csv")) == [
        "bootstrap_results.csv",
        "condition_summaries.csv",
        "distribution_counts.csv",
        "distribution_percent.csv",
        "global_summary.csv",
        "paired_results.csv",
        "survey_long.csv",
    ]

    with csv_path.open(newline="") as handle:
        rows = list(csv.reader(handle))

    assert len(rows) > 1


def test_notebooks_use_current_paper_paths() -> None:
    survey_sources = notebook_sources(NOTEBOOK_ROOT / "survey_results.ipynb")
    paper_sources = notebook_sources(NOTEBOOK_ROOT / "paper_results.ipynb")
    simulation_sources = notebook_sources(NOTEBOOK_ROOT / "simulation_results.ipynb")

    for sources in [survey_sources, paper_sources]:
        assert "raw-responses.csv" in sources
        assert "Path(\"survey_results\")" not in sources
        assert "Human-Robot Interaction Evaluation" not in sources

    assert "artifacts" in simulation_sources
    assert "local-validation" in simulation_sources
