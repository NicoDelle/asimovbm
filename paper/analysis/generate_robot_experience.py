from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAPER_DIR = PROJECT_ROOT / "paper"
DATA_DIR = PAPER_DIR / "data" / "human-survey"
SURVEY_PATH = DATA_DIR / "responses.csv"
RESULTS_DIR = PAPER_DIR / "results"
ASSETS_DIR = PAPER_DIR / "assets"

RANDOM_SEED = 20260514
BOOTSTRAP_SEED = RANDOM_SEED + 1000
BOOTSTRAP_RESAMPLES = 10_000

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
    "awareness": "Social Awareness",
    "positive_impression": "Impression",
}
POLICY_LABELS = {
    "A": "Policy A",
    "B": "Policy B",
    "All": "Participant mean across Policies A and B",
}
GROUP_LABELS = {
    False: "No daily robot contact",
    True: "Daily robot contact",
}
NO_CONTACT = "No daily robot contact"
DAILY_CONTACT = "Daily robot contact"
GROUP_COLORS = {
    NO_CONTACT: "#1f6f8b",
    DAILY_CONTACT: "#c85a3d",
}


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


def familiarity_to_boolean(answer: object) -> object:
    answer_text = str(answer)
    if answer_text == "True" or answer_text.startswith("Daily interaction"):
        return True
    if answer_text == "False" or answer_text.startswith("No daily contact"):
        return False
    return pd.NA


def load_survey_long(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_survey = pd.read_csv(path)

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

    survey_wide["robotics_familiarity"] = (
        survey_wide["robotics_familiarity"].apply(familiarity_to_boolean).astype("boolean")
    )

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
                        "robotics_familiarity": row["robotics_familiarity"],
                        "condition": condition,
                        "condition_label": metadata["condition_label"],
                        "policy": metadata["policy"],
                        "pov": metadata["pov"],
                        "axis": axis,
                        "score": row[column],
                    }
                )

    survey_long = pd.DataFrame(survey_rows)
    return survey_wide, survey_long


