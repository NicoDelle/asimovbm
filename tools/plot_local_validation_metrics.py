#!/usr/bin/env python3
"""Build comparison plots for local-validation metric artifacts.

The local runner writes one authoritative ``report.json`` and ``manifest.json``
per run directory, plus one or more CSV exports. This script treats the JSON
pair as the condition authority and uses the latest CSV row matching the
manifest episode for low-level metric columns.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


AXES = [
    "perceived_dexterity",
    "perceived_safety",
    "perceived_social_awareness",
    "impression",
]

CSV_METADATA_COLUMNS = {
    "run_id",
    "episode_id",
    "episode_title",
    "iteration",
    "tier_id",
    "technical_valid",
    "terminal_status",
}

EPISODE_LABELS = {
    "g1_point_to_point_open": "Ep1 open",
    "g1_point_to_point_static_obstacles": "Ep2 static",
    "g1_point_to_point_dynamic_npcs": "Ep3 dynamic NPCs",
}

EPISODE_ORDER = {
    "g1_point_to_point_open": 1,
    "g1_point_to_point_static_obstacles": 2,
    "g1_point_to_point_dynamic_npcs": 3,
}

POLICY_LABELS = {
    "A": "Policy A",
    "B": "Policy B",
}

PERSPECTIVE_ORDER = {"arrival": 1, "bystander": 2}

DISPLAY_NAMES = {
    "perceived_dexterity": "dexterity",
    "perceived_safety": "safety",
    "perceived_social_awareness": "social",
    "impression": "impression",
    "task_success_rate": "task success",
    "task_completion_time": "completion",
    "comfort_aware_path_efficiency": "path eff.",
    "hesitation": "hesitation",
    "min_human_robot_distance": "min dist",
    "proxemic_intrusion_dose": "proxemic dose",
    "speed_near_humans_p95": "speed near p95",
    "gesture_response_success": "gesture response",
    "acknowledgement_clarity": "ack clarity",
    "human_aware_approach": "approach",
    "bystander_ack": "bystander ack",
    "sparc": "SPARC",
    "heading_jerk": "heading jerk",
    "stability": "stability",
    "legibility": "legibility",
    "behavioral_naturalness": "naturalness",
}


@dataclass(frozen=True)
class Condition:
    run_dir: Path
    run_id: str
    q_bucket: str
    folder_name: str
    policy_code: str
    policy_id: str
    perspective: str
    episode_id: str
    episode_label: str
    selected_csv: Path | None
    csv_count: int
    matching_csv_count: int
    ignored_csv_count: int
    axes: dict[str, float | None]
    axis_statuses: dict[str, str]
    axis_confidences: dict[str, str]
    metrics: dict[str, float | None]
    metric_statuses: dict[str, str]
    technical_valid: str
    terminal_status: str


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number


def _policy_code(policy_id: str, folder_name: str) -> str:
    folded = f"{policy_id} {folder_name}".lower()
    if "policya" in folded or "unitree" in folded:
        return "A"
    if "policyb" in folded or "asap" in folded:
        return "B"
    return policy_id or folder_name


def _episode_label(episode_id: str) -> str:
    return EPISODE_LABELS.get(episode_id, episode_id)


def _condition_sort_key(condition: Condition) -> tuple[int, int, int, str]:
    return (
        PERSPECTIVE_ORDER.get(condition.perspective, 99),
        EPISODE_ORDER.get(condition.episode_id, 99),
        1 if condition.policy_code == "A" else 2,
        condition.run_id,
    )


def _metric_sort_key(metric_id: str) -> tuple[int, str]:
    preferred = [
        "task_success_rate",
        "task_completion_time",
        "comfort_aware_path_efficiency",
        "hesitation",
        "sparc",
        "heading_jerk",
        "stability",
        "legibility",
        "acknowledgement_clarity",
        "min_human_robot_distance",
        "proxemic_intrusion_dose",
        "speed_near_humans_p95",
        "human_aware_approach",
        "bystander_ack",
        "behavioral_naturalness",
        "gesture_response_success",
    ]
    try:
        return (preferred.index(metric_id), metric_id)
    except ValueError:
        return (len(preferred), metric_id)


def _display_name(metric_id: str) -> str:
    return DISPLAY_NAMES.get(metric_id, metric_id)


def _load_csv_rows(run_dir: Path) -> list[tuple[Path, dict[str, str]]]:
    rows: list[tuple[Path, dict[str, str]]] = []
    for csv_path in sorted(run_dir.glob("episode-metrics-*.csv")):
        with csv_path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                rows.append((csv_path, row))
    return rows


def _feature_statuses(report: dict[str, Any]) -> dict[str, str]:
    blocks = report.get("behavioral_metrics", {}).get("episode_blocks", [])
    if not blocks:
        return {}
    features = blocks[0].get("features", {})
    return {feature_id: str(payload.get("status", "")) for feature_id, payload in features.items()}


def _load_condition(run_dir: Path, root: Path, warnings: list[str]) -> Condition:
    manifest = _read_json(run_dir / "manifest.json")
    report = _read_json(run_dir / "report.json")
    episode = (manifest.get("episodes") or [{}])[0]
    episode_blocks = report.get("behavioral_metrics", {}).get("episode_blocks", [])

    episode_id = ""
    canonical_episode_ids = manifest.get("canonical_episode_ids") or []
    if canonical_episode_ids:
        episode_id = canonical_episode_ids[0]
    elif episode.get("id"):
        episode_id = str(episode["id"])
    elif episode_blocks:
        episode_id = str(episode_blocks[0].get("episode_id", ""))

    policy_id = str(episode.get("policy_id", ""))
    policy_code = _policy_code(policy_id, run_dir.name)
    perspective = str(manifest.get("camera_view") or "")

    axes_payload = report.get("behavioral_metrics", {}).get("axes", {})
    axes = {axis_id: _float_or_none(axes_payload.get(axis_id, {}).get("score")) for axis_id in AXES}
    axis_statuses = {axis_id: str(axes_payload.get(axis_id, {}).get("status", "")) for axis_id in AXES}
    axis_confidences = {
        axis_id: str(axes_payload.get(axis_id, {}).get("confidence", "")) for axis_id in AXES
    }

    csv_rows = _load_csv_rows(run_dir)
    matching = [(path, row) for path, row in csv_rows if row.get("episode_id") == episode_id]
    mismatched = [(path, row) for path, row in csv_rows if row.get("episode_id") != episode_id]
    if mismatched:
        rel = run_dir.relative_to(root)
        names = ", ".join(
            f"{path.name}:{row.get('episode_id', '')}" for path, row in mismatched[:4]
        )
        warnings.append(
            f"{rel} contains {len(mismatched)} CSV row(s) that do not match manifest episode "
            f"{episode_id}: {names}"
        )
    if len(matching) > 1:
        rel = run_dir.relative_to(root)
        warnings.append(
            f"{rel} contains {len(matching)} matching CSV rows; using {matching[-1][0].name} "
            "for condition-level metric plots."
        )

    selected_csv: Path | None = None
    selected_row: dict[str, str] = {}
    if matching:
        selected_csv, selected_row = matching[-1]
    elif csv_rows:
        selected_csv, selected_row = csv_rows[-1]
        warnings.append(
            f"{run_dir.relative_to(root)} has no CSV row matching {episode_id}; using "
            f"{selected_csv.name} as a fallback."
        )

    metrics = {
        column: _float_or_none(value)
        for column, value in selected_row.items()
        if column not in CSV_METADATA_COLUMNS
    }
    metrics = {key: value for key, value in metrics.items() if value is not None}

    return Condition(
        run_dir=run_dir,
        run_id=str(report.get("run_id") or manifest.get("run_id") or run_dir.name),
        q_bucket=run_dir.parent.name,
        folder_name=run_dir.name,
        policy_code=policy_code,
        policy_id=policy_id,
        perspective=perspective,
        episode_id=episode_id,
        episode_label=_episode_label(episode_id),
        selected_csv=selected_csv,
        csv_count=len(csv_rows),
        matching_csv_count=len(matching),
        ignored_csv_count=len(mismatched),
        axes=axes,
        axis_statuses=axis_statuses,
        axis_confidences=axis_confidences,
        metrics=metrics,
        metric_statuses=_feature_statuses(report),
        technical_valid=str(selected_row.get("technical_valid", "")),
        terminal_status=str(selected_row.get("terminal_status", "")),
    )


def load_conditions(root: Path) -> tuple[list[Condition], list[str]]:
    warnings: list[str] = []
    run_dirs = sorted(path.parent for path in root.glob("q*/policy*/report.json"))
    conditions = [
        _load_condition(run_dir, root, warnings)
        for run_dir in run_dirs
        if (run_dir / "manifest.json").exists()
    ]

    seen: dict[tuple[str, str, str], Condition] = {}
    for condition in conditions:
        key = (condition.policy_code, condition.perspective, condition.episode_id)
        if key in seen:
            warnings.append(
                "Duplicate condition key "
                f"{key}: {seen[key].run_dir.relative_to(root)} and {condition.run_dir.relative_to(root)}"
            )
        seen[key] = condition

    return sorted(conditions, key=_condition_sort_key), warnings


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _format_value(value: float | None, signed: bool = False) -> str:
    if value is None:
        return "NA"
    if signed:
        return f"{value:+.3f}"
    return f"{value:.3f}"


def _score_color(value: float | None) -> str:
    if value is None:
        return "#e5e7eb"
    value = max(0.0, min(1.0, value))
    # Blend from off-white to teal.
    start = (248, 250, 252)
    end = (15, 118, 110)
    rgb = tuple(round(start[i] + (end[i] - start[i]) * value) for i in range(3))
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def _delta_color(value: float | None, max_abs: float) -> str:
    if value is None:
        return "#e5e7eb"
    if max_abs <= 0:
        max_abs = 1.0
    strength = min(abs(value) / max_abs, 1.0)
    neutral = (248, 250, 252)
    positive = (37, 99, 235)
    negative = (220, 38, 38)
    target = positive if value >= 0 else negative
    rgb = tuple(round(neutral[i] + (target[i] - neutral[i]) * strength) for i in range(3))
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def _text_color(fill: str, value: float | None, delta: bool = False, max_abs: float = 1.0) -> str:
    if value is None:
        return "#475569"
    if delta:
        return "#ffffff" if abs(value) >= max_abs * 0.55 else "#0f172a"
    return "#ffffff" if value >= 0.55 else "#0f172a"


def _svg_text(text: str) -> str:
    return html.escape(text, quote=False)


def render_heatmap(
    *,
    title: str,
    row_labels: list[str],
    column_labels: list[str],
    values: dict[tuple[str, str], float | None],
    output_path: Path,
    mode: str,
    note: str,
) -> None:
    label_w = 230
    cell_w = 116
    cell_h = 38
    header_h = 82
    footer_h = 34
    width = label_w + cell_w * len(column_labels) + 32
    height = header_h + cell_h * len(row_labels) + footer_h
    all_values = [abs(value) for value in values.values() if value is not None]
    max_abs = max(all_values) if all_values else 1.0

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        "<style>"
        "text{font-family:Inter,Arial,sans-serif;}"
        ".title{font-size:20px;font-weight:700;fill:#0f172a;}"
        ".note{font-size:12px;fill:#475569;}"
        ".label{font-size:12px;fill:#0f172a;}"
        ".col{font-size:11px;font-weight:700;fill:#334155;}"
        ".value{font-size:12px;font-weight:700;}"
        "</style>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text class="title" x="16" y="28">{_svg_text(title)}</text>',
        f'<text class="note" x="16" y="50">{_svg_text(note)}</text>',
    ]

    y0 = header_h
    for col_index, col_label in enumerate(column_labels):
        x = label_w + col_index * cell_w
        parts.append(
            f'<text class="col" x="{x + cell_w / 2}" y="{header_h - 12}" '
            f'text-anchor="middle">{_svg_text(col_label)}</text>'
        )

    for row_index, row_label in enumerate(row_labels):
        y = y0 + row_index * cell_h
        parts.append(
            f'<text class="label" x="16" y="{y + 24}">{_svg_text(row_label)}</text>'
        )
        for col_index, col_label in enumerate(column_labels):
            x = label_w + col_index * cell_w
            value = values.get((row_label, col_label))
            if mode == "delta":
                fill = _delta_color(value, max_abs=max_abs)
                label = _format_value(value, signed=True)
                text_fill = _text_color(fill, value, delta=True, max_abs=max_abs)
            else:
                fill = _score_color(value)
                label = _format_value(value)
                text_fill = _text_color(fill, value)
            parts.extend(
                [
                    f'<rect x="{x}" y="{y}" width="{cell_w - 2}" height="{cell_h - 2}" '
                    f'rx="4" fill="{fill}" stroke="#ffffff"/>',
                    f'<text class="value" x="{x + cell_w / 2}" y="{y + 24}" '
                    f'text-anchor="middle" fill="{text_fill}">{label}</text>',
                ]
            )

    parts.append(
        f'<text class="note" x="16" y="{height - 12}">'
        f'{_svg_text("Grey cells mean missing or insufficient evidence in the selected artifact.")}</text>'
    )
    parts.append("</svg>")
    output_path.write_text("\n".join(parts))


def render_metric_heatmap(conditions: list[Condition], output_path: Path) -> None:
    metric_ids = sorted(
        {metric_id for condition in conditions for metric_id in condition.metrics},
        key=_metric_sort_key,
    )
    column_labels = [_display_name(metric_id) for metric_id in metric_ids]
    row_labels = [
        f"{condition.episode_label} | {POLICY_LABELS.get(condition.policy_code, condition.policy_code)} | "
        f"{condition.perspective}"
        for condition in conditions
    ]
    values: dict[tuple[str, str], float | None] = {}
    for condition, row_label in zip(conditions, row_labels, strict=True):
        for metric_id, column_label in zip(metric_ids, column_labels, strict=True):
            values[(row_label, column_label)] = condition.metrics.get(metric_id)
    render_heatmap(
        title="Normalized Feature Metric Scores",
        row_labels=row_labels,
        column_labels=column_labels,
        values=values,
        output_path=output_path,
        mode="score",
        note="Rows are authoritative run conditions; values come from the selected matching CSV export.",
    )


def _axis_rows(conditions: list[Condition]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for condition in conditions:
        for axis_id in AXES:
            rows.append(
                {
                    "q_bucket": condition.q_bucket,
                    "run_id": condition.run_id,
                    "run_dir": str(condition.run_dir),
                    "policy": POLICY_LABELS.get(condition.policy_code, condition.policy_code),
                    "policy_code": condition.policy_code,
                    "policy_id": condition.policy_id,
                    "perspective": condition.perspective,
                    "episode": condition.episode_label,
                    "episode_id": condition.episode_id,
                    "axis": axis_id,
                    "score": condition.axes.get(axis_id),
                    "status": condition.axis_statuses.get(axis_id),
                    "confidence": condition.axis_confidences.get(axis_id),
                }
            )
    return rows


def _metric_rows(conditions: list[Condition]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for condition in conditions:
        for metric_id, score in sorted(condition.metrics.items(), key=lambda item: _metric_sort_key(item[0])):
            rows.append(
                {
                    "q_bucket": condition.q_bucket,
                    "run_id": condition.run_id,
                    "run_dir": str(condition.run_dir),
                    "policy": POLICY_LABELS.get(condition.policy_code, condition.policy_code),
                    "policy_code": condition.policy_code,
                    "policy_id": condition.policy_id,
                    "perspective": condition.perspective,
                    "episode": condition.episode_label,
                    "episode_id": condition.episode_id,
                    "metric": metric_id,
                    "score": score,
                    "status": condition.metric_statuses.get(metric_id, ""),
                    "selected_csv": str(condition.selected_csv) if condition.selected_csv else "",
                }
            )
    return rows


def _summary_rows(conditions: list[Condition]) -> list[dict[str, Any]]:
    metric_ids = sorted(
        {metric_id for condition in conditions for metric_id in condition.metrics},
        key=_metric_sort_key,
    )
    rows: list[dict[str, Any]] = []
    for condition in conditions:
        row: dict[str, Any] = {
            "q_bucket": condition.q_bucket,
            "run_id": condition.run_id,
            "run_dir": str(condition.run_dir),
            "folder_name": condition.folder_name,
            "policy": POLICY_LABELS.get(condition.policy_code, condition.policy_code),
            "policy_code": condition.policy_code,
            "policy_id": condition.policy_id,
            "perspective": condition.perspective,
            "episode": condition.episode_label,
            "episode_id": condition.episode_id,
            "selected_csv": str(condition.selected_csv) if condition.selected_csv else "",
            "csv_count": condition.csv_count,
            "matching_csv_count": condition.matching_csv_count,
            "ignored_csv_count": condition.ignored_csv_count,
            "technical_valid": condition.technical_valid,
            "terminal_status": condition.terminal_status,
        }
        for axis_id in AXES:
            row[f"axis_{axis_id}"] = condition.axes.get(axis_id)
        for metric_id in metric_ids:
            row[f"metric_{metric_id}"] = condition.metrics.get(metric_id)
        rows.append(row)
    return rows


def _policy_delta_rows(conditions: list[Condition]) -> list[dict[str, Any]]:
    by_key = {
        (condition.episode_id, condition.perspective, condition.policy_code, axis_id): score
        for condition in conditions
        for axis_id, score in condition.axes.items()
    }
    rows: list[dict[str, Any]] = []
    for episode_id in sorted({condition.episode_id for condition in conditions}, key=lambda item: EPISODE_ORDER.get(item, 99)):
        for perspective in sorted(
            {condition.perspective for condition in conditions}, key=lambda item: PERSPECTIVE_ORDER.get(item, 99)
        ):
            for axis_id in AXES:
                a = by_key.get((episode_id, perspective, "A", axis_id))
                b = by_key.get((episode_id, perspective, "B", axis_id))
                rows.append(
                    {
                        "episode": _episode_label(episode_id),
                        "episode_id": episode_id,
                        "perspective": perspective,
                        "axis": axis_id,
                        "policy_a": a,
                        "policy_b": b,
                        "delta_policy_b_minus_a": None if a is None or b is None else b - a,
                    }
                )
    return rows


def _perspective_delta_rows(conditions: list[Condition]) -> list[dict[str, Any]]:
    by_key = {
        (condition.episode_id, condition.policy_code, condition.perspective, axis_id): score
        for condition in conditions
        for axis_id, score in condition.axes.items()
    }
    rows: list[dict[str, Any]] = []
    for episode_id in sorted({condition.episode_id for condition in conditions}, key=lambda item: EPISODE_ORDER.get(item, 99)):
        for policy_code in ["A", "B"]:
            for axis_id in AXES:
                arrival = by_key.get((episode_id, policy_code, "arrival", axis_id))
                bystander = by_key.get((episode_id, policy_code, "bystander", axis_id))
                rows.append(
                    {
                        "episode": _episode_label(episode_id),
                        "episode_id": episode_id,
                        "policy": POLICY_LABELS.get(policy_code, policy_code),
                        "policy_code": policy_code,
                        "axis": axis_id,
                        "arrival": arrival,
                        "bystander": bystander,
                        "delta_bystander_minus_arrival": None
                        if arrival is None or bystander is None
                        else bystander - arrival,
                    }
                )
    return rows


def _top_deltas(rows: list[dict[str, Any]], value_key: str, limit: int = 8) -> list[dict[str, Any]]:
    with_values = [row for row in rows if row.get(value_key) is not None]
    return sorted(with_values, key=lambda row: abs(float(row[value_key])), reverse=True)[:limit]


def _html_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return "<p>No rows.</p>"
    header = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    body_parts = []
    for row in rows:
        cells = []
        for column in columns:
            value = row.get(column, "")
            if isinstance(value, float):
                value = _format_value(value, signed=column.startswith("delta"))
            elif value is None:
                value = "NA"
            cells.append(f"<td>{html.escape(str(value))}</td>")
        body_parts.append(f"<tr>{''.join(cells)}</tr>")
    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body_parts)}</tbody></table>"


def _render_html(
    output_dir: Path,
    conditions: list[Condition],
    warnings: list[str],
    policy_deltas: list[dict[str, Any]],
    perspective_deltas: list[dict[str, Any]],
) -> None:
    warning_items = "".join(f"<li>{html.escape(warning)}</li>" for warning in warnings)
    condition_rows = [
        {
            "run": condition.run_id,
            "episode": condition.episode_label,
            "policy": POLICY_LABELS.get(condition.policy_code, condition.policy_code),
            "perspective": condition.perspective,
            "selected_csv": condition.selected_csv.name if condition.selected_csv else "",
            "csv_rows": condition.csv_count,
            "ignored": condition.ignored_csv_count,
        }
        for condition in conditions
    ]
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Local Validation Metric Comparisons</title>
  <style>
    body {{
      margin: 32px;
      font-family: Inter, Arial, sans-serif;
      color: #0f172a;
      background: #f8fafc;
    }}
    main {{ max-width: 1180px; margin: 0 auto; }}
    h1 {{ font-size: 30px; margin-bottom: 8px; }}
    h2 {{ margin-top: 32px; font-size: 20px; }}
    p, li {{ color: #475569; line-height: 1.5; }}
    .card {{
      background: white;
      border: 1px solid #e2e8f0;
      border-radius: 8px;
      padding: 18px;
      margin: 18px 0;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }}
    img {{ max-width: 100%; height: auto; display: block; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      background: white;
    }}
    th, td {{
      border-bottom: 1px solid #e2e8f0;
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ color: #334155; font-size: 12px; text-transform: uppercase; letter-spacing: 0.02em; }}
    code {{ background: #e2e8f0; padding: 2px 5px; border-radius: 4px; }}
    .links a {{ margin-right: 16px; }}
  </style>
</head>
<body>
<main>
  <h1>Local Validation Metric Comparisons</h1>
  <p>
    Axis scores come from each run's authoritative <code>report.json</code>.
    Low-level feature metric scores come from the latest CSV row that matches the
    manifest episode for that folder. Because these are deterministic validation
    artifacts rather than independent participant samples, the comparison uses
    paired within-episode deltas instead of p-values.
  </p>

  <div class="card links">
    <strong>Data exports:</strong>
    <a href="condition_summary.csv">condition_summary.csv</a>
    <a href="axis_scores.csv">axis_scores.csv</a>
    <a href="metric_scores.csv">metric_scores.csv</a>
    <a href="policy_deltas.csv">policy_deltas.csv</a>
    <a href="perspective_deltas.csv">perspective_deltas.csv</a>
  </div>

  <h2>Axis Score Overview</h2>
  <div class="card"><img src="axis_score_heatmap.svg" alt="Axis score heatmap"></div>

  <h2>Policy Comparison</h2>
  <p>Positive cells mean Policy B scored higher than Policy A for the same episode and perspective.</p>
  <div class="card"><img src="policy_delta_heatmap.svg" alt="Policy delta heatmap"></div>
  <div class="card">
    <h3>Largest policy deltas</h3>
    {_html_table(_top_deltas(policy_deltas, "delta_policy_b_minus_a"), ["episode", "perspective", "axis", "policy_a", "policy_b", "delta_policy_b_minus_a"])}
  </div>

  <h2>Perspective Comparison</h2>
  <p>Positive cells mean the bystander perspective scored higher than arrival for the same episode and policy.</p>
  <div class="card"><img src="perspective_delta_heatmap.svg" alt="Perspective delta heatmap"></div>
  <div class="card">
    <h3>Largest perspective deltas</h3>
    {_html_table(_top_deltas(perspective_deltas, "delta_bystander_minus_arrival"), ["episode", "policy", "axis", "arrival", "bystander", "delta_bystander_minus_arrival"])}
  </div>

  <h2>Feature Metric Scores</h2>
  <div class="card"><img src="feature_metric_heatmap.svg" alt="Feature metric heatmap"></div>

  <h2>Included Conditions</h2>
  <div class="card">
    {_html_table(condition_rows, ["run", "episode", "policy", "perspective", "selected_csv", "csv_rows", "ignored"])}
  </div>

  <h2>Data Notes</h2>
  <div class="card">
    <ul>{warning_items or "<li>No data warnings.</li>"}</ul>
  </div>
</main>
</body>
</html>
"""
    (output_dir / "index.html").write_text(html_text)


