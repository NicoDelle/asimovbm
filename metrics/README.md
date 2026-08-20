# Metrics

This is the front door for checking and editing objective HRI metrics.

Editable metric code:

```text
asimovbm/metrics/
```

Metric tests:

```text
tests/metrics/
```

Metric specification:

```text
docs/specs/social-navigation-metrics.md
```

## How The Metric Package Is Organized

```text
asimovbm/metrics/models.py        Shared metric value/status models.
asimovbm/metrics/registry.py      Stable metric and axis registry.
asimovbm/metrics/weights.py       Axis and feature weighting.
asimovbm/metrics/scoring.py       Score normalization helpers.
asimovbm/metrics/aggregation.py   Axis aggregation logic.
asimovbm/metrics/*                One file per concrete metric.
```

## Current High-Level Axes

- `perceived_dexterity`
- `perceived_safety`
- `perceived_social_awareness`
- `impression`

## Concrete Metric Files

Dexterity:

- `asimovbm/metrics/task_success_rate.py`
- `asimovbm/metrics/completion_time.py`
- `asimovbm/metrics/comfort_aware_path_efficiency.py`
- `asimovbm/metrics/hesitation.py`

Safety:

- `asimovbm/metrics/min_human_robot_distance.py`
- `asimovbm/metrics/proxemic_intrusion_dose.py`
- `asimovbm/metrics/speed_near_humans_p95.py`
- `asimovbm/metrics/stability.py`

Social awareness:

- `asimovbm/metrics/gesture_response_success.py`
- `asimovbm/metrics/acknowledgement_clarity.py`
- `asimovbm/metrics/human_aware_approach.py`
- `asimovbm/metrics/bystander_ack.py`

Impression:

- `asimovbm/metrics/sparc.py`
- `asimovbm/metrics/heading_jerk.py`
- `asimovbm/metrics/legibility.py`
- `asimovbm/metrics/behavioral_naturalness.py`

## Edit Checklist

1. Edit the metric file under `asimovbm/metrics/`.
2. Update or add the matching test under `tests/metrics/`.
3. Run:

```bash
.venv/bin/python -m pytest tests/metrics
```

4. If the edit changes a formula or interpretation, update
   `docs/specs/social-navigation-metrics.md`.
