from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAPER_DIR = PROJECT_ROOT / "paper"
DATA_DIR = PAPER_DIR / "data" / "human-survey"
RESULTS_DIR = PAPER_DIR / "results"
ASSETS_DIR = PAPER_DIR / "assets"

SURVEY_PATH = DATA_DIR / "responses.csv"
POLICY_METRIC_TABLE_PATH = RESULTS_DIR / "policy_metric_table.csv"

RANDOM_SEED = 20260514
CALIBRATION_TUNING_N = 50
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 0

Q_MAPPING = {
    "q1": {"policy": "A", "pov": "first_person", "condition_label": "Policy A - first person"},
    "q2": {"policy": "B", "pov": "first_person", "condition_label": "Policy B - first person"},
    "q3": {"policy": "A", "pov": "third_person", "condition_label": "Policy A - third person"},
    "q4": {"policy": "B", "pov": "third_person", "condition_label": "Policy B - third person"},
}

SURVEY_QUESTION_AXIS = {
    "1": "competence_control",
    "2": "safety",
    "3": "awareness",
    "4": "positive_impression",
}

AXES = ["competence_control", "safety", "awareness", "positive_impression"]
AXIS_LABELS = {
    "competence_control": "Dexterity",
    "safety": "Safety",
    "awareness": "Social\nAware.",
    "positive_impression": "Impression",
}

POLICY_A_COLOR = "#174A7E"
POLICY_B_COLOR = "#B45F06"
TIE_COLOR = "#B9B9B9"
DOT_EDGE = "#1D1D1D"


def convert_answer_to_number(answer: object) -> float:
    answer_text = str(answer)
    for score_text, score_number in {
        "-3": -3,
        "-2": -2,
        "-1": -1,
        "0": 0,
        "+1": 1,
        "+2": 2,
        "+3": 3,
    }.items():
        if answer_text.startswith(score_text):
            return float(score_number)
    return np.nan


def load_survey_long() -> pd.DataFrame:
    raw_survey = pd.read_csv(SURVEY_PATH)

    rename_columns = {}
    for old_column_name in raw_survey.columns:
        if old_column_name == "Timestamp":
            rename_columns[old_column_name] = "timestamp"
        elif old_column_name.startswith("Background / Familiarity"):
            rename_columns[old_column_name] = "robotics_familiarity"
        elif old_column_name.startswith("Q"):
            question_code = old_column_name.split(" ", 1)[0]
            rename_columns[old_column_name] = question_code.lower().replace(".", "_")

    survey_wide = raw_survey.rename(columns=rename_columns).copy()
    survey_wide.insert(0, "participant_id", np.arange(1, len(survey_wide) + 1))

    score_columns = [
        column for column in survey_wide.columns if re.fullmatch(r"q[1-4]_[1-4]", column)
    ]
    for column in score_columns:
        survey_wide[column] = survey_wide[column].apply(convert_answer_to_number)

    survey_rows = []
    for condition, metadata in Q_MAPPING.items():
        for question_number, axis in SURVEY_QUESTION_AXIS.items():
            column = f"{condition}_{question_number}"
            if column not in survey_wide.columns:
                continue

            for _, row in survey_wide.iterrows():
                survey_rows.append(
                    {
                        "participant_id": row["participant_id"],
                        "condition": condition,
                        "condition_label": metadata["condition_label"],
                        "policy": metadata["policy"],
                        "pov": metadata["pov"],
                        "axis": axis,
                        "score": row[column],
                    }
                )

    survey_long = pd.DataFrame(survey_rows)
    survey_long["score_norm"] = (survey_long["score"].astype(float) + 3.0) / 6.0
    return survey_long


def validation_subset(survey_long: pd.DataFrame) -> pd.DataFrame:
    participant_ids = np.array(sorted(survey_long["participant_id"].dropna().unique()))
    rng = np.random.default_rng(RANDOM_SEED)
    rng.shuffle(participant_ids)
    validation_participants = set(participant_ids[CALIBRATION_TUNING_N:])
    return survey_long[survey_long["participant_id"].isin(validation_participants)].copy()


def paired_bootstrap_ci(diff_0_100: np.ndarray) -> tuple[float, float, float]:
    values = np.asarray(diff_0_100, dtype=float)
    values = values[~np.isnan(values)]
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    boot = np.empty(BOOTSTRAP_RESAMPLES)
    for index in range(BOOTSTRAP_RESAMPLES):
        boot[index] = rng.choice(values, size=len(values), replace=True).mean()
    ci_low, ci_high = np.quantile(boot, [0.025, 0.975])
    return float(values.mean()), float(ci_low), float(ci_high)


