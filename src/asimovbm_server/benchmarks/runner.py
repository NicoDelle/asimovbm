"""Server-local episodic validation runner."""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path
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
from asimovbm_server.metrics import MetricRegistry, default_metric_registry
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
        robot_profile_ids = _selected_robot_profile_ids(config)
        self.robot_registry.validate_profile_ids(robot_profile_ids)
        records: list[EpisodeRunRecord] = []
        tier_summaries: list[TierRunSummary] = []

        for tier in pack.tiers:
            if config.tier_id is not None and tier.id != config.tier_id:
                continue
            tier_attempts = 0
            tier_valid = 0
            tier_technical_failures = 0
            status_counter: Counter[str] = Counter()
            max_attempts = tier.max_attempts or config.max_attempts_per_episode

            for episode in tier.episodes:
                if config.episode_id is not None and episode.id != config.episode_id:
                    continue
                for robot_profile_id in robot_profile_ids:
                    for attempt in range(1, max_attempts + 1):
                        tier_attempts += 1
                        robot = self.robot_registry.create(robot_profile_id)
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
                                robot_profile_id=robot.profile.id,
                                robot_embodiment_kind=robot.profile.embodiment_kind,
                                robot_metadata=robot.profile.setup_metadata(),
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
            final_axes=_placeholder_axis_summary(records),
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
        viewer = maybe_open_viewer(_scenario_viewer_target(scenario, world), robot, enabled=config.visible)
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
                        metadata=scenario_sample.metadata,
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
            metadata={"robot": robot.profile.setup_metadata()},
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


def _scenario_viewer_target(scenario, world) -> tuple[Any, Any] | None:
    viewer_target = getattr(scenario, "viewer_target", None)
    if not callable(viewer_target):
        return None
    return viewer_target(world)


def _placeholder_axis_summary(records: list[EpisodeRunRecord]) -> dict[str, float | None]:
    if not records:
        return {
            "perceived_dexterity": None,
            "perceived_safety": None,
            "perceived_social_awareness": None,
            "impression": None,
        }
    return {
        "perceived_dexterity": None,
        "perceived_safety": None,
        "perceived_social_awareness": None,
        "impression": None,
    }


def _selected_robot_profile_ids(config: BenchmarkRunConfig) -> tuple[str, ...]:
    if config.robot_profile_ids:
        return tuple(profile_id for profile_id in config.robot_profile_ids if profile_id)
    if not config.robot_profile_id:
        return ()
    return (config.robot_profile_id,)
