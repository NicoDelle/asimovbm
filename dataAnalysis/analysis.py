"""
Social navigation benchmark — metric analysis.
Loads data from dummyDataset.json and saves all figures/tables to ./plots/.
Run dummyDatasetGeneration.py first to populate the JSON.
"""

import json
import os
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.figure import Figure
from scipy.stats import gaussian_kde, ttest_ind

matplotlib.use("Agg")  

# ── paths ──────────────────────────────────────────────────────────────────────
DATA_FILE  = "dummyDataset.json"
PLOTS_DIR  = "plots"
os.makedirs(PLOTS_DIR, exist_ok=True)

# ── constants ──────────────────────────────────────────────────────────────────
METRICS = ["Safety", "Naturalness", "Responsiveness", "Predictability", "Comfort"]
GROUPS  = ["Auto Evaluator", "Human (Random Population)", "Human (Robotics Students)"]

PALETTE = {
    "Auto Evaluator":            "#0072B2",   # blue
    "Human (Random Population)": "#E69F00",   # amber
    "Human (Robotics Students)": "#009E73",   # green
}

plt.rcParams.update({
    # fonts
    "font.family":       "serif",
    "font.serif":        ["Times New Roman", "DejaVu Serif"],
    "mathtext.fontset":  "stix",
    # sizes
    "font.size":         9,
    "axes.titlesize":    10,
    "axes.labelsize":    9,
    "xtick.labelsize":   8,
    "ytick.labelsize":   8,
    "legend.fontsize":   8,
    # figure
    "figure.dpi":        300,
    "savefig.dpi":       300,
    "savefig.bbox":      "tight",
    "savefig.pad_inches": 0.05,
    # lines / axes
    "axes.linewidth":    0.8,
    "grid.linewidth":    0.4,
    "lines.linewidth":   1.5,
    "patch.linewidth":   0.6,
    "axes.grid":         False,
})


def data_range(
    arrays: list[pd.Series],
    delta: float = 0.35,
    lo_floor: float = 0.0,
    hi_ceil: float = 10.0,
) -> tuple[float, float]:
    """Return (lo, hi) clamped to [lo_floor, hi_ceil] with a padding delta."""
    lo = min(float(a.min()) for a in arrays) - delta
    hi = max(float(a.max()) for a in arrays) + delta
    return max(lo_floor, lo), min(hi_ceil, hi)


def nice_ticks(lo: float, hi: float, max_n: int = 6) -> list[float]:
    """Return evenly-spaced round ticks that span [lo, hi]."""
    span = hi - lo
    raw_step = span / max_n
    # round step up to nearest 0.5 or 1
    step = 0.5 if raw_step <= 0.5 else round(raw_step * 2) / 2
    step = max(step, 0.5)
    start = np.ceil(lo / step) * step
    return [round(start + i * step, 2) for i in range(int((hi - start) / step) + 1)]


def save(fig: Figure, name: str):
    path = os.path.join(PLOTS_DIR, f"{name}.pdf")
    fig.savefig(path)
    plt.close(fig)
    print(f"  saved → {path}")


# ── data loading ───────────────────────────────────────────────────────────────
def load_data() -> dict[str, pd.DataFrame]:
    with open(DATA_FILE) as f:
        raw = json.load(f)
    return {g: pd.DataFrame(raw[g]) for g in GROUPS}


