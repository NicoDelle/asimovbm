from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAPER_DIR = PROJECT_ROOT / "paper"
RESULTS_DIR = PAPER_DIR / "results"
ASSETS_DIR = PAPER_DIR / "assets"

PROFILE_SOURCE = RESULTS_DIR / "profile_alignment.csv"

AXES = ["competence_control", "safety", "awareness", "positive_impression"]
AXIS_LABELS = {
    "competence_control": "Dexterity",
    "safety": "Safety",
    "awareness": "Social\nAware.",
    "positive_impression": "Impression",
}
POLICY_COLORS = {
    "A": "#174A7E",
    "B": "#8A5A12",
}
HUMAN_COLOR = "#1F1F1F"
RIBBON_COLOR = "#BFC7CE"


def load_profile_table() -> pd.DataFrame:
    profile = pd.read_csv(PROFILE_SOURCE)
    profile = profile[profile["axis"].isin(AXES)].copy()
    profile["axis_order"] = profile["axis"].map({axis: index for index, axis in enumerate(AXES)})
    profile["axis_label"] = profile["axis"].map(lambda axis: AXIS_LABELS[axis].replace("\n", " "))
    return profile.sort_values(["policy", "source", "axis_order"])


def profile_row(profile: pd.DataFrame, policy: str, source: str) -> pd.DataFrame:
    return (
        profile[(profile["policy"] == policy) & (profile["source"] == source)]
        .set_index("axis")
        .loc[AXES]
        .reset_index()
    )


def save_figure(fig: plt.Figure) -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        ASSETS_DIR / "fig4_profile_alignment.pdf",
        metadata={"CreationDate": None, "ModDate": None},
    )


def make_plot(profile: pd.DataFrame) -> None:
    x = np.arange(len(AXES))
    axis_labels = [AXIS_LABELS[axis] for axis in AXES]

    try:
        from matplotlib import font_manager

        for font_path in Path("/usr/share/fonts/truetype/croscore").glob("Tinos*.ttf"):
            font_manager.fontManager.addfont(font_path)
    except Exception:
        pass

    with plt.rc_context(
        {
            "font.family": "Tinos",
            "font.serif": ["Tinos", "Times New Roman", "Liberation Serif", "serif"],
            "mathtext.fontset": "dejavuserif",
            "font.size": 6.7,
            "axes.labelsize": 6.8,
            "axes.titlesize": 7.1,
            "xtick.labelsize": 6.1,
            "ytick.labelsize": 6.2,
        }
    ):
        fig, axes = plt.subplots(
            2,
            1,
            figsize=(3.35, 2.45),
            sharex=True,
            sharey=True,
            gridspec_kw={"hspace": 0.20},
        )

        for ax, policy in zip(axes, ["A", "B"], strict=True):
            human = profile_row(profile, policy, "Human")
            auto = profile_row(profile, policy, "Auto")
            policy_color = POLICY_COLORS[policy]

            human_mean = human["score_0_100"].to_numpy(dtype=float)
            human_low = human["ci_low_0_100"].to_numpy(dtype=float)
            human_high = human["ci_high_0_100"].to_numpy(dtype=float)
            auto_mean = auto["score_0_100"].to_numpy(dtype=float)

            ax.fill_between(
                x,
                human_low,
                human_high,
                color=RIBBON_COLOR,
                alpha=0.36,
                linewidth=0,
                zorder=1,
            )
            ax.plot(
                x,
                human_mean,
                color=HUMAN_COLOR,
                linewidth=1.45,
                marker="o",
                markersize=3.7,
                markerfacecolor="white",
                markeredgecolor=HUMAN_COLOR,
                markeredgewidth=0.8,
                label="Human mean",
                zorder=4,
            )
            ax.plot(
                x,
                auto_mean,
                color=policy_color,
                linewidth=1.45,
                linestyle=(0, (3.2, 1.9)),
                marker="D",
                markersize=3.4,
                markerfacecolor=policy_color,
                markeredgecolor="white",
                markeredgewidth=0.45,
                label="AsimovBM",
                zorder=5,
            )

            title_text = (
                "Policy A: sharper capability profile"
                if policy == "A"
                else "Policy B: flatter lower profile"
            )
            ax.set_title(title_text, loc="left", color=policy_color, fontweight="bold", pad=1.5)
            ax.set_ylim(24, 62)
            ax.set_xlim(-0.18, len(AXES) - 0.82)
            ax.set_yticks([30, 40, 50, 60])
            ax.grid(axis="y", alpha=0.20, linewidth=0.7)
            ax.grid(axis="x", alpha=0.12, linewidth=0.6)
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["left"].set_color("#333333")
            ax.spines["bottom"].set_color("#333333")
            ax.tick_params(axis="both", length=2.3, width=0.6)

        axes[0].legend(
            loc="upper right",
            bbox_to_anchor=(0.68, 1.00),
            frameon=False,
            fontsize=5.8,
            handlelength=1.6,
            borderaxespad=0.10,
        )
        axes[0].set_ylabel("Score (0-100)")
        axes[1].set_ylabel("Score (0-100)")
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(axis_labels)
        axes[1].set_xlabel("Perceptual axis")

        fig.subplots_adjust(left=0.145, right=0.985, bottom=0.18, top=0.96)
        save_figure(fig)
        plt.close(fig)


def main() -> None:
    profile = load_profile_table()
    make_plot(profile)
    print(profile.to_string(index=False))
    print(f"Saved Figure 4 to {ASSETS_DIR / 'fig4_profile_alignment.pdf'}")


if __name__ == "__main__":
    main()