def paired_axis_differences(
    survey_validation_long: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    plotted_rows = []
    participant_rows = []

    for axis in AXES:
        axis_frame = survey_validation_long[survey_validation_long["axis"] == axis]
        paired = (
            axis_frame.pivot_table(index="participant_id", columns="policy", values="score_norm")
            .dropna(subset=["A", "B"])
            .copy()
        )
        diff_0_100 = (paired["A"] - paired["B"]).to_numpy(dtype=float) * 100.0
        mean, ci_low, ci_high = paired_bootstrap_ci(diff_0_100)
        a_wins = int(np.sum(diff_0_100 > 0))
        ties = int(np.sum(np.isclose(diff_0_100, 0.0)))
        b_wins = int(np.sum(diff_0_100 < 0))

        plotted_rows.append(
            {
                "axis": axis,
                "axis_label": AXIS_LABELS[axis].replace("\n", " "),
                "n_participants": len(diff_0_100),
                "mean_diff_A_minus_B": mean / 100.0,
                "std_diff_A_minus_B": float(np.std(diff_0_100 / 100.0, ddof=1)),
                "p_value_two_sided": float(
                    stats.ttest_1samp(diff_0_100 / 100.0, popmean=0.0).pvalue
                ),
                "mean_diff_A_minus_B_0_100": mean,
                "ci_low_0_100": ci_low,
                "ci_high_0_100": ci_high,
                "a_wins": a_wins,
                "ties": ties,
                "b_wins": b_wins,
                "stable_95ci": bool((ci_low > 0 and ci_high > 0) or (ci_low < 0 and ci_high < 0)),
            }
        )

        for participant_id, value in zip(paired.index.to_numpy(), diff_0_100, strict=True):
            participant_rows.append(
                {
                    "participant_id": participant_id,
                    "axis": axis,
                    "axis_label": AXIS_LABELS[axis].replace("\n", " "),
                    "diff_A_minus_B_0_100": value,
                    "preference": "A" if value > 0 else "B" if value < 0 else "tie",
                }
            )

    plotted = pd.DataFrame(plotted_rows)
    participants = pd.DataFrame(participant_rows)
    return plotted, participants


def verify_against_paper_table(plotted: pd.DataFrame) -> None:
    metric_table = pd.read_csv(POLICY_METRIC_TABLE_PATH)
    metric_table = metric_table[metric_table["axis"].isin(AXES)]
    paper_delta = metric_table.set_index("axis")["Human Delta A-B"]

    for _, row in plotted.iterrows():
        paper_value = float(paper_delta.loc[row["axis"]])
        if abs(round(row["mean_diff_A_minus_B_0_100"], 1) - paper_value) > 0.11:
            raise ValueError(
                f"{row['axis']} mean {row['mean_diff_A_minus_B_0_100']:.3f} "
                f"does not match paper table value {paper_value:.3f}."
            )


def add_value_label(ax: plt.Axes, x: float, y: float) -> None:
    label = f"{x:+.1f}"
    if x >= 0:
        text_x = x + 2.5
        ha = "left"
    else:
        text_x = x - 2.5
        ha = "right"
    ax.text(
        text_x,
        y + 0.22,
        label,
        ha=ha,
        va="bottom",
        fontsize=6.4,
        color="#111111",
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.88, "pad": 0.35},
        zorder=8,
    )


