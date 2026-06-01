from matplotlib.patches import Patch
from matplotlib.transforms import ScaledTranslation

POLICY_SPIDERPLOT_HUMAN_CI_PATH = (
    ANALYSIS_DIR / "heldout_policy_spiderplot_human_ci.png"
)
POLICY_SPIDERPLOT_HUMAN_CI_TABLE_PATH = POLICY_SPIDERPLOT_HUMAN_CI_PATH.with_suffix(".csv")
POLICY_HUMAN_CI_BOOTSTRAPS = 10000
POLICY_HUMAN_CI_SEED = RANDOM_SEED + 31
POLICY_HUMAN_CI_LEVEL = 95
POLICY_SPIDERPLOT_HUMAN_CI_R_MIN = 20  # Set anywhere from 0 to 20.
# Label nudges are in points. Positive x moves right; negative x moves left.
# Positive y moves up; negative y moves down.
POLICY_SPIDERPLOT_HUMAN_CI_DEXTERITY_X_OFFSET_POINTS = 22.0
POLICY_SPIDERPLOT_HUMAN_CI_SAFETY_Y_OFFSET_POINTS = -6.0
POLICY_SPIDERPLOT_HUMAN_CI_SOCIAL_AWARENESS_X_OFFSET_POINTS = 0.0
POLICY_SPIDERPLOT_HUMAN_CI_IMPRESSION_Y_OFFSET_POINTS = 0.0
POLICY_SPIDERPLOT_HUMAN_CI_LABEL_OFFSETS_POINTS = {
    "competence_control": (POLICY_SPIDERPLOT_HUMAN_CI_DEXTERITY_X_OFFSET_POINTS, 0.0),
    "safety": (0.0, POLICY_SPIDERPLOT_HUMAN_CI_SAFETY_Y_OFFSET_POINTS),
    "awareness": (POLICY_SPIDERPLOT_HUMAN_CI_SOCIAL_AWARENESS_X_OFFSET_POINTS, 0.0),
    "positive_impression": (0.0, POLICY_SPIDERPLOT_HUMAN_CI_IMPRESSION_Y_OFFSET_POINTS),
}
if not 0 <= POLICY_SPIDERPLOT_HUMAN_CI_R_MIN <= 20:
    raise ValueError("POLICY_SPIDERPLOT_HUMAN_CI_R_MIN must be between 0 and 20.")
policy_human_ci_r_ticks = (
    [20, 30, 40, 50, 60]
    if POLICY_SPIDERPLOT_HUMAN_CI_R_MIN == 20
    else [POLICY_SPIDERPLOT_HUMAN_CI_R_MIN, 20, 30, 40, 50, 60]
)


def policy_bootstrap_mean_ci(values, *, n_resamples=POLICY_HUMAN_CI_BOOTSTRAPS, seed=POLICY_HUMAN_CI_SEED):
    values = np.asarray(values, dtype=float)
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return np.nan, np.nan, np.nan, 0
    if len(values) == 1:
        value = float(values[0])
        return value, value, value, 1

    rng = np.random.default_rng(seed)
    sample_indices = rng.integers(0, len(values), size=(n_resamples, len(values)))
    bootstrap_means = values[sample_indices].mean(axis=1)
    ci_probability = POLICY_HUMAN_CI_LEVEL / 100
    tail_probability = (1 - ci_probability) / 2
    ci_low, ci_high = np.quantile(bootstrap_means, [tail_probability, 1 - tail_probability])
    return float(values.mean()), float(ci_low), float(ci_high), int(len(values))

policy_human_participant_values = (
    survey_validation_long[survey_validation_long["axis"].isin(CALIBRATION_AXES)]
    .groupby(["participant_id", "policy", "axis"], dropna=False)
    .agg(score_0_100=("score_norm", lambda values: values.mean() * 100))
    .reset_index()
)

policy_human_ci_rows = []
for policy_index, policy in enumerate(["A", "B"]):
    for axis_index, axis in enumerate(CALIBRATION_AXES):
        values = policy_human_participant_values[
            (policy_human_participant_values["policy"] == policy)
            & (policy_human_participant_values["axis"] == axis)
        ]["score_0_100"].to_numpy()
        mean, ci_low, ci_high, n = policy_bootstrap_mean_ci(
            values,
            n_resamples=POLICY_HUMAN_CI_BOOTSTRAPS,
            seed=POLICY_HUMAN_CI_SEED + policy_index * 10 + axis_index,
        )
        policy_human_ci_rows.append(
            {
                "series": f"Policy {policy} Human",
                "policy": policy,
                "source": "Human",
                "axis": axis,
                "mean_0_100": mean,
                "ci_low_0_100": ci_low,
                "ci_high_0_100": ci_high,
                "ci_level_percent": POLICY_HUMAN_CI_LEVEL,
                "n": n,
                "bootstrap_unit": "participant",
            }
        )

policy_human_ci = pd.DataFrame(policy_human_ci_rows)
policy_spiderplot_human_ci_table = policy_spiderplot_table.merge(
    policy_human_ci[
        ["series", "policy", "source", "axis", "ci_low_0_100", "ci_high_0_100", "ci_level_percent", "bootstrap_unit"]
    ],
    on=["series", "policy", "source", "axis"],
    how="left",
)
policy_spiderplot_human_ci_table["ci_low_0_100"] = policy_spiderplot_human_ci_table[
    "ci_low_0_100"
].where(policy_spiderplot_human_ci_table["source"] == "Human")
policy_spiderplot_human_ci_table["ci_high_0_100"] = policy_spiderplot_human_ci_table[
    "ci_high_0_100"
].where(policy_spiderplot_human_ci_table["source"] == "Human")
policy_spiderplot_human_ci_table["bootstrap_unit"] = policy_spiderplot_human_ci_table[
    "bootstrap_unit"
].where(policy_spiderplot_human_ci_table["source"] == "Human", "")
policy_spiderplot_human_ci_table["ci_level_percent"] = policy_spiderplot_human_ci_table[
    "ci_level_percent"
].where(policy_spiderplot_human_ci_table["source"] == "Human")