def build_visualizations(
    root: Path = Path("artifacts/local-validation"),
    output_dir: Path = Path("artifacts/local-validation/metric-visualizations"),
) -> Path:
    root = root.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    conditions, warnings = load_conditions(root)
    if not conditions:
        raise SystemExit(f"No local-validation q*/policy* reports found under {root}")

    axis_rows = _axis_rows(conditions)
    metric_rows = _metric_rows(conditions)
    summary_rows = _summary_rows(conditions)
    policy_deltas = _policy_delta_rows(conditions)
    perspective_deltas = _perspective_delta_rows(conditions)

    metric_ids = sorted(
        {metric_id for condition in conditions for metric_id in condition.metrics},
        key=_metric_sort_key,
    )
    _write_csv(
        output_dir / "condition_summary.csv",
        summary_rows,
        [
            "q_bucket",
            "run_id",
            "run_dir",
            "folder_name",
            "policy",
            "policy_code",
            "policy_id",
            "perspective",
            "episode",
            "episode_id",
            "selected_csv",
            "csv_count",
            "matching_csv_count",
            "ignored_csv_count",
            "technical_valid",
            "terminal_status",
            *[f"axis_{axis_id}" for axis_id in AXES],
            *[f"metric_{metric_id}" for metric_id in metric_ids],
        ],
    )
    _write_csv(
        output_dir / "axis_scores.csv",
        axis_rows,
        [
            "q_bucket",
            "run_id",
            "run_dir",
            "policy",
            "policy_code",
            "policy_id",
            "perspective",
            "episode",
            "episode_id",
            "axis",
            "score",
            "status",
            "confidence",
        ],
    )
    _write_csv(
        output_dir / "metric_scores.csv",
        metric_rows,
        [
            "q_bucket",
            "run_id",
            "run_dir",
            "policy",
            "policy_code",
            "policy_id",
            "perspective",
            "episode",
            "episode_id",
            "metric",
            "score",
            "status",
            "selected_csv",
        ],
    )
    _write_csv(
        output_dir / "policy_deltas.csv",
        policy_deltas,
        ["episode", "episode_id", "perspective", "axis", "policy_a", "policy_b", "delta_policy_b_minus_a"],
    )
    _write_csv(
        output_dir / "perspective_deltas.csv",
        perspective_deltas,
        ["episode", "episode_id", "policy", "policy_code", "axis", "arrival", "bystander", "delta_bystander_minus_arrival"],
    )

    condition_labels = [
        f"{condition.episode_label} | {POLICY_LABELS.get(condition.policy_code, condition.policy_code)} | "
        f"{condition.perspective}"
        for condition in conditions
    ]
    axis_values = {
        (row_label, _display_name(axis_id)): condition.axes.get(axis_id)
        for condition, row_label in zip(conditions, condition_labels, strict=True)
        for axis_id in AXES
    }
    render_heatmap(
        title="Perceptual Axis Scores By Condition",
        row_labels=condition_labels,
        column_labels=[_display_name(axis_id) for axis_id in AXES],
        values=axis_values,
        output_path=output_dir / "axis_score_heatmap.svg",
        mode="score",
        note="Scores are 0-1; higher is better. Rows are episode x policy x perspective.",
    )

    policy_row_labels = [
        f"{row['episode']} | {row['perspective']}"
        for row in policy_deltas
        if row["axis"] == AXES[0]
    ]
    policy_values = {
        (f"{row['episode']} | {row['perspective']}", _display_name(str(row["axis"]))): row[
            "delta_policy_b_minus_a"
        ]
        for row in policy_deltas
    }
    render_heatmap(
        title="Policy Delta: Policy B Minus Policy A",
        row_labels=policy_row_labels,
        column_labels=[_display_name(axis_id) for axis_id in AXES],
        values=policy_values,
        output_path=output_dir / "policy_delta_heatmap.svg",
        mode="delta",
        note="Positive means Policy B is higher for the same episode and perspective.",
    )

    perspective_row_labels = [
        f"{row['episode']} | {row['policy']}"
        for row in perspective_deltas
        if row["axis"] == AXES[0]
    ]
    perspective_values = {
        (f"{row['episode']} | {row['policy']}", _display_name(str(row["axis"]))): row[
            "delta_bystander_minus_arrival"
        ]
        for row in perspective_deltas
    }
    render_heatmap(
        title="Perspective Delta: Bystander Minus Arrival",
        row_labels=perspective_row_labels,
        column_labels=[_display_name(axis_id) for axis_id in AXES],
        values=perspective_values,
        output_path=output_dir / "perspective_delta_heatmap.svg",
        mode="delta",
        note="Positive means bystander is higher for the same episode and policy.",
    )

    render_metric_heatmap(conditions, output_dir / "feature_metric_heatmap.svg")
    (output_dir / "data_warnings.txt").write_text("\n".join(warnings) + ("\n" if warnings else ""))
    _render_html(output_dir, conditions, warnings, policy_deltas, perspective_deltas)
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("artifacts/local-validation"),
        help="Root containing q*/policy*/ local-validation artifacts.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/local-validation/metric-visualizations"),
        help="Directory for CSV, SVG, and HTML outputs.",
    )
    args = parser.parse_args()
    output_dir = build_visualizations(args.root, args.output)
    print(f"Wrote metric visualizations to {output_dir}")


if __name__ == "__main__":
    main()
