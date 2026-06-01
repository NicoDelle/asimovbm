import csv
import json
from pathlib import Path


PAPER_DIR = Path(__file__).resolve().parents[1] / "paper"
NOTEBOOK_DIR = PAPER_DIR / "notebooks"
SURVEY_DIR = PAPER_DIR / "data" / "human-survey"
REMOVED_PATH_TOKENS = [
    "project" "_root",
    "PROJECT" "_ROOT",
    "find_" "project" "_root",
    "project" "_path",
    "/home/",
]


def notebook_sources(path: Path) -> str:
    notebook = json.loads(path.read_text())
    return "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook.get("cells", [])
    )


def notebook_text(path: Path) -> str:
    return path.read_text()


def test_paper_notebooks_exist() -> None:
    assert (NOTEBOOK_DIR / "survey_results.ipynb").is_file()
    assert (NOTEBOOK_DIR / "simulation_results.ipynb").is_file()
    assert (NOTEBOOK_DIR / "paper_results.ipynb").is_file()


def test_human_survey_assets_exist_and_have_rows() -> None:
    csv_path = SURVEY_DIR / "raw-responses.csv"
    output_dir = SURVEY_DIR / "analysis_outputs"

    assert csv_path.is_file()
    assert output_dir.is_dir()
    assert sorted(path.name for path in output_dir.glob("*.csv")) == [
        "bootstrap_results.csv",
        "condition_summaries.csv",
        "distribution_counts.csv",
        "distribution_percent.csv",
        "global_summary.csv",
        "heldout_calibration_comparison.csv",
        "heldout_calibration_spiderplot_ci.csv",
        "heldout_policy_metric_table.csv",
        "heldout_policy_spiderplot.csv",
        "heldout_policy_spiderplot_human_ci.csv",
        "paired_results.csv",
        "survey_long.csv",
    ]
    assert (output_dir / "heldout_calibration_comparison.png").is_file()
    assert (output_dir / "heldout_calibration_spiderplot_ci.png").is_file()
    assert (output_dir / "heldout_policy_metric_table.tex").is_file()
    assert (output_dir / "heldout_policy_spiderplot.png").is_file()
    assert (output_dir / "heldout_policy_spiderplot_human_ci.png").is_file()

    with csv_path.open(newline="") as handle:
        rows = list(csv.reader(handle))

    assert len(rows) > 1


def test_notebooks_use_current_paper_paths() -> None:
    survey_sources = notebook_sources(NOTEBOOK_DIR / "survey_results.ipynb")
    paper_sources = notebook_sources(NOTEBOOK_DIR / "paper_results.ipynb")
    simulation_sources = notebook_sources(NOTEBOOK_DIR / "simulation_results.ipynb")

    assert "raw-responses.csv" in survey_sources
    assert "raw-responses2.csv" in paper_sources

    for sources in [survey_sources, paper_sources]:
        assert "Path(\"survey_results\")" not in sources
        assert "Human-Robot Interaction Evaluation" not in sources

    for path in NOTEBOOK_DIR.rglob("*.ipynb"):
        content = notebook_text(path)
        for token in REMOVED_PATH_TOKENS:
            assert token not in content

    assert "artifacts" in simulation_sources
    assert "local-validation" in simulation_sources
    assert "Held-out Calibration Figure" in paper_sources
    assert "Paper-ready Spiderplot With 95% Confidence Intervals" in paper_sources
    assert "Paper-ready Policy Spiderplot" in paper_sources
    assert "Paper-ready Policy Spiderplot With Human Confidence Intervals" in paper_sources
    assert "survey_validation_summary.merge" in paper_sources
    assert "PAPER_SPIDERPLOT_R_MIN = 25" in paper_sources
    assert "POLICY_SPIDERPLOT_FONT" in paper_sources
    assert "POLICY_SPIDERPLOT_HUMAN_CI_PATH" in paper_sources
    assert "POLICY_HUMAN_CI_LEVEL = 95" in paper_sources
    assert "POLICY_SPIDERPLOT_HUMAN_CI_R_MIN = 20" in paper_sources
    assert "POLICY_METRIC_TABLE_CSV_PATH" in paper_sources
    assert "POLICY_METRIC_TABLE_CI_LEVEL = 95" in paper_sources
