"""Server-local episodic validation runner."""

from __future__ import annotations

import time
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from statistics import mean
from typing import Any

from asimovbm_protocol import ActionMessage
from asimovbm_server.agents import AgentRegistry, default_agent_registry
from asimovbm_server.episodes import (
    EpisodePack,
    EpisodeStatus,
    EpisodeStatusCode,
    default_scenario_registry,
)
from asimovbm_server.episodes.registry import ScenarioRegistry
from asimovbm_server.metrics import (
    MetricRegistry,
    MetricStatus,
    MetricValue,
    aggregate_axes,
    default_metric_registry,
)
from asimovbm_server.robots import RobotRegistry, default_robot_registry
from asimovbm_server.traces import EpisodeTrace, StepTrace
from asimovbm_server.visualization import ViewerHandle, maybe_open_viewer

from .models import BenchmarkRunConfig, BenchmarkRunResult, EpisodeRunRecord, TierRunSummary


class EpisodicValidationRunner:
    def __init__(
        self,
        *,
        robot_registry: RobotRegistry | None = None,
        agent_registry: AgentRegistry | None = None,
        scenario_registry: ScenarioRegistry | None = None,
        metric_registry: MetricRegistry | None = None,
    ) -> None:
        self.robot_registry = robot_registry or default_robot_registry()
        self.agent_registry = agent_registry or default_agent_registry()
        self.scenario_registry = scenario_registry or default_scenario_registry()
        self.metric_registry = metric_registry or default_metric_registry()

    def run(self, pack: EpisodePack, config: BenchmarkRunConfig | None = None) -> BenchmarkRunResult:
        config = config or BenchmarkRunConfig()
        records: list[EpisodeRunRecord] = []
        tier_summaries: list[TierRunSummary] = []

        for tier in pack.tiers:
            tier_attempts = 0
            tier_valid = 0
            tier_technical_failures = 0
            status_counter: Counter[str] = Counter()
            max_attempts = tier.max_attempts or config.max_attempts_per_episode

            for episode in tier.episodes:
                for attempt in range(1, max_attempts + 1):
                    tier_attempts += 1
                    robot = self.robot_registry.create(config.robot_profile_id)
                    agent = self.agent_registry.create(config.agent_id)
                    scenario = self.scenario_registry.create(episode)
                    world = scenario.create_world()
                    trace = self._run_episode(
                        pack_id=pack.id,
                        tier_id=tier.id,
                        attempt=attempt,
                        robot=robot,
                        agent=agent,
                        scenario=scenario,
                        world=world,
                        config=config,
                    )
                    metrics = (
                        self.metric_registry.compute(trace)
                        if trace.technical_valid
                        else {}
                    )
                    records.append(
                        EpisodeRunRecord(
                            tier_id=tier.id,
                            episode_id=episode.id,
                            attempt=attempt,
                            trace=trace,
                            metrics=metrics,
                        )
                    )
                    if trace.technical_valid:
                        tier_valid += 1
                        status_counter.update(value.status for value in metrics.values())
                        break
                    else:
                        tier_technical_failures += 1

            tier_summaries.append(
                TierRunSummary(
                    tier_id=tier.id,
                    attempts=tier_attempts,
                    valid_episodes=tier_valid,
                    technical_failures=tier_technical_failures,
                    metric_status_counts=dict(status_counter),
                )
            )

        return BenchmarkRunResult(
            pack_id=pack.id,
            records=tuple(records),
            tier_summaries=tuple(tier_summaries),
            final_axes=_final_axis_summary(records),
        )

    def _run_episode(
        self,
        *,
        pack_id: str,
        tier_id: str,
        attempt: int,
        robot,
        agent,
        scenario,
        world: Any,
        config: BenchmarkRunConfig,
    ) -> EpisodeTrace:
        observation = scenario.reset(world, robot)
        step_traces: list[StepTrace] = []
        status = EpisodeStatus(EpisodeStatusCode.RUNNING)
        viewer = maybe_open_viewer(robot, enabled=config.visible)
        try:
            while not status.terminal:
                action = agent.act(observation)
                if action.step_id != observation.step_id:
                    action = ActionMessage(
                        observation.step_id,
                        list(action.action),
                        latency_ms=action.latency_ms,
                        metadata=dict(action.metadata),
                        warnings=list(action.warnings),
                        invalid_reason=action.invalid_reason,
                    )
                robot_state = robot.apply_action(action, observation.dt)
                time_s = robot_state.time_s
                scenario.before_step(time_s, world)
                next_observation = scenario.observe(time_s, world, robot)
                status = scenario.evaluate(time_s, world, robot)
                scenario_sample = scenario.trace_sample(time_s, world, robot)
                step_traces.append(
                    StepTrace(
                        step_id=robot_state.step_id,
                        time_s=time_s,
                        dt=observation.dt,
                        robot_state=robot_state,
                        action=action,
                        entities=scenario_sample.entities,
                        cue_events=scenario_sample.cue_events,
                        observation=next_observation,
                        status_after_step=status,
                        collision_summary=scenario_sample.collision_summary,
                        distance_to_goal=scenario_sample.distance_to_goal,
                    )
                )
                observation = next_observation
                _sync_viewer(viewer, config)
        except Exception as exc:
            status = EpisodeStatus(
                EpisodeStatusCode.EPISODE_FAILURE,
                technical_valid=False,
                reason=str(exc),
            )
        finally:
            viewer.close()

        return EpisodeTrace(
            pack_id=pack_id,
            tier_id=tier_id,
            episode_id=scenario.definition.id,
            attempt=attempt,
            definition=scenario.definition,
            steps=tuple(step_traces),
            terminal_status=status,
            robot_profile_id=robot.profile.id,
            agent_id=agent.id,
        )


