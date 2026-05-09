"""
Social navigation benchmark — metric analysis.
Loads data from dummyDataset.json, saves figures to ./plots/ and
copies assets to ../../docs/paper/assets/.
Run dummyDatasetGeneration.py first to populate the JSON.

Scores follow the 0-100 normalisation defined in
docs/specs/social-navigation-metrics.md.
"""

import json
import os
import shutil
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
ASSETS_DIR = os.path.join("..", "docs", "paper", "assets")
os.makedirs(PLOTS_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)

# ── constants ──────────────────────────────────────────────────────────────────
METRICS = [
    "Perceived Dexterity",
    "Perceived Safety",
    "Perceived Social Awareness",
    "Impression",
]
# Short labels for radar axes
METRIC_SHORT = {
    "Perceived Dexterity":         "Dexterity",
    "Perceived Safety":            "Safety",
    "Perceived Social Awareness":  "Social\nAwareness",
    "Impression":                  "Impression",
}
GROUPS = ["Auto Evaluator", "Human (Random Population)", "Human (Robotics Students)"]

# Colorblind-safe palette (Wong 2011)
PALETTE = {
    "Auto Evaluator":            "#0072B2",
    "Human (Random Population)": "#E69F00",
    "Human (Robotics Students)": "#009E73",
}

# ── IEEE-grade matplotlib defaults ────────────────────────────────────────────
plt.rcParams.update({
    "font.family":        "serif",
    "font.serif":         ["Times New Roman", "DejaVu Serif"],
    "mathtext.fontset":   "stix",
    "font.size":          9,
    "axes.titlesize":     10,
    "axes.labelsize":     9,
    "xtick.labelsize":    8,
    "ytick.labelsize":    8,
    "legend.fontsize":    8,
    "figure.dpi":         300,
    "savefig.dpi":        300,
    "savefig.bbox":       "tight",
    "savefig.pad_inches": 0.05,
    "axes.linewidth":     0.8,
    "grid.linewidth":     0.4,
    "lines.linewidth":    1.5,
    "patch.linewidth":    0.6,
    "axes.grid":          False,
})


def data_range(
    arrays: list[pd.Series],
    delta: float = 3.5,
    lo_floor: float = 0.0,
    hi_ceil: float = 100.0,
) -> tuple[float, float]:
    lo = min(float(a.min()) for a in arrays) - delta
    hi = max(float(a.max()) for a in arrays) + delta
    return max(lo_floor, lo), min(hi_ceil, hi)


def nice_ticks(lo: float, hi: float, max_n: int = 6) -> list[float]:
    span = hi - lo
    raw_step = span / max_n
    step = 5.0 if raw_step <= 5 else round(raw_step / 5) * 5
    step = max(step, 5.0)
    start = np.ceil(lo / step) * step
    return [round(start + i * step, 1) for i in range(int((hi - start) / step) + 1)]


def save(fig: Figure, name: str):
    for directory in (PLOTS_DIR, ASSETS_DIR):
        path = os.path.join(directory, f"{name}.pdf")
        fig.savefig(path)
        print(f"  saved → {path}")
    plt.close(fig)


# ── data loading ───────────────────────────────────────────────────────────────
def load_data() -> dict[str, pd.DataFrame]:
    with open(DATA_FILE) as f:
        raw = json.load(f)
    return {g: pd.DataFrame(raw[g]) for g in GROUPS}


# ── 1  radar plot ──────────────────────────────────────────────────────────────
def radar_plot(data_groups: dict[str, pd.DataFrame]):
    short_labels = [METRIC_SHORT[m] for m in METRICS]
    n = len(METRICS)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(3.5, 3.5), subplot_kw={"polar": True})

    for group_name, df in data_groups.items():
        color = PALETTE[group_name]
        values = df[METRICS].mean().tolist()
        values += values[:1]
        ax.plot(angles, values, color=color, linewidth=1.6, zorder=3)
        ax.fill(angles, values, color=color, alpha=0.10)
        ax.scatter(angles[:-1], values[:-1], color=color, s=18, zorder=4)

    all_means = [pd.Series(df[METRICS].mean().values) for df in data_groups.values()]
    r_lo, r_hi = data_range(all_means, delta=4.0)
    ticks = nice_ticks(r_lo, r_hi)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(short_labels, size=8)
    ax.set_ylim(r_lo, r_hi)
    ax.set_yticks(ticks)
    ax.set_yticklabels([f"{t:.0f}" for t in ticks], size=6.5, color="grey")
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

    all_composite = [df["Composite"] for df in data_groups.values()]
    x_lo, x_hi = data_range(all_composite, delta=5.0)
    x = np.linspace(x_lo, x_hi, 400)

    for group_name, df in data_groups.items():
        color = PALETTE[group_name]
        values = df["Composite"]
        ax.hist(values, bins=14, density=True, color=color, alpha=0.18,
                edgecolor="none")
        kde = gaussian_kde(values, bw_method=0.4)
        ax.plot(x, kde(x), color=color, linewidth=1.6, label=group_name)
        ax.axvline(values.mean(), color=color, linewidth=0.9,
                   linestyle="--", alpha=0.7)

    ax.set_xlabel("Composite Score (0–100)")
    ax.set_ylabel("Density")
    ax.set_xlim(x_lo, x_hi)
    ax.set_title("Distribution of Composite Evaluation Scores")
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

    data   = [data_groups[g]["Composite"] for g in GROUPS]
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
    ax.set_ylabel("Composite Score (0–100)")

    all_composite = [data_groups[g]["Composite"] for g in GROUPS]
    y_lo, y_hi = data_range(all_composite, delta=3.0)
    ax.set_ylim(y_lo, y_hi)

    ax.set_title("Composite Score Distribution by Evaluator Group")
    ax.grid(axis="y", linewidth=0.35, alpha=0.5)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    save(fig, "boxplot_global")


