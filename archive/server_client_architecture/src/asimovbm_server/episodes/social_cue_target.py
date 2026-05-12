"""Social-cue target approach scenario with hidden target identity."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .models import (
    CueDefinition,
    EpisodeDefinition,
    EpisodeObservation,
    EpisodePackError,
    EpisodeStatus,
    EpisodeStatusCode,
    GoalDefinition,
    PublicCueEvent,
    PublicEntityObservation,
    ScenarioTraceSample,
)


@dataclass
class SocialCueTargetWorld:
    emitted_cue_keys: set[tuple[float, str, str]] = field(default_factory=set)
    active_cues: list[PublicCueEvent] = field(default_factory=list)


class SocialCueTargetScenario:
    """Third MVP episode: approach the target only after a public cue."""

    def __init__(self, definition: EpisodeDefinition) -> None:
        self.definition = definition
        if not self.definition.goal or not self.definition.goal.target_human_id:
            raise EpisodePackError(
                f"social cue episode {definition.id} must define goal.target_human_id"
            )
        if not any(cue.source == self.definition.goal.target_human_id for cue in self.definition.cues):
            raise EpisodePackError(
                f"social cue episode {definition.id} needs a cue from target "
                f"{self.definition.goal.target_human_id}"
            )

    def create_world(self) -> SocialCueTargetWorld:
        return SocialCueTargetWorld()

    def reset(self, world: SocialCueTargetWorld, robot) -> EpisodeObservation:
        world.emitted_cue_keys.clear()
        world.active_cues.clear()
        robot.reset(self.definition.robot_start)
        return self.observe(0.0, world, robot)

    def before_step(self, time_s: float, world: SocialCueTargetWorld) -> None:
        for cue in self.definition.cues:
            key = (cue.time_s, cue.type, cue.source)
            if cue.time_s <= time_s and key not in world.emitted_cue_keys:
                world.emitted_cue_keys.add(key)
                world.active_cues.append(_public_cue(cue))

    def observe(self, time_s: float, world: SocialCueTargetWorld, robot) -> EpisodeObservation:
        robot_state = robot.state()
        return EpisodeObservation(
            episode_id=self.definition.id,
            step_id=robot_state.step_id,
            time_s=time_s,
            dt=self.definition.control_dt,
            robot_pose=robot_state.pose,
            robot_velocity=robot_state.velocity,
            public_goal=_public_goal(self.definition.goal, world),
            range_readings=_range_readings(self.definition, robot_state.pose),
            visible_entities=_visible_entities(self.definition, world),
            active_cues=tuple(world.active_cues),
            metadata={
                "cue_public": _target_public(self.definition, world),
                "world_bounds": self.definition.bounds,
            },
        )

    def evaluate(self, time_s: float, world: SocialCueTargetWorld, robot) -> EpisodeStatus:
        robot_state = robot.state()
        pose = robot_state.pose
        distance = _distance_to_target(self.definition, pose)
        if _outside_bounds(self.definition, pose):
            return EpisodeStatus(EpisodeStatusCode.LEFT_BOUNDS, distance_to_goal=distance)
        if _collisions(self.definition, pose, robot.profile.body_radius):
            return EpisodeStatus(
                EpisodeStatusCode.COLLISION,
                distance_to_goal=distance,
                reason="robot intersected a human",
            )
        if (
            _target_public(self.definition, world)
            and distance is not None
            and distance <= _goal_tolerance(self.definition.goal)
        ):
            return EpisodeStatus(EpisodeStatusCode.SUCCESS, distance_to_goal=distance)
        if robot_state.step_id >= self.definition.max_steps:
            return EpisodeStatus(EpisodeStatusCode.TIMEOUT, distance_to_goal=distance)
        return EpisodeStatus(EpisodeStatusCode.RUNNING, distance_to_goal=distance)

    def trace_sample(self, time_s: float, world: SocialCueTargetWorld, robot) -> ScenarioTraceSample:
        pose = robot.state().pose
        collisions = _collisions(self.definition, pose, robot.profile.body_radius)
        return ScenarioTraceSample(
            entities=_trace_entities(self.definition, world),
            cue_events=tuple(world.active_cues),
            collision_summary={
                "collisions": collisions,
                "count": len(collisions),
                "target_public": _target_public(self.definition, world),
                "robot_radius": robot.profile.body_radius,
            },
            distance_to_goal=_distance_to_target(self.definition, pose),
            metadata={
                "hidden_target_id": self.definition.goal.target_human_id if self.definition.goal else None,
                "target_public": _target_public(self.definition, world),
                "cue_count": len(world.active_cues),
            },
        )


def _public_cue(cue: CueDefinition) -> PublicCueEvent:
    return PublicCueEvent(cue.time_s, cue.type, cue.source, dict(cue.payload))


def _target_public(definition: EpisodeDefinition, world: SocialCueTargetWorld) -> bool:
    target_id = definition.goal.target_human_id if definition.goal else None
    return bool(target_id and any(cue.source == target_id for cue in world.active_cues))


def _public_goal(goal: GoalDefinition | None, world: SocialCueTargetWorld) -> GoalDefinition | None:
    if goal is None or goal.target_human_id is None:
        return goal
    if any(cue.source == goal.target_human_id for cue in world.active_cues):
        return goal
    return None


def _visible_entities(
    definition: EpisodeDefinition,
    world: SocialCueTargetWorld,
) -> tuple[PublicEntityObservation, ...]:
    target_id = definition.goal.target_human_id if definition.goal else None
    target_public = _target_public(definition, world)
    observations = []
    for human in definition.humans:
        role = human.role
        public = human.public_before_cue or human.id != target_id or target_public
        if human.id == target_id and not target_public:
            role = "human"
        observations.append(
            PublicEntityObservation(
                id=human.id,
                kind=human.kind,
                x=human.x,
                y=human.y,
                radius=human.radius,
                role=role,
                posture=human.posture,
                public=public,
                metadata={"target_identity_public": human.id != target_id or target_public},
            )
        )
    return tuple(observations)


def _trace_entities(
    definition: EpisodeDefinition,
    world: SocialCueTargetWorld,
) -> tuple[PublicEntityObservation, ...]:
    target_id = definition.goal.target_human_id if definition.goal else None
    target_public = _target_public(definition, world)
    return tuple(
        PublicEntityObservation(
            id=human.id,
            kind=human.kind,
            x=human.x,
            y=human.y,
            radius=human.radius,
            role=human.role,
            posture=human.posture,
            public=human.id != target_id or target_public,
            metadata={"is_hidden_target": human.id == target_id, "target_identity_public": target_public},
        )
        for human in definition.humans
    )


def _range_readings(definition: EpisodeDefinition, pose) -> tuple[float, ...]:
    return tuple(
        max(0.0, math.hypot(human.x - pose.x, human.y - pose.y) - human.radius)
        for human in definition.humans
    )


def _collisions(definition: EpisodeDefinition, pose, robot_radius: float) -> list[str]:
    return [
        human.id
        for human in definition.humans
        if math.hypot(human.x - pose.x, human.y - pose.y) <= human.radius + robot_radius
    ]


def _distance_to_target(definition: EpisodeDefinition, pose) -> float | None:
    target_id = definition.goal.target_human_id if definition.goal else None
    target = next((human for human in definition.humans if human.id == target_id), None)
    if target is None:
        return None
    return math.hypot(target.x - pose.x, target.y - pose.y)


def _goal_tolerance(goal: GoalDefinition | None) -> float:
    if goal and goal.stop_distance_m is not None:
        return goal.stop_distance_m
    return 0.8


def _outside_bounds(definition: EpisodeDefinition, pose) -> bool:
    if not definition.bounds:
        return False
    min_x, min_y, max_x, max_y = definition.bounds
    return pose.x < min_x or pose.x > max_x or pose.y < min_y or pose.y > max_y
