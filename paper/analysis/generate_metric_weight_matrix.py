from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from asimovbm.metrics.models import SOCIAL_NAVIGATION_AXIS_IDS, SOCIAL_NAVIGATION_METRIC_IDS
from asimovbm.metrics.weights import normalized_axis_weights

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PAPER_DIR = PROJECT_ROOT / "paper"
ASSETS_DIR = PAPER_DIR / "assets"
RESULTS_DIR = PAPER_DIR / "results"

AXIS_LABELS = {
    "perceived_dexterity": "Dexterity",
    "perceived_safety": "Safety",
    "perceived_social_awareness": "Social Awareness",
    "impression": "Impression",
}
AXIS_COLORS = {
    "perceived_dexterity": "#174A7E",
    "perceived_safety": "#4F9A94",
    "perceived_social_awareness": "#A06A16",
    "impression": "#6D5B8D",
}
METRIC_LABELS = {
    "task_success_rate": ("Task Success Rate", "acknowledges and stops at target"),
    "task_completion_time": ("Task Completion Time", "time needed after success"),
    "comfort_aware_path_efficiency": (
        "Comfort-Aware Path Efficiency",
        "efficient approach outside comfort zones",
    ),
    "hesitation": ("Hesitation Rate", "stops, reversals, or indecisive motion"),
    "min_human_robot_distance": ("Minimum Human-Robot Distance", "closest instant to a person"),
    "proxemic_intrusion_dose": (
        "Proxemic Intrusion Dose",
        "depth and duration inside personal space",
    ),
    "speed_near_humans_p95": ("Speed Near Humans", "fast close passes near people"),
    "gesture_response_success": (
        "Gesture Response Success",
        "responds correctly to an explicit cue",
    ),
    "acknowledgement_clarity": ("Acknowledgement Clarity", "orients toward the intended target"),
    "human_aware_approach": ("Human-Aware Approach", "progress, clearance, and approach angle"),
    "bystander_ack": ("Bystander Acknowledgement", "preserves clearance and slows near bystanders"),
    "sparc": ("Motion Smoothness (SPARC)", "smooth translational motion"),
    "heading_jerk": ("Heading Jerk", "smooth turning behavior"),
    "stability": ("Stability", "falls, collisions, and invalid actions"),
    "legibility": ("Legibility", "early commitment to an interpretable trajectory"),
    "behavioral_naturalness": ("Behavioral Naturalness", "gait or wheel-velocity regularity"),
}
GROUPS = {
    "Task performance": [
        "task_success_rate",
        "task_completion_time",
        "comfort_aware_path_efficiency",
        "hesitation",
    ],
    "Human spacing": [
        "min_human_robot_distance",
        "proxemic_intrusion_dose",
        "speed_near_humans_p95",
    ],
    "Social response": [
        "gesture_response_success",
        "acknowledgement_clarity",
        "human_aware_approach",
        "bystander_ack",
    ],
    "Motion quality": [
        "sparc",
        "heading_jerk",
        "stability",
        "legibility",
        "behavioral_naturalness",
    ],
}
GROUP_COLORS = {
    "Task performance": "#E8F0F8",
    "Human spacing": "#E6F2F0",
    "Social response": "#F6EEE2",
    "Motion quality": "#EFEAF5",
}


def metric_order() -> list[str]:
    ordered = [metric for metrics in GROUPS.values() for metric in metrics]
    assert tuple(ordered) == SOCIAL_NAVIGATION_METRIC_IDS
    return ordered


def normalized_weight_table() -> pd.DataFrame:
    rows = []
    for axis in SOCIAL_NAVIGATION_AXIS_IDS:
        axis_weights = normalized_axis_weights(axis)
        for metric in SOCIAL_NAVIGATION_METRIC_IDS:
            rows.append(
                {
                    "metric_id": metric,
                    "axis_id": axis,
                    "normalized_weight": axis_weights.get(metric, 0.0),
                }
            )
    return pd.DataFrame(rows)


def bubble_size(weight: float) -> float:
    return 9.0 + 3200.0 * weight


def bubble_label(weight: float) -> str:
    return f"{weight * 100:.0f}%"


def save_figure(fig: plt.Figure) -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        ASSETS_DIR / "fig2_metric_weight_matrix.pdf",
        metadata={"CreationDate": None, "ModDate": None},
    )


def draw_rounded_rect(
    ax, x, y, w, h, facecolor, edgecolor="none", linewidth=0.5, radius=0.08, zorder=0
):
    from matplotlib.patches import FancyBboxPatch

    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle=f"round,pad=0.025,rounding_size={radius}",
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=linewidth,
        zorder=zorder,
    )
    ax.add_patch(patch)
    return patch