# ── 4  metrics table (PDF + LaTeX) ───────────────────────────────────────────
def metrics_table_pdf(data_groups: dict[str, pd.DataFrame]):
    rows = []
    latex_rows = []
    for metric in METRICS + ["Composite"]:
        row = [metric]
        latex_cells = [metric.replace("&", r"\&")]
        for g in GROUPS:
            m = data_groups[g][metric].mean()
            s = data_groups[g][metric].std()
            row.append(f"{m:.1f} ± {s:.1f}")
            latex_cells.append(f"${m:.1f} \\pm {s:.1f}$")
        rows.append(row)
        latex_rows.append(latex_cells)

    col_labels = ["Metric"] + [g.replace(" (", "\n(") for g in GROUPS]

    # ── PDF figure ────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(7.0, 2.8))
    ax.axis("off")

    tbl = ax.table(cellText=rows, colLabels=col_labels,
                   loc="center", cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8)
    tbl.scale(1, 1.55)

    for j in range(len(col_labels)):
        cell = tbl[0, j]
        cell.set_facecolor("#2C3E50")
        cell.set_text_props(color="white", fontweight="bold")
        cell.set_linewidth(0)

    for i, row in enumerate(rows):
        is_composite = row[0] == "Composite"
        for j in range(len(col_labels)):
            cell = tbl[i + 1, j]
            if is_composite:
                cell.set_facecolor("#D5E8D4")
                cell.set_text_props(fontweight="bold")
            elif i % 2 == 0:
                cell.set_facecolor("#F5F5F5")
            else:
                cell.set_facecolor("white")
            cell.set_linewidth(0.3)
            cell.set_edgecolor("0.75")

    ax.set_title(
        "TABLE I — Comparison of Evaluation Scores (Mean ± Std, scale 0–100)",
        fontweight="bold", fontsize=9, pad=10,
    )
    save(fig, "metrics_table")

    # ── LaTeX table ───────────────────────────────────────────────────────────
    short_groups = ["Auto Evaluator", "Human (Random Pop.)", "Human (Robotics St.)"]
    header = " & ".join(["\\textbf{Metric}"] +
                         [f"\\textbf{{{g}}}" for g in short_groups])
    lines = [
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        header + r" \\",
        r"\midrule",
    ]
    for i, cells in enumerate(latex_rows):
        if cells[0] == "Composite":
            lines.append(r"\midrule")
            lines.append(r"\textbf{" + cells[0] + "} & " +
                         " & ".join(r"\textbf{" + c + "}" for c in cells[1:]) + r" \\")
        else:
            lines.append(" & ".join(cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]

    tex_path = os.path.join(ASSETS_DIR, "metrics_table.tex")
    with open(tex_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  saved → {tex_path}")


# ── 5  statistical analysis (PDF) ────────────────────────────────────────────
def statistical_analysis_pdf(data_groups: dict[str, pd.DataFrame]):
    auto = data_groups["Auto Evaluator"]["Composite"]
    rand = data_groups["Human (Random Population)"]["Composite"]
    robo = data_groups["Human (Robotics Students)"]["Composite"]

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

    tbl = ax.table(cellText=rows, colLabels=col_labels,
                   loc="center", cellLoc="center")
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
        "TABLE II — Welch's Independent t-Test Results (Composite Score)",
        fontweight="bold", fontsize=9, pad=10,
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
    print("Done.")


if __name__ == "__main__":
    main()
