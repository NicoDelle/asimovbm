"""Static-obstacle navigation scenario backed by g1_slam world logic."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .models import (
    EntityDefinition,
    EpisodeDefinition,
    EpisodeObservation,
    EpisodeStatus,
    EpisodeStatusCode,
    PublicEntityObservation,
    ScenarioTraceSample,
)

DEFAULT_WORLD_PADDING_M = 1.0
DEFAULT_LIDAR_RAYS = 31
DEFAULT_LIDAR_RANGE_M = 5.5
DEFAULT_LIDAR_STEP_M = 0.04


@dataclass(frozen=True)
class RectObstacle:
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def contains(self, x: float, y: float, margin: float = 0.0) -> bool:
        return (
            self.x_min - margin <= x <= self.x_max + margin
            and self.y_min - margin <= y <= self.y_max + margin
        )


@dataclass(frozen=True)
class StaticWorld2D:
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    obstacles: tuple[RectObstacle, ...]

    def contains(self, x: float, y: float, margin: float = 0.0) -> bool:
        return (
            self.x_min + margin <= x <= self.x_max - margin
            and self.y_min + margin <= y <= self.y_max - margin
        )

    def is_occupied(self, x: float, y: float, margin: float = 0.0) -> bool:
        if not self.contains(x, y, margin=margin):
            return True
        return any(obstacle.contains(x, y, margin=margin) for obstacle in self.obstacles)

    def collides(self, pose, radius: float) -> bool:
        return self.is_occupied(pose.x, pose.y, margin=radius)


@dataclass(frozen=True)
class StaticLaserScan:
    angles: tuple[float, ...]
    ranges: tuple[float, ...]
    max_range: float


@dataclass
class StaticObstacleWorld:
    world: StaticWorld2D
    obstacle_rects: dict[str, RectObstacle] = field(default_factory=dict)
    latest_ranges: tuple[float, ...] = ()


class StaticObstacleNavigationScenario:
    """First MVP episode: local navigation through fixed rectangular obstacles."""

    def __init__(self, definition: EpisodeDefinition) -> None:
        self.definition = definition

    def create_world(self) -> StaticObstacleWorld:
        return _world_from_definition(self.definition)

    def reset(self, world: StaticObstacleWorld, robot) -> EpisodeObservation:
        robot.reset(self.definition.robot_start)
        return self.observe(0.0, world, robot)

    def before_step(self, time_s: float, world: StaticObstacleWorld) -> None:
        return None

    def observe(
        self,
        time_s: float,
        world: StaticObstacleWorld,
        robot,
    ) -> EpisodeObservation:
        robot_state = robot.state()
        scan = _simulate_lidar(
            world.world,
            robot_state.pose,
            num_rays=_int_metadata(self.definition, "lidar_rays", DEFAULT_LIDAR_RAYS),
            max_range=_float_metadata(self.definition, "lidar_max_range_m", DEFAULT_LIDAR_RANGE_M),
            step=_float_metadata(self.definition, "lidar_step_m", DEFAULT_LIDAR_STEP_M),
        )
        world.latest_ranges = scan.ranges
        return EpisodeObservation(
            episode_id=self.definition.id,
            step_id=robot_state.step_id,
            time_s=time_s,
            dt=self.definition.control_dt,
            robot_pose=robot_state.pose,
            robot_velocity=robot_state.velocity,
            public_goal=self.definition.goal,
            range_readings=scan.ranges,
            visible_entities=tuple(_public_obstacle(entity) for entity in self.definition.obstacles),
            metadata={
                "source": "g1_slam",
                "lidar_angles": scan.angles,
                "lidar_max_range": scan.max_range,
            },
        )

    def evaluate(self, time_s: float, world: StaticObstacleWorld, robot) -> EpisodeStatus:
        robot_state = robot.state()
        pose = robot_state.pose
        distance = _distance_to_goal(self.definition, pose)

        if world.world.collides(pose, robot.profile.body_radius):
            return EpisodeStatus(
                EpisodeStatusCode.COLLISION,
                distance_to_goal=distance,
                reason="robot collided with static obstacle or left g1_slam world",
            )

        if distance is not None and distance <= _goal_tolerance(self.definition):
            return EpisodeStatus(EpisodeStatusCode.SUCCESS, distance_to_goal=distance)

        if robot_state.step_id >= self.definition.max_steps:
            return EpisodeStatus(EpisodeStatusCode.TIMEOUT, distance_to_goal=distance)

        return EpisodeStatus(EpisodeStatusCode.RUNNING, distance_to_goal=distance)

    def trace_sample(
        self,
        time_s: float,
        world: StaticObstacleWorld,
        robot,
    ) -> ScenarioTraceSample:
        pose = robot.state().pose
        collision_summary = _collision_summary(self.definition, world, pose, robot.profile.body_radius)
        return ScenarioTraceSample(
            entities=tuple(_public_obstacle(entity) for entity in self.definition.obstacles),
            collision_summary=collision_summary,
            distance_to_goal=_distance_to_goal(self.definition, pose),
            metadata={
                "source": "g1_slam",
                "world_bounds": (
                    world.world.x_min,
                    world.world.y_min,
                    world.world.x_max,
                    world.world.y_max,
                ),
                "obstacle_rects": {
                    entity_id: (rect.x_min, rect.y_min, rect.x_max, rect.y_max)
                    for entity_id, rect in world.obstacle_rects.items()
                },
                "latest_range_readings": world.latest_ranges,
            },
        )


def _world_from_definition(definition: EpisodeDefinition) -> StaticObstacleWorld:
    rects = {
        entity.id: _rect_from_obstacle(entity)
        for entity in definition.obstacles
    }
    x_min, y_min, x_max, y_max = _bounds_for_definition(definition, tuple(rects.values()))
    return StaticObstacleWorld(
        world=StaticWorld2D(x_min, y_min, x_max, y_max, tuple(rects.values())),
        obstacle_rects=rects,
    )


def _rect_from_obstacle(entity: EntityDefinition) -> RectObstacle:
    half_width = float(entity.metadata.get("half_width", entity.radius))
    half_depth = float(entity.metadata.get("half_depth", entity.radius))
    return RectObstacle(
        entity.x - half_width,
        entity.y - half_depth,
        entity.x + half_width,
        entity.y + half_depth,
    )


def _bounds_for_definition(
    definition: EpisodeDefinition,
    rects: tuple[RectObstacle, ...],
) -> tuple[float, float, float, float]:
    if definition.bounds is not None:
        return definition.bounds

    xs = [definition.robot_start.x]
    ys = [definition.robot_start.y]
    if definition.goal and definition.goal.x is not None and definition.goal.y is not None:
        xs.append(definition.goal.x)
        ys.append(definition.goal.y)
    for rect in rects:
        xs.extend([rect.x_min, rect.x_max])
        ys.extend([rect.y_min, rect.y_max])
    padding = _float_metadata(definition, "world_padding_m", DEFAULT_WORLD_PADDING_M)
    return (
        min(xs) - padding,
        min(ys) - padding,
        max(xs) + padding,
        max(ys) + padding,
    )


def _collision_summary(
    definition: EpisodeDefinition,
    world: StaticObstacleWorld,
    pose,
    robot_radius: float,
) -> dict[str, object]:
    colliding_ids = [
        entity_id
        for entity_id, rect in world.obstacle_rects.items()
        if rect.contains(pose.x, pose.y, margin=robot_radius)
    ]
    left_bounds = not world.world.contains(pose.x, pose.y, margin=robot_radius)
    return {
        "collisions": colliding_ids,
        "count": len(colliding_ids),
        "left_bounds": left_bounds,
        "source": "g1_slam",
        "robot_radius": robot_radius,
        "episode_id": definition.id,
    }


def _public_obstacle(entity: EntityDefinition) -> PublicEntityObservation:
    return PublicEntityObservation(
        id=entity.id,
        kind=entity.kind,
        x=entity.x,
        y=entity.y,
        radius=entity.radius,
        role=entity.role,
    )


def _distance_to_goal(definition: EpisodeDefinition, pose) -> float | None:
    goal = definition.goal
    if goal is None or goal.x is None or goal.y is None:
        return None
    return math.hypot(goal.x - pose.x, goal.y - pose.y)


def _goal_tolerance(definition: EpisodeDefinition) -> float:
    if definition.goal and definition.goal.stop_distance_m is not None:
        return definition.goal.stop_distance_m
    return 0.35


def _simulate_lidar(
    world: StaticWorld2D,
    pose,
    *,
    num_rays: int,
    max_range: float,
    step: float,
) -> StaticLaserScan:
    if num_rays < 2:
        raise ValueError("num_rays must be at least 2")
    fov = 2.0 * math.pi
    start = -0.5 * fov
    delta = fov / (num_rays - 1)
    angles: list[float] = []
    ranges: list[float] = []

    for index in range(num_rays):
        local_angle = _wrap_angle(start + index * delta)
        yaw = pose.yaw + local_angle
        hit_range = max_range
        distance = 0.0
        while distance <= max_range:
            x = pose.x + distance * math.cos(yaw)
            y = pose.y + distance * math.sin(yaw)
            if world.is_occupied(x, y):
                hit_range = distance
                break
            distance += step
        angles.append(local_angle)
        ranges.append(min(hit_range, max_range))

    return StaticLaserScan(tuple(angles), tuple(ranges), max_range)


def _wrap_angle(value: float) -> float:
    return math.atan2(math.sin(value), math.cos(value))


def _float_metadata(definition: EpisodeDefinition, key: str, default: float) -> float:
    return float(definition.metadata.get(key, default))


def _int_metadata(definition: EpisodeDefinition, key: str, default: int) -> int:
    return int(definition.metadata.get(key, default))