def result_to_dict(result: BenchmarkRunResult) -> dict[str, Any]:
    return asdict(result)


def write_result_json(result: BenchmarkRunResult, path: Path) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result_to_dict(result), indent=2), encoding="utf-8")


def _sync_viewer(viewer: ViewerHandle, config: BenchmarkRunConfig) -> None:
    viewer.sync()
    if config.realtime > 0:
        # The runner does not know per-step dt here; realtime is just a visible
        # manual-validation throttle.
        time.sleep(0.02 / config.realtime)


def _final_axis_summary(records: list[EpisodeRunRecord]) -> dict[str, dict[str, Any]]:
    axes = aggregate_axes(_run_metric_values(records))
    return {axis_id: axis.to_report() for axis_id, axis in axes.items()}


def _run_metric_values(records: list[EpisodeRunRecord]) -> dict[str, MetricValue]:
    values_by_metric: defaultdict[str, list[MetricValue]] = defaultdict(list)
    for record in records:
        if not record.trace.technical_valid:
            continue
        for value in record.metrics.values():
            values_by_metric[value.metric_id].append(value)
    return {
        metric_id: _summarize_metric_values(metric_id, values)
        for metric_id, values in values_by_metric.items()
    }


def _summarize_metric_values(
    metric_id: str,
    values: list[MetricValue],
) -> MetricValue:
    scored_values = [value for value in values if value.scored]
    metadata = {
        "aggregation": "mean_over_valid_episodes",
        "eligible_episodes": len(values),
        "computed_episodes": len(scored_values),
    }
    if scored_values:
        raw_values = [
            value.raw_value for value in scored_values if value.raw_value is not None
        ]
        return MetricValue(
            metric_id=metric_id,
            status=MetricStatus.COMPUTED,
            raw_value=mean(raw_values) if len(raw_values) == len(scored_values) else None,
            normalized_score=mean(
                value.normalized_score or 0.0 for value in scored_values
            ),
            confidence="sufficient"
            if len(scored_values) == len(values)
            else "partial",
            metadata=metadata,
        )

    status = _summarize_unscored_status(values)
    return MetricValue(
        metric_id=metric_id,
        status=status,
        confidence="not_applicable"
        if status == MetricStatus.NOT_APPLICABLE
        else "insufficient",
        reason="no scored metric values across valid episodes",
        metadata=metadata,
    )


def _summarize_unscored_status(values: list[MetricValue]) -> MetricStatus:
    statuses = {value.status for value in values}
    if statuses == {MetricStatus.NOT_APPLICABLE}:
        return MetricStatus.NOT_APPLICABLE
    if statuses == {MetricStatus.NOT_IMPLEMENTED}:
        return MetricStatus.NOT_IMPLEMENTED
    if MetricStatus.INVALID_INPUT in statuses:
        return MetricStatus.INVALID_INPUT
    return MetricStatus.INSUFFICIENT_EVIDENCE