def plot_preference_spine(plotted: pd.DataFrame, participants: pd.DataFrame) -> None:
    rng = np.random.default_rng(RANDOM_SEED + 71)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    plotted = plotted.set_index("axis").loc[AXES].reset_index()
    participants = participants[participants["axis"].isin(AXES)].copy()

    y_positions = np.arange(len(AXES))[::-1]
    axis_to_y = dict(zip(AXES, y_positions, strict=True))
    values_by_axis = [
        participants.loc[participants["axis"] == axis, "diff_A_minus_B_0_100"].to_numpy(dtype=float)
        for axis in AXES
    ]

    try:
        for font_path in Path("/usr/share/fonts/truetype/croscore").glob("Tinos*.ttf"):
            from matplotlib import font_manager

            font_manager.fontManager.addfont(font_path)
    except Exception:
        pass

    with plt.rc_context(
        {
            "font.family": "Tinos",
            "font.serif": ["Tinos", "Times New Roman", "Liberation Serif", "serif"],
            "mathtext.fontset": "dejavuserif",
            "font.size": 7.0,
            "axes.labelsize": 7.0,
            "xtick.labelsize": 6.5,
            "ytick.labelsize": 7.1,
        }
    ):
        fig, (ax, ax_strip) = plt.subplots(
            1,
            2,
            figsize=(3.35, 2.35),
            gridspec_kw={"width_ratios": [4.0, 1.05], "wspace": 0.05},
        )

        violin = ax.violinplot(
            values_by_axis,
            positions=y_positions,
            vert=False,
            widths=0.58,
            showmeans=False,
            showmedians=False,
            showextrema=False,
        )
        for body in violin["bodies"]:
            body.set_facecolor("#D8D8D8")
            body.set_edgecolor("none")
            body.set_alpha(0.32)
            body.set_zorder(1)

        for axis in AXES:
            axis_participants = participants[participants["axis"] == axis]
            y_base = axis_to_y[axis]
            jitter = rng.uniform(-0.16, 0.16, size=len(axis_participants))
            colors = axis_participants["preference"].map(
                {"A": POLICY_A_COLOR, "B": POLICY_B_COLOR, "tie": TIE_COLOR}
            )
            ax.scatter(
                axis_participants["diff_A_minus_B_0_100"],
                np.full(len(axis_participants), y_base) + jitter,
                s=8.5,
                c=colors,
                alpha=0.34,
                linewidths=0,
                zorder=3,
            )

        ax.axvline(0, color="#2B2B2B", linewidth=0.85, linestyle="--", alpha=0.9, zorder=2)

        for _, row in plotted.iterrows():
            y = axis_to_y[row["axis"]]
            mean = row["mean_diff_A_minus_B_0_100"]
            ci_low = row["ci_low_0_100"]
            ci_high = row["ci_high_0_100"]
            color = POLICY_A_COLOR if row["stable_95ci"] and mean > 0 else "#202020"
            ax.errorbar(
                mean,
                y,
                xerr=[[mean - ci_low], [ci_high - mean]],
                fmt="o",
                color=color,
                ecolor="#303030",
                elinewidth=1.25,
                capsize=3.0,
                markersize=4.8,
                markeredgecolor=DOT_EDGE,
                markeredgewidth=0.35,
                zorder=6,
            )
            add_value_label(ax, mean, y)

        ax.set_yticks(y_positions)
        ax.set_yticklabels([AXIS_LABELS[axis] for axis in AXES])
        ax.set_xlabel("Policy A - Policy B (0-100 points)")
        ax.set_xlim(-75, 85)
        ax.set_xticks([-60, -30, 0, 30, 60])
        ax.set_ylim(-0.55, len(AXES) - 0.45)
        ax.grid(axis="x", alpha=0.20, linewidth=0.8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#222222")
        ax.spines["bottom"].set_color("#222222")
        ax.tick_params(axis="y", length=0)

        ax.text(
            -73,
            len(AXES) - 0.23,
            "B favored",
            ha="left",
            va="bottom",
            fontsize=6.3,
            color=POLICY_B_COLOR,
        )
        ax.text(
            83,
            len(AXES) - 0.23,
            "A favored",
            ha="right",
            va="bottom",
            fontsize=6.3,
            color=POLICY_A_COLOR,
        )

        ax_strip.set_xlim(0, 1)
        ax_strip.set_ylim(ax.get_ylim())
        ax_strip.set_xticks([])
        ax_strip.set_yticks([])
        for spine in ax_strip.spines.values():
            spine.set_visible(False)

        for _, row in plotted.iterrows():
            y = axis_to_y[row["axis"]]
            n = row["n_participants"]
            b_width = row["b_wins"] / n
            tie_width = row["ties"] / n
            a_width = row["a_wins"] / n
            left = 0.0
            for width, color in [
                (b_width, POLICY_B_COLOR),
                (tie_width, TIE_COLOR),
                (a_width, POLICY_A_COLOR),
            ]:
                ax_strip.barh(
                    y,
                    width,
                    left=left,
                    height=0.28,
                    color=color,
                    edgecolor="white",
                    linewidth=0.35,
                    alpha=0.95,
                )
                left += width
            ax_strip.text(
                0.5,
                y + 0.25,
                f"{int(row['b_wins'])}/{int(row['ties'])}/{int(row['a_wins'])}",
                ha="center",
                va="bottom",
                fontsize=5.8,
                color="#1A1A1A",
            )

        ax_strip.text(0.5, len(AXES) - 0.18, "B/T/A", ha="center", va="bottom", fontsize=6.1)

        fig.subplots_adjust(left=0.215, right=0.995, bottom=0.205, top=0.875, wspace=0.06)

        fig.savefig(
            ASSETS_DIR / "fig3_paired_policy_ratings.pdf",
            metadata={"CreationDate": None, "ModDate": None},
        )

        plt.close(fig)


def main() -> None:
    survey_long = load_survey_long()
    survey_validation_long = validation_subset(survey_long)
    plotted, participants = paired_axis_differences(survey_validation_long)
    verify_against_paper_table(plotted)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    plotted.to_csv(RESULTS_DIR / "paired_policy_ratings.csv", index=False)
    participants.to_csv(RESULTS_DIR / "paired_policy_ratings_participants.csv", index=False)
    plot_preference_spine(plotted, participants)

    print(plotted.to_string(index=False))
    print(f"Saved Figure 3 to {ASSETS_DIR / 'fig3_paired_policy_ratings.pdf'}")


if __name__ == "__main__":
    main()
