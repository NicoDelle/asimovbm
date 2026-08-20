"""Reproduce the statistical evidence for the POV appendix section.

Run from the repository root with:

    .venv/bin/python paper/analysis/reproduce_pov_statistics.py

The script reads the raw survey file, recreates the same held-out participant
split used in the paper, and prints the POV statistics reported in the text.
It does not generate plots or write output files.
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd

# Locate the raw survey relative to this script, so the file can be run from
# any working directory inside the repository.
ROOT = Path(__file__).resolve().parents[2]
SURVEY_PATH = ROOT / "paper" / "data" / "human-survey" / "responses.csv"

# Same split used by the paper: 50 participants for calibration/tuning and the
# remaining 70 participants for held-out validation.
RANDOM_SEED = 20260514
TUNING_N = 50

# Resampling settings used for the reported confidence intervals and p-values.
N_BOOT = 10_000
N_PERM = 200_000

# Survey condition mapping:
# q1 = Policy A, first-person video
# q2 = Policy B, first-person video
# q3 = Policy A, third-person video
# q4 = Policy B, third-person video
CONDITIONS = {
    "q1": ("A", "first"),
    "q2": ("B", "first"),
    "q3": ("A", "third"),
    "q4": ("B", "third"),
}

# Within each condition, questions 1-4 correspond to the four perceptual axes.
AXES = {
    "1": "Dexterity",
    "2": "Safety",
    "3": "Social Awareness",
    "4": "Impression",
}


def likert_to_number(value):
    """Convert survey strings such as '+2 ...' or '-1 ...' to numeric scores."""
    text = str(value)
    for score in ["-3", "-2", "-1", "0", "+1", "+2", "+3"]:
        if text.startswith(score):
            return float(score)
    return np.nan


def load_heldout_long():
    """Load the raw survey and return one row per participant/condition/axis."""
    raw = pd.read_csv(SURVEY_PATH)

    # Rename long Google-Forms column names to compact names such as q1_1,
    # q1_2, ..., q4_4. This makes the analysis independent of the full text of
    # the survey questions.
    rename = {}
    for column in raw.columns:
        if column.startswith("Q"):
            rename[column] = column.split(" ", 1)[0].lower().replace(".", "_")
    wide = raw.rename(columns=rename).copy()
    wide.insert(0, "participant_id", np.arange(1, len(wide) + 1))

    # Convert all Likert answers from text to numeric values on the -3..+3 scale.
    score_columns = [c for c in wide.columns if re.fullmatch(r"q[1-4]_[1-4]", c)]
    for column in score_columns:
        wide[column] = wide[column].apply(likert_to_number)

    # Recreate the paper's held-out split exactly.
    participant_ids = wide["participant_id"].to_numpy().copy()
    rng = np.random.default_rng(RANDOM_SEED)
    rng.shuffle(participant_ids)
    heldout_ids = set(participant_ids[TUNING_N:])

    # Convert from wide format to long format:
    # participant_id, policy, POV, axis, score.
    rows = []
    for condition, (policy, pov) in CONDITIONS.items():
        for axis_number, axis_name in AXES.items():
            column = f"{condition}_{axis_number}"
            for _, row in wide[wide["participant_id"].isin(heldout_ids)].iterrows():
                rows.append(
                    {
                        "participant_id": row["participant_id"],
                        "condition": condition,
                        "policy": policy,
                        "pov": pov,
                        "axis": axis_name,
                        "score": row[column],
                    }
                )
    return pd.DataFrame(rows)


def summarize(values, seed):
    """Return n, mean, bootstrap 95% CI, and paired sign-flip p-value."""
    values = np.asarray(values, dtype=float)
    values = values[~np.isnan(values)]

    # Participant bootstrap CI for the mean paired contrast.
    boot_rng = np.random.default_rng(seed)
    boot = boot_rng.choice(values, size=(N_BOOT, len(values)), replace=True).mean(axis=1)
    ci_low, ci_high = np.quantile(boot, [0.025, 0.975])

    # Two-sided paired permutation test under the null that each paired
    # difference is equally likely to have either sign.
    observed = abs(values.mean())
    perm_rng = np.random.default_rng(seed)
    signs = perm_rng.choice([-1, 1], size=(N_PERM, len(values)))
    null = np.abs((signs * values).mean(axis=1))
    p_value = (np.sum(null >= observed) + 1) / (N_PERM + 1)

    return {
        "n": len(values),
        "mean": values.mean(),
        "ci_low": ci_low,
        "ci_high": ci_high,
        "p": p_value,
    }


def main():
    data = load_heldout_long()

    # These three lists become the three printed tables below.
    direct_rows = []
    policy_rows = []
    separation_rows = []

    for axis_i, axis in enumerate(AXES.values()):
        axis_data = data[data["axis"] == axis]

        # Main POV effect:
        # mean(first-person ratings across A/B) - mean(third-person ratings across A/B)
        complete = axis_data.pivot_table(
            index="participant_id", columns="condition", values="score"
        ).dropna(subset=["q1", "q2", "q3", "q4"])
        direct_diff = (complete["q1"] + complete["q2"]) / 2 - (complete["q3"] + complete["q4"]) / 2
        direct_rows.append({"axis": axis, **summarize(direct_diff, seed=axis_i)})

        # Policy-specific POV effect:
        # first-person - third-person within each policy.
        for policy_i, policy in enumerate(["A", "B"]):
            paired = (
                axis_data[axis_data["policy"] == policy]
                .pivot_table(index="participant_id", columns="pov", values="score")
                .dropna(subset=["first", "third"])
            )
            diff = paired["first"] - paired["third"]
            policy_rows.append(
                {
                    "policy": policy,
                    "axis": axis,
                    **summarize(diff, seed=100 + 10 * policy_i + axis_i),
                }
            )

        # POV as a moderator of policy discrimination:
        # compare the A-B policy gap in third-person view against the A-B gap in first-person view.
        first = (
            axis_data[axis_data["pov"] == "first"]
            .pivot_table(index="participant_id", columns="policy", values="score")
            .dropna(subset=["A", "B"])
        )
        third = (
            axis_data[axis_data["pov"] == "third"]
            .pivot_table(index="participant_id", columns="policy", values="score")
            .dropna(subset=["A", "B"])
        )
        gaps = pd.concat(
            {
                "first_A_minus_B": first["A"] - first["B"],
                "third_A_minus_B": third["A"] - third["B"],
            },
            axis=1,
        ).dropna()

        # Positive interaction means that third-person view separates Policy A
        # from Policy B more strongly than first-person view.
        interaction = gaps["third_A_minus_B"] - gaps["first_A_minus_B"]
        interaction_summary = summarize(interaction, seed=200 + axis_i)
        separation_rows.append(
            {
                "axis": axis,
                "n": len(gaps),
                "first_A_minus_B": gaps["first_A_minus_B"].mean(),
                "third_A_minus_B": gaps["third_A_minus_B"].mean(),
                "third_minus_first_gap": interaction_summary["mean"],
                "ci_low": interaction_summary["ci_low"],
                "ci_high": interaction_summary["ci_high"],
                "p": interaction_summary["p"],
            }
        )

    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 140)

    print("\nMain POV effect: first-person minus third-person, averaged across policies")
    print(pd.DataFrame(direct_rows).round(4).to_string(index=False))

    print("\nPolicy-specific POV effect: first-person minus third-person")
    print(pd.DataFrame(policy_rows).round(4).to_string(index=False))

    print("\nPolicy discrimination by POV: A-minus-B gap in first-person vs third-person")
    print(pd.DataFrame(separation_rows).round(4).to_string(index=False))


if __name__ == "__main__":
    main()
