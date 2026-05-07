from __future__ import annotations

from asimovbm_server.benchmarks import BenchmarkRunConfig, EpisodicValidationRunner
from asimovbm_server.episodes import episode_pack_from_mapping
from asimovbm_server.metrics import (
    SOCIAL_NAVIGATION_METRIC_IDS,
    MetricStatus,
    default_metric_registry,
)


def _one_episode_pack():
    return episode_pack_from_mapping(
        {
            "version": 1,
            "id": "pack",
            "tiers": [
                {
                    "id": "tier",
                    "episodes": [
                        {
                            "id": "episode",
                            "scenario_type": "obstacle_navigation",
                            "robot_start": {"x": 0.0, "y": 0.0},
                            "goal": {"x": 0.1, "y": 0.0},
                            "max_steps": 5,
                        }
                    ],
                }
            ],
        }
    )


def test_default_metric_registry_exposes_all_social_navigation_metric_ids() -> None:
    registry = default_metric_registry()

    assert registry.metric_ids == SOCIAL_NAVIGATION_METRIC_IDS
    assert len(registry.metric_ids) == 12


def test_runner_invokes_placeholder_metrics_for_valid_episode() -> None:
    result = EpisodicValidationRunner().run(
        _one_episode_pack(),
        BenchmarkRunConfig(max_attempts_per_episode=1),
    )

    assert result.valid_episodes == 1
    metrics = result.records[0].metrics
    assert set(metrics) == set(SOCIAL_NAVIGATION_METRIC_IDS)
    assert {value.status for value in metrics.values()} == {MetricStatus.NOT_IMPLEMENTED}