def prepare_analysis_scores(
    survey_long: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    answers = survey_long[survey_long["axis"].isin(AXES)].copy()
    answers = answers.dropna(subset=["robotics_familiarity"])
    answers["score_0_100"] = (answers["score"].astype(float) + 3.0) / 6.0 * 100.0
    answers["experience_group"] = answers["robotics_familiarity"].map(GROUP_LABELS)

    participant_policy_axis = answers.groupby(
        ["participant_id", "experience_group", "policy", "axis"], as_index=False
    ).agg(score_0_100=("score_0_100", "mean"))

    participant_combined_axis = participant_policy_axis.groupby(
        ["participant_id", "experience_group", "axis"], as_index=False
    ).agg(score_0_100=("score_0_100", "mean"))
    participant_combined_axis["policy"] = "All"

    analysis_scores = pd.concat(
        [participant_policy_axis, participant_combined_axis], ignore_index=True
    )
    analysis_scores["policy_label"] = analysis_scores["policy"].map(POLICY_LABELS)
    analysis_scores["axis_label"] = analysis_scores["axis"].map(AXIS_LABELS)

    participant_overall = (
        analysis_scores[analysis_scores["policy"] == "All"]
        .groupby(["participant_id", "experience_group"], as_index=False)
        .agg(score_0_100=("score_0_100", "mean"))
    )

    return answers, analysis_scores, participant_overall


def hedges_g(daily_values: np.ndarray, no_contact_values: np.ndarray) -> float:
    daily_values = daily_values[~np.isnan(daily_values)]
    no_contact_values = no_contact_values[~np.isnan(no_contact_values)]
    n_daily = len(daily_values)
    n_no_contact = len(no_contact_values)
    pooled_variance = (
        (n_daily - 1) * daily_values.var(ddof=1)
        + (n_no_contact - 1) * no_contact_values.var(ddof=1)
    ) / (n_daily + n_no_contact - 2)
    pooled_sd = np.sqrt(pooled_variance)
    if pooled_sd == 0:
        return np.nan
    correction = 1 - 3 / (4 * (n_daily + n_no_contact) - 9)
    return float(correction * ((daily_values.mean() - no_contact_values.mean()) / pooled_sd))


def bootstrap_difference(
    daily_values: np.ndarray, no_contact_values: np.ndarray, seed: int
) -> dict[str, float]:
    daily_values = np.asarray(daily_values, dtype=float)
    no_contact_values = np.asarray(no_contact_values, dtype=float)
    daily_values = daily_values[~np.isnan(daily_values)]
    no_contact_values = no_contact_values[~np.isnan(no_contact_values)]

    rng = np.random.default_rng(seed)
    daily_indices = rng.integers(
        0, len(daily_values), size=(BOOTSTRAP_RESAMPLES, len(daily_values))
    )
    no_contact_indices = rng.integers(
        0,
        len(no_contact_values),
        size=(BOOTSTRAP_RESAMPLES, len(no_contact_values)),
    )
    bootstrap_diffs = daily_values[daily_indices].mean(axis=1) - no_contact_values[
        no_contact_indices
    ].mean(axis=1)

    mean_diff = daily_values.mean() - no_contact_values.mean()
    ci_low, ci_high = np.quantile(bootstrap_diffs, [0.025, 0.975])

    return {
        "daily_minus_no_contact": float(mean_diff),
        "ci_low": float(ci_low),
        "ci_high": float(ci_high),
        "daily_minus_no_contact_likert": float(mean_diff * 6 / 100),
        "hedges_g": hedges_g(daily_values, no_contact_values),
        "n_daily_contact": int(len(daily_values)),
        "n_no_daily_contact": int(len(no_contact_values)),
    }


def compare_groups(frame: pd.DataFrame, seed: int) -> dict[str, float]:
    daily_values = frame.loc[frame["experience_group"] == DAILY_CONTACT, "score_0_100"].to_numpy(
        dtype=float
    )
    no_contact_values = frame.loc[frame["experience_group"] == NO_CONTACT, "score_0_100"].to_numpy(
        dtype=float
    )
    return bootstrap_difference(daily_values, no_contact_values, seed)


def build_score_table(analysis_scores: pd.DataFrame) -> pd.DataFrame:
    mean_scores = analysis_scores.groupby(
        ["policy", "policy_label", "axis", "axis_label", "experience_group"],
        as_index=False,
    ).agg(mean_score=("score_0_100", "mean"), n_participants=("participant_id", "nunique"))

    score_table = mean_scores.pivot_table(
        index=["policy", "policy_label", "axis", "axis_label"],
        columns="experience_group",
        values="mean_score",
    ).reset_index()
    score_table["daily_minus_no_contact"] = score_table[DAILY_CONTACT] - score_table[NO_CONTACT]
    score_table["axis_order"] = score_table["axis"].map(
        {axis: index for index, axis in enumerate(AXES)}
    )
    score_table["policy_order"] = score_table["policy"].map({"A": 0, "B": 1, "All": 2})
    return score_table.sort_values(["policy_order", "axis_order"]).drop(
        columns=["policy_order", "axis_order"]
    )


def build_policy_effects(analysis_scores: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for seed_offset, policy in enumerate(["A", "B", "All"]):
        participant_policy_mean = (
            analysis_scores[analysis_scores["policy"] == policy]
            .groupby(["participant_id", "experience_group"], as_index=False)
            .agg(score_0_100=("score_0_100", "mean"))
        )
        result = compare_groups(participant_policy_mean, seed=BOOTSTRAP_SEED + seed_offset)
        result.update({"policy": policy, "policy_label": POLICY_LABELS[policy]})
        rows.append(result)
    return pd.DataFrame(rows)


def build_axis_effects(analysis_scores: pd.DataFrame) -> pd.DataFrame:
    rows = []
    combined_scores = analysis_scores[analysis_scores["policy"] == "All"].copy()

    for seed_offset, axis in enumerate(AXES):
        axis_frame = combined_scores[combined_scores["axis"] == axis]
        result = compare_groups(axis_frame, seed=BOOTSTRAP_SEED + 100 + seed_offset)
        result.update({"axis": axis, "axis_label": AXIS_LABELS[axis]})
        rows.append(result)

    overall_frame = combined_scores.groupby(
        ["participant_id", "experience_group"], as_index=False
    ).agg(score_0_100=("score_0_100", "mean"))
    overall_result = compare_groups(overall_frame, seed=BOOTSTRAP_SEED + 200)
    overall_result.update({"axis": "overall", "axis_label": "Overall"})
    rows.insert(0, overall_result)

    return pd.DataFrame(rows)


def save_figure(fig: plt.Figure) -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        ASSETS_DIR / "fig6_robot_experience.pdf",
        bbox_inches="tight",
        facecolor="white",
        metadata={"CreationDate": None, "ModDate": None},
    )
    plt.close(fig)


def plot_paired_axis_distributions(
    analysis_scores: pd.DataFrame,
    participant_overall: pd.DataFrame,
    axis_effects: pd.DataFrame,
) -> None:
    """Plot both familiarity groups on a shared rating scale for every axis."""
    combined_axis_scores = analysis_scores[analysis_scores["policy"] == "All"]
    effect_by_axis = axis_effects.set_index("axis")
    rng = np.random.default_rng(RANDOM_SEED + 177)
    plot_rows = [("overall", participant_overall)] + [
        (axis, combined_axis_scores[combined_axis_scores["axis"] == axis]) for axis in AXES
    ]

    with plt.rc_context(
        {
            "font.size": 7,
            "axes.labelsize": 7,
            "xtick.labelsize": 6.5,
            "ytick.labelsize": 7,
        }
    ):
        fig, axes = plt.subplots(
            len(plot_rows),
            1,
            figsize=(3.35, 5.25),
            sharex=True,
            gridspec_kw={"hspace": 0.12},
        )

        for ax, (axis, frame) in zip(axes, plot_rows, strict=True):
            values_by_group = [
                frame.loc[
                    frame["experience_group"] == group,
                    "score_0_100",
                ]
                .dropna()
                .to_numpy(dtype=float)
                for group in (NO_CONTACT, DAILY_CONTACT)
            ]

            for group, values in zip((NO_CONTACT, DAILY_CONTACT), values_by_group, strict=True):
                direction = 1 if group == NO_CONTACT else -1
                violin = ax.violinplot(
                    [values],
                    positions=[0.0],
                    vert=False,
                    widths=0.78,
                    showmeans=False,
                    showmedians=False,
                    showextrema=False,
                    bw_method=0.32,
                )
                body = violin["bodies"][0]
                body.set_facecolor(GROUP_COLORS[group])
                body.set_edgecolor(GROUP_COLORS[group])
                body.set_linewidth(0.75)
                body.set_alpha(0.18)
                vertices = body.get_paths()[0].vertices
                if direction > 0:
                    vertices[:, 1] = np.maximum(vertices[:, 1], 0.0)
                else:
                    vertices[:, 1] = np.minimum(vertices[:, 1], 0.0)

                point_offsets = rng.uniform(0.065, 0.34, size=len(values)) * direction
                ax.scatter(
                    values,
                    point_offsets,
                    s=8.5 if group == NO_CONTACT else 13,
                    color=GROUP_COLORS[group],
                    alpha=0.44 if group == NO_CONTACT else 0.62,
                    linewidths=0,
                    zorder=3,
                )

            means = [float(np.mean(values)) for values in values_by_group]
            ax.plot(means, [0.0, 0.0], color="#303030", linewidth=1.15, zorder=4)
            for group, mean in zip((NO_CONTACT, DAILY_CONTACT), means, strict=True):
                ax.scatter(
                    mean,
                    0.0,
                    s=29,
                    color=GROUP_COLORS[group],
                    edgecolor="white",
                    linewidth=0.7,
                    zorder=5,
                )

            shift = float(effect_by_axis.loc[axis, "daily_minus_no_contact"])
            ax.text(
                0.985,
                0.83,
                rf"$\Delta={shift:.1f}$",
                transform=ax.transAxes,
                ha="right",
                va="top",
                color="#303030",
                fontsize=6.5,
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.86, "pad": 0.6},
                zorder=6,
            )
            axis_label = "Overall" if axis == "overall" else AXIS_LABELS[axis]
            if axis_label == "Social Awareness":
                axis_label = "Social\nAwareness"
            ax.set_ylabel(axis_label, rotation=0, ha="right", va="center", labelpad=12)
            ax.set_yticks([])
            ax.set_ylim(-0.56, 0.56)
            ax.set_xlim(0, 100)
            ax.grid(axis="x", color="#d7d7d7", linewidth=0.55, alpha=0.75)
            ax.set_axisbelow(True)
            for side in ("top", "right", "left"):
                ax.spines[side].set_visible(False)

        for ax in axes[:-1]:
            ax.spines["bottom"].set_visible(False)
            ax.tick_params(axis="x", which="both", bottom=False, labelbottom=False)

        axes[-1].set_xticks(np.arange(0, 101, 20))
        axes[-1].set_xlabel("Participant mean rating (0-100)")
        axes[-1].spines["bottom"].set_color("#333333")

        group_sizes = {
            group: int((participant_overall["experience_group"] == group).sum())
            for group in (NO_CONTACT, DAILY_CONTACT)
        }
        legend_handles = [
            Line2D(
                [0],
                [0],
                marker="o",
                color=GROUP_COLORS[group],
                markerfacecolor=GROUP_COLORS[group],
                linewidth=5,
                alpha=0.55,
                markersize=4,
                label=f"{group} (n={group_sizes[group]})",
            )
            for group in (NO_CONTACT, DAILY_CONTACT)
        ]
        fig.legend(
            handles=legend_handles,
            loc="upper center",
            bbox_to_anchor=(0.57, 1.0),
            ncol=1,
            frameon=False,
            handlelength=1.5,
            borderaxespad=0,
        )
        fig.subplots_adjust(left=0.29, right=0.985, top=0.89, bottom=0.09)
        save_figure(fig)