policy_spiderplot_human_ci_table_rounded = policy_spiderplot_human_ci_table.copy()
for column in ["score_0_100", "ci_low_0_100", "ci_high_0_100"]:
    policy_spiderplot_human_ci_table_rounded[column] = policy_spiderplot_human_ci_table_rounded[column].round(1)
policy_spiderplot_human_ci_table_rounded.to_csv(POLICY_SPIDERPLOT_HUMAN_CI_TABLE_PATH, index=False)


def closed_policy_human_ci_values(series_label, column):
    series_frame = policy_human_ci[policy_human_ci["series"] == series_label]
    values = [
        float(series_frame.loc[series_frame["axis"] == axis, column].iloc[0])
        for axis in CALIBRATION_AXES
    ]
    return values + values[:1]


with plt.rc_context(
    {
        "font.family": POLICY_SPIDERPLOT_FONT,
        "font.serif": ["Times New Roman", "Tinos", "Liberation Serif", "serif"],
        "mathtext.fontset": "dejavuserif",
    }
):
    fig, ax = plt.subplots(figsize=(6.9, 6.5), subplot_kw={"polar": True})
    ci_patch_handles = []

    for series in [spec for spec in POLICY_SERIES if spec["source"] == "Human"]:
        low_values = closed_policy_human_ci_values(series["label"], "ci_low_0_100")
        high_values = closed_policy_human_ci_values(series["label"], "ci_high_0_100")
        ax.fill_between(policy_angles, low_values, high_values, color=series["color"], alpha=0.105, zorder=1)
        ci_patch_handles.append(
            Patch(
                facecolor=series["color"],
                edgecolor="none",
                alpha=0.105,
                label=f"{series['label']} {POLICY_HUMAN_CI_LEVEL}% CI",
            )
        )

    for index, series in enumerate(POLICY_SERIES):
        values = closed_policy_values(series["label"])
        ax.plot(
            policy_angles,
            values,
            color=series["color"],
            linewidth=2.45,
            marker="o",
            markersize=5.8,
            label=series["label"],
            zorder=4 - index * 0.1,
        )

    ax.set_ylim(POLICY_SPIDERPLOT_HUMAN_CI_R_MIN, POLICY_SPIDERPLOT_R_MAX)
    ax.set_yticks(policy_human_ci_r_ticks)
    radial_tick_labels = ax.set_yticklabels([f"{tick:g}" for tick in policy_human_ci_r_ticks], fontsize=11.0)
    for label in radial_tick_labels:
        label.set_zorder(10)
        label.set_bbox({"facecolor": "white", "edgecolor": "none", "alpha": 0.72, "pad": 0.2})
    ax.set_xticks(policy_angles[:-1])
    axis_tick_labels = ax.set_xticklabels([POLICY_AXIS_LABELS[axis] for axis in CALIBRATION_AXES], fontsize=14)
    ax.tick_params(axis="x", pad=9)
    for axis, label in zip(CALIBRATION_AXES, axis_tick_labels):
        x_offset_points, y_offset_points = POLICY_SPIDERPLOT_HUMAN_CI_LABEL_OFFSETS_POINTS.get(axis, (0.0, 0.0))
        if x_offset_points or y_offset_points:
            label.set_transform(
                label.get_transform()
                + ScaledTranslation(x_offset_points / 72, y_offset_points / 72, fig.dpi_scale_trans)
            )
    ax.grid(True, linewidth=0.8, alpha=0.5)
    ax.spines["polar"].set_linewidth(1.0)
    ax.set_rlabel_position(25)
    line_handles, line_labels = ax.get_legend_handles_labels()
    line_handle_by_label = dict(zip(line_labels, line_handles))
    ci_handle_by_label = {handle.get_label(): handle for handle in ci_patch_handles}
    legend_handles = [
        line_handle_by_label["Policy A Human"],
        line_handle_by_label["Policy A Auto"],
        ci_handle_by_label[f"Policy A Human {POLICY_HUMAN_CI_LEVEL}% CI"],
        line_handle_by_label["Policy B Human"],
        line_handle_by_label["Policy B Auto"],
        ci_handle_by_label[f"Policy B Human {POLICY_HUMAN_CI_LEVEL}% CI"],
    ]
    legend = ax.legend(
        handles=legend_handles,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.35),
        ncol=2,
        fontsize=11,
        frameon=True,
    )
    legend.get_frame().set_alpha(0.95)
    legend.get_frame().set_linewidth(0.7)
    fig.subplots_adjust(left=0.16, right=0.84, top=0.92, bottom=0.36)
    fig.savefig(POLICY_SPIDERPLOT_HUMAN_CI_PATH, dpi=450, bbox_inches="tight", pad_inches=0.15)
    plt.show()

print(f"Saved policy spiderplot with human CIs: {POLICY_SPIDERPLOT_HUMAN_CI_PATH}")
print(f"Saved policy spiderplot human CI table: {POLICY_SPIDERPLOT_HUMAN_CI_TABLE_PATH}")
display(policy_spiderplot_human_ci_table_rounded)