# ── 1  radar plot ──────────────────────────────────────────────────────────────
def radar_plot(data_groups: dict[str, pd.DataFrame]):
    labels = METRICS
    n = len(labels)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(3.5, 3.5), subplot_kw={"polar": True})

    for group_name, df in data_groups.items():
        color = PALETTE[group_name]
        values = df[labels].mean().tolist()
        values += values[:1]

        ax.plot(angles, values, color=color, linewidth=1.6, zorder=3)
        ax.fill(angles, values, color=color, alpha=0.10)
        ax.scatter(angles[:-1], values[:-1], color=color, s=18, zorder=4)

    # zoom to the range actually used by the data
    all_means = [
        pd.Series(df[labels].mean().values) for df in data_groups.values()
    ]
    r_lo, r_hi = data_range(all_means, delta=0.4)
    ticks = nice_ticks(r_lo, r_hi)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, size=8)
    ax.set_ylim(r_lo, r_hi)
    ax.set_yticks(ticks)
    ax.set_yticklabels([f"{t:.1f}" for t in ticks], size=6.5, color="grey")
    ax.grid(color="grey", linewidth=0.35, alpha=0.5)
    ax.spines["polar"].set_linewidth(0.6)

    two_line = {
        "Auto Evaluator":            "Auto\nEvaluator",
        "Human (Random Population)": "Human\n(Random Population)",
        "Human (Robotics Students)": "Human\n(Robotics Students)",
    }
    handles = [
        mpatches.Patch(color=PALETTE[g], label=two_line[g], alpha=0.75)
        for g in GROUPS
    ]
    ax.legend(
        handles=handles,
        loc="lower right",
        bbox_to_anchor=(1.55, -0.10),
        frameon=True,
        framealpha=0.9,
        edgecolor="0.7",
        handlelength=1.2,
        handleheight=1.0,
    )
    ax.set_title("Perception Metrics — Group Comparison", pad=14)

    save(fig, "radar_plot")