def main() -> None:
    try:
        from matplotlib import font_manager

        for font_path in Path("/usr/share/fonts/truetype/croscore").glob("Tinos*.ttf"):
            font_manager.fontManager.addfont(font_path)
    except Exception:
        pass

    weights = normalized_weight_table()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    weights.to_csv(RESULTS_DIR / "metric_weight_matrix.csv", index=False)

    metrics = metric_order()
    y_lookup = {metric: len(metrics) - 1 - index for index, metric in enumerate(metrics)}
    axis_x = {
        "perceived_dexterity": 3.85,
        "perceived_safety": 5.45,
        "perceived_social_awareness": 7.05,
        "impression": 8.66,
    }

    with plt.rc_context(
        {
            "font.family": "Tinos",
            "font.serif": ["Tinos", "Times New Roman", "Liberation Serif", "serif"],
            "font.size": 6.0,
            "axes.linewidth": 0,
        }
    ):
        # A little extra vertical pitch keeps each explanation visually separate
        # from the following row's metric name at full-page and poster scale.
        fig, ax = plt.subplots(figsize=(7.16, 5.05))
        ax.set_xlim(0.0, 9.55)
        ax.set_ylim(-2.32, len(metrics) + 1.85)
        ax.axis("off")

        ax.text(
            4.775,
            len(metrics) + 1.42,
            "How objective sub-metrics flow into human-perception scores",
            ha="center",
            fontsize=11.2,
            fontweight="bold",
            color="#202124",
        )

        ax.text(
            0.50,
            len(metrics) + 0.38,
            "Sub-metric and interpretation",
            fontsize=7.0,
            fontweight="bold",
            color="#30343A",
        )
        for axis, x in axis_x.items():
            ax.text(
                x,
                len(metrics) + 0.40,
                AXIS_LABELS[axis],
                ha="center",
                va="center",
                fontsize=6.9,
                fontweight="bold",
                color=AXIS_COLORS[axis],
            )
            ax.plot(
                [x, x],
                [-0.10, len(metrics) - 0.18],
                color=AXIS_COLORS[axis],
                linewidth=0.7,
                alpha=0.16,
                zorder=1,
            )

        for group_name, group_metrics in GROUPS.items():
            y_values = [y_lookup[m] for m in group_metrics]
            y_min = min(y_values) - 0.46
            y_max = max(y_values) + 0.46
            draw_rounded_rect(
                ax,
                0.06,
                y_min,
                9.18,
                y_max - y_min,
                facecolor=GROUP_COLORS[group_name],
                edgecolor="none",
                radius=0.08,
                zorder=0,
            )
            draw_rounded_rect(
                ax,
                0.12,
                y_min + 0.10,
                0.26,
                (y_max - y_min) - 0.20,
                facecolor="white",
                edgecolor="none",
                radius=0.07,
                zorder=1,
            )
            ax.text(
                0.25,
                (y_min + y_max) / 2,
                group_name,
                fontsize=6.2,
                fontweight="bold",
                color="#68717A",
                ha="center",
                va="center",
                rotation=90,
                zorder=3,
            )

        for metric in metrics:
            y = y_lookup[metric]
            name, note = METRIC_LABELS[metric]
            ax.plot(
                [0.17, 9.16],
                [y - 0.46, y - 0.46],
                color="white",
                linewidth=0.75,
                alpha=0.85,
                zorder=2,
            )
            ax.text(
                0.56,
                y + 0.18,
                name,
                fontsize=7.4,
                fontweight="bold",
                color="#202124",
                va="center",
                zorder=4,
            )
            ax.text(0.56, y - 0.26, note, fontsize=6.1, color="#4F565D", va="center", zorder=4)

            for axis, x in axis_x.items():
                value = float(
                    weights.loc[
                        (weights["metric_id"] == metric) & (weights["axis_id"] == axis),
                        "normalized_weight",
                    ].iloc[0]
                )
                if value == 0.0:
                    ax.text(
                        x,
                        y,
                        "-",
                        ha="center",
                        va="center",
                        fontsize=6.0,
                        color="#AEB7BF",
                        zorder=3,
                    )
                    continue

                ax.scatter(
                    [x],
                    [y],
                    s=bubble_size(value),
                    color=AXIS_COLORS[axis],
                    alpha=0.88,
                    linewidth=0.55,
                    edgecolor="white",
                    zorder=5,
                )
                if value >= 0.03:
                    label_size = 4.4 if value >= 0.05 else 3.8
                    ax.text(
                        x,
                        y,
                        bubble_label(value),
                        ha="center",
                        va="center",
                        fontsize=label_size,
                        color="white",
                        fontweight="bold",
                        zorder=6,
                    )

        legend_y = -1.42
        ax.text(
            0.28,
            legend_y,
            "Dash = zero weight; colored bubble = nonzero influence",
            fontsize=6.1,
            fontweight="bold",
            color="#42484F",
            va="center",
        )
        legend_items = [("5%", 0.05), ("10%", 0.10), ("15%", 0.15)]
        for i, (label, value) in enumerate(legend_items):
            x = 4.40 + i * 0.86
            ax.scatter(
                [x],
                [legend_y],
                s=bubble_size(value),
                color="#7F8992",
                alpha=0.70,
                edgecolor="white",
                linewidth=0.4,
            )
            ax.text(
                x + 0.27,
                legend_y,
                label,
                fontsize=6.0,
                fontweight="bold",
                color="#42484F",
                va="center",
            )

        fig.subplots_adjust(left=0.012, right=0.995, bottom=0.035, top=0.985)
        save_figure(fig)
        plt.close(fig)

    print(f"Saved Figure 2 to {ASSETS_DIR / 'fig2_metric_weight_matrix.pdf'}")


if __name__ == "__main__":
    main()