def write_dataset_audit(survey_wide: pd.DataFrame) -> None:
    score_columns = [
        column for column in survey_wide.columns if re.fullmatch(r"q[1-4]_[1-4]", column)
    ]
    complete = survey_wide.dropna(subset=score_columns)
    rows = [
        {
            "dataset": SURVEY_PATH.name,
            "scope": "all responses",
            "n_total": len(survey_wide),
            "n_daily_contact": int(survey_wide["robotics_familiarity"].eq(True).sum()),
            "n_no_daily_contact": int(survey_wide["robotics_familiarity"].eq(False).sum()),
            "n_blank_familiarity": int(survey_wide["robotics_familiarity"].isna().sum()),
            "n_complete_16_ratings": int(len(complete)),
            "n_complete_daily_contact": int(complete["robotics_familiarity"].eq(True).sum()),
            "n_complete_no_daily_contact": int(complete["robotics_familiarity"].eq(False).sum()),
            "n_complete_blank_familiarity": int(complete["robotics_familiarity"].isna().sum()),
        }
    ]
    pd.DataFrame(rows).to_csv(RESULTS_DIR / "robot_experience_dataset_audit.csv", index=False)


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    survey_wide, survey_long = load_survey_long(SURVEY_PATH)
    answers, analysis_scores, participant_overall = prepare_analysis_scores(survey_long)

    score_table = build_score_table(analysis_scores)
    policy_effects = build_policy_effects(analysis_scores)
    axis_effects = build_axis_effects(analysis_scores)

    score_table.to_csv(RESULTS_DIR / "robot_experience_mean_scores.csv", index=False)
    policy_effects.to_csv(RESULTS_DIR / "robot_experience_policy_effects.csv", index=False)
    axis_effects.to_csv(RESULTS_DIR / "robot_experience_axis_effects.csv", index=False)
    write_dataset_audit(survey_wide)

    plot_paired_axis_distributions(analysis_scores, participant_overall, axis_effects)

    group_sizes = (
        answers[["participant_id", "experience_group"]]
        .drop_duplicates()
        .groupby("experience_group")
        .size()
    )
    combined = policy_effects.loc[policy_effects["policy"] == "All"].iloc[0]
    print(f"Source: {SURVEY_PATH.relative_to(PROJECT_ROOT)}")
    print(group_sizes.to_string())
    print(
        "Combined daily-minus-no-contact: "
        f"{combined['daily_minus_no_contact']:.3f} "
        f"[{combined['ci_low']:.3f}, {combined['ci_high']:.3f}]"
    )
    print(f"Wrote results to: {RESULTS_DIR.relative_to(PROJECT_ROOT)}")
    print(
        f"Saved Figure 6 to: {(ASSETS_DIR / 'fig6_robot_experience.pdf').relative_to(PROJECT_ROOT)}"
    )


if __name__ == "__main__":
    main()
