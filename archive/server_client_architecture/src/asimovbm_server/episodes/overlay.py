"""Simple overlay scenario used until full MuJoCo scenario bodies land."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .models import (
    CueDefinition,
    EpisodeDefinition,
    EpisodeObservation,
    EpisodeStatus,
    EpisodeStatusCode,
    PublicCueEvent,
    PublicEntityObservation,
    ScenarioTraceSample,
)


@dataclass
class OverlayScenarioWorld:
    emitted_cue_keys: set[tuple[float, str, str]] = field(default_factory=set)
    active_cues: list[PublicCueEvent] = field(default_factory=list)


class OverlayEpisodeScenario:
    """Scenario implementation based on declarative entities and cue schedules."""

    def __init__(self, definition: EpisodeDefinition) -> None:
        self.definition = definition

    def create_world(self) -> OverlayScenarioWorld:
        return OverlayScenarioWorld()

    def reset(self, world: OverlayScenarioWorld, robot) -> EpisodeObservation:
        world.emitted_cue_keys.clear()
        world.active_cues.clear()
        robot.reset(self.definition.robot_start)
        return self.observe(0.0, world, robot)

    def before_step(self, time_s: float, world: OverlayScenarioWorld) -> None:
        for cue in self.definition.cues:
            key = (cue.time_s, cue.type, cue.source)
            if cue.time_s <= time_s and key not in world.emitted_cue_keys:
                world.emitted_cue_keys.add(key)
                world.active_cues.append(_public_cue(cue))

    def observe(
        self,
        time_s: float,
        world: OverlayScenarioWorld,
        robot,
    ) -> EpisodeObservation:
        robot_state = robot.state()
        return EpisodeObservation(
            episode_id=self.definition.id,
            step_id=robot_state.step_id,
            time_s=time_s,
            dt=self.definition.control_dt,
            robot_pose=robot_state.pose,
            robot_velocity=robot_state.velocity,
            public_goal=self._public_goal(world),
            range_readings=self._range_readings(robot_state.pose),
            visible_entities=tuple(self._visible_entities(world)),
            active_cues=tuple(world.active_cues),
        )

    def evaluate(self, time_s: float, world: OverlayScenarioWorld, robot) -> EpisodeStatus:
        robot_state = robot.state()
        pose = robot_state.pose
        if self.definition.bounds:
            min_x, min_y, max_x, max_y = self.definition.bounds
            if pose.x < min_x or pose.x > max_x or pose.y < min_y or pose.y > max_y:
                return EpisodeStatus(EpisodeStatusCode.LEFT_BOUNDS)

        distance = self._distance_to_goal(pose, world)
        if distance is not None and distance <= self._goal_tolerance():
            return EpisodeStatus(EpisodeStatusCode.SUCCESS, distance_to_goal=distance)

        collision = self._collision_summary(pose)
        if collision["collisions"]:
            return EpisodeStatus(
                EpisodeStatusCode.COLLISION,
                distance_to_goal=distance,
                reason="robot intersected scenario entity",
            )

        if robot_state.step_id >= self.definition.max_steps:
            return EpisodeStatus(EpisodeStatusCode.TIMEOUT, distance_to_goal=distance)

        return EpisodeStatus(EpisodeStatusCode.RUNNING, distance_to_goal=distance)

    def trace_sample(
        self,
        time_s: float,
        world: OverlayScenarioWorld,
        robot,
    ) -> ScenarioTraceSample:
        pose = robot.state().pose
        return ScenarioTraceSample(
            entities=tuple(self._all_entities_for_trace(world)),
            cue_events=tuple(world.active_cues),
            collision_summary=self._collision_summary(pose),
            distance_to_goal=self._distance_to_goal(pose, world),
        )

    def _public_goal(self, world: OverlayScenarioWorld):
        goal = self.definition.goal
        if goal is None or goal.target_human_id is None:
            return goal
        if any(cue.source == goal.target_human_id for cue in world.active_cues):
            return goal
        return None

    def _visible_entities(
        self,
        world: OverlayScenarioWorld,
    ) -> list[PublicEntityObservation]:
        visible: list[PublicEntityObservation] = []
        target_id = self.definition.goal.target_human_id if self.definition.goal else None
        target_public = target_id is None or any(cue.source == target_id for cue in world.active_cues)
        for entity in self.definition.entities:
            role = entity.role
            if entity.id == target_id and not target_public:
                role = "human"
            visible.append(
                PublicEntityObservation(
                    id=entity.id,
                    kind=entity.kind,
                    x=entity.x,
                    y=entity.y,
                    radius=entity.radius,
                    role=role,
                )
            )
        return visible

    def _all_entities_for_trace(
        self,
        world: OverlayScenarioWorld,
    ) -> list[PublicEntityObservation]:
        return self._visible_entities(world)

    def _range_readings(self, pose) -> tuple[float, ...]:
        if not self.definition.entities:
            return (10.0,)
        return tuple(
            max(0.0, math.hypot(entity.x - pose.x, entity.y - pose.y) - entity.radius)
            for entity in self.definition.entities
        )

    def _collision_summary(self, pose) -> dict[str, object]:
        robot_radius = 0.25
        collisions = [
            entity.id
            for entity in self.definition.entities
            if math.hypot(entity.x - pose.x, entity.y - pose.y) <= entity.radius + robot_radius
        ]
        return {"collisions": collisions, "count": len(collisions)}

    def _distance_to_goal(self, pose, world: OverlayScenarioWorld) -> float | None:
        goal = self._public_goal(world)
        if goal is None:
            return None
        if goal.x is not None and goal.y is not None:
            return math.hypot(goal.x - pose.x, goal.y - pose.y)
        if goal.target_human_id:
            target = next(
                (human for human in self.definition.humans if human.id == goal.target_human_id),
                None,
            )
            if target is None:
                return None
            return math.hypot(target.x - pose.x, target.y - pose.y)
        return None

    def _goal_tolerance(self) -> float:
        goal = self.definition.goal
        if goal and goal.stop_distance_m is not None:
            return goal.stop_distance_m
        return 0.35


def _public_cue(cue: CueDefinition) -> PublicCueEvent:
    return PublicCueEvent(
        time_s=cue.time_s,
        type=cue.type,
        source=cue.source,
        payload=dict(cue.payload),
    )