# ── 2  distribution shift ──────────────────────────────────────────────────────
def distribution_shift_plot(data_groups: dict[str, pd.DataFrame]):
    fig, ax = plt.subplots(figsize=(3.5, 2.6))

    all_global = [df["Global"] for df in data_groups.values()]
    x_lo, x_hi = data_range(all_global, delta=0.5)
    x = np.linspace(x_lo, x_hi, 400)

    for group_name, df in data_groups.items():
        color = PALETTE[group_name]
        values = df["Global"]
        ax.hist(values, bins=14, density=True, color=color, alpha=0.18,
                edgecolor="none")
        kde = gaussian_kde(values, bw_method=0.4)
        ax.plot(x, kde(x), color=color, linewidth=1.6, label=group_name)
        ax.axvline(values.mean(), color=color, linewidth=0.9,
                   linestyle="--", alpha=0.7)

    ax.set_xlabel("Global Score")
    ax.set_ylabel("Density")
    ax.set_xlim(x_lo, x_hi)
    ax.set_title("Distribution of Global Evaluation Scores")
    ax.grid(axis="y", linewidth=0.35, alpha=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(
        loc="upper right",
        frameon=True,
        framealpha=0.9,
        edgecolor="0.7",
        handlelength=1.2,
    )

    save(fig, "distribution_shift")


# ── 3  boxplot ────────────────────────────────────────────────────────────────
def boxplot_global(data_groups: dict[str, pd.DataFrame]):
    fig, ax = plt.subplots(figsize=(3.5, 2.8))

    data   = [data_groups[g]["Global"] for g in GROUPS]
    colors = [PALETTE[g] for g in GROUPS]

    bp = ax.boxplot(
        data,
        patch_artist=True,
        showfliers=True,
        flierprops=dict(marker="o", markersize=3, alpha=0.5, linestyle="none"),
        medianprops=dict(color="white", linewidth=1.6),
        whiskerprops=dict(linewidth=0.9),
        capprops=dict(linewidth=0.9),
        widths=0.45,
    )

    for patch, color in zip(bp["boxes"], colors):
        patch.set(facecolor=color, alpha=0.75)  # type: ignore[union-attr]
    for flier, color in zip(bp["fliers"], colors):
        flier.set(markerfacecolor=color, markeredgecolor=color)  # type: ignore[union-attr]

    short_labels = ["Auto\nEvaluator", "Human\n(Random)", "Human\n(Robotics)"]
    ax.set_xticks([1, 2, 3])
    ax.set_xticklabels(short_labels, size=8)
    all_global = [data_groups[g]["Global"] for g in GROUPS]
    y_lo, y_hi = data_range(all_global, delta=0.3)
    ax.set_ylabel("Global Score")
    ax.set_ylim(y_lo, y_hi)
    ax.set_title("Global Score Distribution by Evaluator Group")
    ax.grid(axis="y", linewidth=0.35, alpha=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    save(fig, "boxplot_global")


# ── 4  metrics table (PDF) ────────────────────────────────────────────────────
def metrics_table_pdf(data_groups: dict[str, pd.DataFrame]):
    rows = []
    for metric in METRICS + ["Global"]:
        row = [metric]
        for g in GROUPS:
            m = data_groups[g][metric].mean()
            s = data_groups[g][metric].std()
            row.append(f"{m:.2f} ± {s:.2f}")
        rows.append(row)

    col_labels = ["Metric"] + [g.replace(" (", "\n(") for g in GROUPS]

    fig, ax = plt.subplots(figsize=(7.0, 2.8))
    ax.axis("off")

    tbl = ax.table(
        cellText=rows,
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    tbl.scale(1, 1.55)

    for j in range(len(col_labels)):
        cell = tbl[0, j]
        cell.set_facecolor("#2C3E50")
        cell.set_text_props(color="white", fontweight="bold")
        cell.set_linewidth(0)

    # alternate row shading + highlight Global row
    for i, row in enumerate(rows):
        is_global = row[0] == "Global"
        for j in range(len(col_labels)):
            cell = tbl[i + 1, j]
            if is_global:
                cell.set_facecolor("#D5E8D4")
                cell.set_text_props(fontweight="bold")
            elif i % 2 == 0:
                cell.set_facecolor("#F5F5F5")
            else:
                cell.set_facecolor("white")
            cell.set_linewidth(0.3)
            cell.set_edgecolor("0.75")

    ax.set_title(
        "TABLE I — Comparison of Evaluation Scores (Mean ± Std)",
        fontweight="bold", fontsize=9, pad=10
    )

    save(fig, "metrics_table")


# ── 5  statistical analysis (PDF) ────────────────────────────────────────────
def statistical_analysis_pdf(data_groups: dict[str, pd.DataFrame]):
    auto = data_groups["Auto Evaluator"]["Global"]
    rand = data_groups["Human (Random Population)"]["Global"]
    robo = data_groups["Human (Robotics Students)"]["Global"]

    tests = [
        ("Auto Evaluator  vs  Human (Random Population)", auto, rand),
        ("Auto Evaluator  vs  Human (Robotics Students)", auto, robo),
        ("Human (Random)  vs  Human (Robotics Students)", rand, robo),
    ]

    rows = []
    for name, a, b in tests:
        result = ttest_ind(a, b)
        t, p = float(result[0]), float(result[1])  # type: ignore[arg-type]
        sig = "yes" if p < 0.05 else "no"
        rows.append([name, f"{t:.3f}", f"{p:.4f}", sig])

    col_labels = ["Comparison", "t-statistic", "p-value", "p < 0.05"]

    fig, ax = plt.subplots(figsize=(7.0, 1.9))
    ax.axis("off")

    tbl = ax.table(
        cellText=rows,
        colLabels=col_labels,
        loc="center",
        cellLoc="center",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    tbl.scale(1, 1.7)

    for j in range(len(col_labels)):
        cell = tbl[0, j]
        cell.set_facecolor("#2C3E50")
        cell.set_text_props(color="white", fontweight="bold")
        cell.set_linewidth(0)

    for i, row in enumerate(rows):
        is_sig = row[3] == "yes"
        for j in range(len(col_labels)):
            cell = tbl[i + 1, j]
            cell.set_facecolor("#FFF3CD" if is_sig else "white")
            cell.set_linewidth(0.3)
            cell.set_edgecolor("0.75")

        tbl[i + 1, 0].set_text_props(ha="left")

    ax.set_title(
        "TABLE II — Welch's Independent t-Test Results (Global Score)",
        fontweight="bold", fontsize=9, pad=10
    )

    save(fig, "statistical_analysis")


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    data_groups = load_data()
    print("Running analysis …")
    radar_plot(data_groups)
    distribution_shift_plot(data_groups)
    boxplot_global(data_groups)
    metrics_table_pdf(data_groups)
    statistical_analysis_pdf(data_groups)
    print("Done. All outputs written to ./plots/")


if __name__ == "__main__":
    main()
