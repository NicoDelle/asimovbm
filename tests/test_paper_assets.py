import csv
import hashlib
import json
from pathlib import Path

from tools.plot_local_validation_metrics import build_visualizations

PAPER_DIR = Path(__file__).resolve().parents[1] / "paper"
REPO_ROOT = PAPER_DIR.parent
ANALYSIS_DIR = PAPER_DIR / "analysis"
ASSET_DIR = PAPER_DIR / "assets"
RESULTS_DIR = PAPER_DIR / "results"
SURVEY_PATH = PAPER_DIR / "data" / "human-survey" / "responses.csv"
FINAL_PDF_SHA256 = "c98bfdd149aaaacaf4671512ce483574b472216c849e2466e01029059eae0c10"
SURVEY_SHA256 = "31898f4545a19c2a90467a450c33b5266d4b0c4d64607ee8c6de59e206292a31"


def notebook_sources(path: Path) -> str:
    notebook = json.loads(path.read_text())
    return "\n".join("".join(cell.get("source", [])) for cell in notebook.get("cells", []))


def test_final_paper_and_figure_assets_exist() -> None:
    final_pdf = PAPER_DIR / "AsimovBM_ICRA2026.pdf"
    assert final_pdf.read_bytes().startswith(b"%PDF")
    assert final_pdf.stat().st_size > 1_000_000
    assert hashlib.sha256(final_pdf.read_bytes()).hexdigest() == FINAL_PDF_SHA256

    assert sorted(path.name for path in ASSET_DIR.iterdir()) == [
        "fig1_benchmark_overview.pdf",
        "fig1_benchmark_overview.svg",
        "fig2_metric_weight_matrix.pdf",
        "fig3_paired_policy_ratings.pdf",
        "fig4_profile_alignment.pdf",
        "fig5_first_person.png",
        "fig5_third_person.png",
        "fig6_robot_experience.pdf",
    ]
    for figure_name in (
        "fig2_metric_weight_matrix.pdf",
        "fig3_paired_policy_ratings.pdf",
        "fig4_profile_alignment.pdf",
        "fig6_robot_experience.pdf",
    ):
        assert b"/CreationDate" not in (ASSET_DIR / figure_name).read_bytes()


def test_survey_data_is_final_and_deidentified() -> None:
    assert hashlib.sha256(SURVEY_PATH.read_bytes()).hexdigest() == SURVEY_SHA256
    with SURVEY_PATH.open(newline="") as handle:
        rows = list(csv.reader(handle))

    assert len(rows) == 121
    assert "Timestamp" not in rows[0]
    assert len(rows[0]) == 17


def test_paper_analysis_has_only_supported_entrypoints() -> None:
    assert sorted(path.name for path in ANALYSIS_DIR.iterdir() if path.is_file()) == [
        "generate_metric_weight_matrix.py",
        "generate_paired_policy_ratings.py",
        "generate_profile_alignment.py",
        "generate_robot_experience.py",
        "paper_results.ipynb",
        "reproduce_pov_statistics.py",
        "simulation_results.ipynb",
    ]

    for notebook in ANALYSIS_DIR.glob("*.ipynb"):
        parsed_notebook = json.loads(notebook.read_text())
        sources = notebook_sources(notebook)
        assert "responses.csv" in sources or notebook.name == "simulation_results.ipynb"
        assert "raw-responses" not in sources
        assert "/home/" not in sources
        for cell_index, cell in enumerate(parsed_notebook.get("cells", [])):
            if cell.get("cell_type") == "code":
                compile("".join(cell.get("source", [])), f"{notebook}:cell-{cell_index}", "exec")


def test_published_results_match_final_paper() -> None:
    expected_results = {
        "metric_weight_matrix.csv",
        "paired_policy_ratings.csv",
        "paired_policy_ratings_participants.csv",
        "policy_metric_table.csv",
        "pov_direct_effects.csv",
        "pov_policy_separation.csv",
        "pov_policy_specific_effects.csv",
        "profile_alignment.csv",
        "robot_experience_axis_effects.csv",
        "robot_experience_dataset_audit.csv",
        "robot_experience_mean_scores.csv",
        "robot_experience_policy_effects.csv",
    }
    assert {path.name for path in RESULTS_DIR.iterdir()} == expected_results

    with (RESULTS_DIR / "policy_metric_table.csv").open(newline="") as handle:
        metric_rows = {row["Metric"]: row for row in csv.DictReader(handle)}
    assert metric_rows["AsimovBM"]["Delta_%"] == "91.6"

    with (RESULTS_DIR / "paired_policy_ratings.csv").open(newline="") as handle:
        paired_rows = {row["axis"]: row for row in csv.DictReader(handle)}
    assert paired_rows["competence_control"]["n_participants"] == "70"
    assert round(float(paired_rows["competence_control"]["mean_diff_A_minus_B"]), 3) == 0.177

    with (RESULTS_DIR / "robot_experience_axis_effects.csv").open(newline="") as handle:
        experience_rows = {row["axis"]: row for row in csv.DictReader(handle)}
    overall = experience_rows["overall"]
    assert round(float(overall["daily_minus_no_contact"]), 1) == -9.0
    assert int(overall["n_daily_contact"]) == 23
    assert int(overall["n_no_daily_contact"]) == 95


def test_stale_paper_artifacts_are_absent() -> None:
    obsolete_paths = [
        PAPER_DIR / "paper.tex",
        PAPER_DIR / "paper.pdf",
        PAPER_DIR / "paper_backup.tex",
        PAPER_DIR / "poster.tex",
        PAPER_DIR / "poster.pdf",
        PAPER_DIR / "notebooks",
        PAPER_DIR / "data" / "human-survey" / "raw-responses.csv",
        PAPER_DIR / "data" / "human-survey" / "raw-responses2.csv",
        PAPER_DIR / "data" / "human-survey" / "analysis_outputs",
    ]
    assert not [path for path in obsolete_paths if path.exists()]


def test_curated_validation_artifacts_have_no_local_machine_paths() -> None:
    validation_root = REPO_ROOT / "artifacts" / "local-validation"
    text_artifacts = [
        path for path in validation_root.rglob("*") if path.suffix in {".csv", ".html", ".json"}
    ]
    leaking = [
        path.relative_to(REPO_ROOT)
        for path in text_artifacts
        if "/home/" in path.read_text(errors="replace")
    ]
    assert not leaking


def test_validation_dashboard_regenerates_with_portable_paths(tmp_path: Path) -> None:
    validation_root = REPO_ROOT / "artifacts" / "local-validation"
    build_visualizations(validation_root, tmp_path)

    with (tmp_path / "condition_summary.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 12
    assert all(not Path(row["run_dir"]).is_absolute() for row in rows)
    assert all(not Path(row["selected_csv"]).is_absolute() for row in rows)
    assert not (tmp_path / "data_warnings.txt").exists()
