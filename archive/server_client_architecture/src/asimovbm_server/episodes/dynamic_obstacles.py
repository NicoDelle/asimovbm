"""Dynamic-obstacle navigation scenario based on the g1_slam cylinder pattern."""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field
from typing import Any

from .models import (
    EntityDefinition,
    EpisodeDefinition,
    EpisodeObservation,
    EpisodeStatus,
    EpisodeStatusCode,
    GoalDefinition,
    PublicEntityObservation,
    ScenarioTraceSample,
)
from .static_obstacles import RectObstacle


@dataclass(frozen=True)
class DynamicCylinder:
    name: str
    center: tuple[float, float]
    axis: tuple[float, float]
    radius: float
    half_height: float
    amplitude_m: float
    period_s: float
    phase_rad: float

    def xy_at(self, sim_time: float) -> tuple[float, float]:
        offset = self.amplitude_m * math.sin(
            (2.0 * math.pi * sim_time / self.period_s) + self.phase_rad
        )
        return self.center[0] + self.axis[0] * offset, self.center[1] + self.axis[1] * offset

    def velocity_at(self, sim_time: float) -> tuple[float, float]:
        scale = (
            self.amplitude_m
            * (2.0 * math.pi / self.period_s)
            * math.cos((2.0 * math.pi * sim_time / self.period_s) + self.phase_rad)
        )
        return self.axis[0] * scale, self.axis[1] * scale


@dataclass
class DynamicObstacleWorld:
    cylinders: tuple[DynamicCylinder, ...]
    static_rects: dict[str, RectObstacle] = field(default_factory=dict)
    positions: dict[str, tuple[float, float]] = field(default_factory=dict)
    velocities: dict[str, tuple[float, float]] = field(default_factory=dict)
    mujoco: Any | None = None
    model: Any | None = None
    data: Any | None = None
    robot_qpos_addr: int | None = None
    cylinder_qpos_addr: dict[str, int] = field(default_factory=dict)


class DynamicObstacleNavigationScenario:
    """Second MVP episode: deterministic moving humans/cylinders in public view."""

    def __init__(self, definition: EpisodeDefinition) -> None:
        self.definition = definition

    def create_world(self) -> DynamicObstacleWorld:
        seed = int(self.definition.metadata.get("dynamic_seed", 7))
        count = int(self.definition.metadata.get("dynamic_count", 8))
        cylinders = _default_dynamic_cylinders(seed)[:count]
        static_rects = {
            entity.id: _rect_from_obstacle(entity)
            for entity in self.definition.obstacles
        }
        world = DynamicObstacleWorld(cylinders=cylinders, static_rects=static_rects)
        _attach_mujoco_scene(self.definition, world)
        return world

    def reset(self, world: DynamicObstacleWorld, robot) -> EpisodeObservation:
        robot.reset(self.definition.robot_start)
        self.before_step(0.0, world)
        _sync_mujoco(world, robot.state().pose)
        return self.observe(0.0, world, robot)

    def before_step(self, time_s: float, world: DynamicObstacleWorld) -> None:
        for cylinder in world.cylinders:
            world.positions[cylinder.name] = cylinder.xy_at(time_s)
            world.velocities[cylinder.name] = cylinder.velocity_at(time_s)

    def observe(self, time_s: float, world: DynamicObstacleWorld, robot) -> EpisodeObservation:
        robot_state = robot.state()
        _sync_mujoco(world, robot_state.pose)
        return EpisodeObservation(
            episode_id=self.definition.id,
            step_id=robot_state.step_id,
            time_s=time_s,
            dt=self.definition.control_dt,
            robot_pose=robot_state.pose,
            robot_velocity=robot_state.velocity,
            public_goal=self.definition.goal,
            range_readings=_range_readings(world, robot_state.pose),
            visible_entities=_entities(self.definition, world),
            metadata={"source": "g1_slam", "world_bounds": _bounds(self.definition)},
        )

    def viewer_target(self, world: DynamicObstacleWorld) -> tuple[Any, Any] | None:
        if world.model is None or world.data is None:
            return None
        return world.model, world.data

    def evaluate(self, time_s: float, world: DynamicObstacleWorld, robot) -> EpisodeStatus:
        robot_state = robot.state()
        pose = robot_state.pose
        distance = _distance_to_goal(self.definition.goal, pose)
        if _outside_bounds(self.definition, pose, robot.profile.body_radius):
            return EpisodeStatus(EpisodeStatusCode.LEFT_BOUNDS, distance_to_goal=distance)
        collision_ids = _collisions(world, pose, robot.profile.body_radius)
        if collision_ids:
            return EpisodeStatus(
                EpisodeStatusCode.COLLISION,
                distance_to_goal=distance,
                reason=f"robot intersected dynamic entity {collision_ids[0]}",
            )
        if distance is not None and distance <= _goal_tolerance(self.definition):
            return EpisodeStatus(EpisodeStatusCode.SUCCESS, distance_to_goal=distance)
        if robot_state.step_id >= self.definition.max_steps:
            return EpisodeStatus(EpisodeStatusCode.TIMEOUT, distance_to_goal=distance)
        return EpisodeStatus(EpisodeStatusCode.RUNNING, distance_to_goal=distance)

    def trace_sample(self, time_s: float, world: DynamicObstacleWorld, robot) -> ScenarioTraceSample:
        pose = robot.state().pose
        collisions = _collisions(world, pose, robot.profile.body_radius)
        return ScenarioTraceSample(
            entities=_entities(self.definition, world),
            collision_summary={
                "collisions": collisions,
                "static_collisions": _static_collisions(world, pose, robot.profile.body_radius),
                "dynamic_collisions": _dynamic_collisions(world, pose, robot.profile.body_radius),
                "count": len(collisions),
                "source": "g1_slam_dynamic_cylinders",
                "robot_radius": robot.profile.body_radius,
            },
            distance_to_goal=_distance_to_goal(self.definition.goal, pose),
            metadata={
                "dynamic_entity_count": len(world.cylinders),
                "static_obstacle_count": len(world.static_rects),
                "source": "g1_slam",
            },
        )


def _default_dynamic_cylinders(seed: int) -> tuple[DynamicCylinder, ...]:
    rng = random.Random(seed)
    specs = (
        ("blue_cylinder_0", (-3.2, -1.2), (1.0, 0.20), 0.22, 1.5, 12.0),
        ("blue_cylinder_1", (-1.0, 1.4), (-0.35, 1.0), 0.25, 1.2, 10.0),
        ("blue_cylinder_2", (1.4, -1.3), (0.8, -0.55), 0.20, 1.4, 14.0),
        ("blue_cylinder_3", (3.2, 1.1), (0.15, 1.0), 0.24, 1.3, 13.0),
        ("blue_cylinder_4", (5.0, -1.4), (1.0, -0.10), 0.22, 1.5, 15.0),
        ("blue_cylinder_5", (6.8, 1.3), (-0.45, 1.0), 0.25, 1.1, 11.0),
        ("blue_cylinder_6", (8.3, -0.8), (0.55, 1.0), 0.20, 1.0, 9.5),
        ("blue_cylinder_7", (0.4, 0.2), (0.0, 1.0), 0.18, 1.0, 8.5),
    )
    return tuple(
        DynamicCylinder(
            name=name,
            center=center,
            axis=_unit(axis),
            radius=radius,
            half_height=0.35,
            amplitude_m=amplitude,
            period_s=period,
            phase_rad=rng.uniform(0.0, 2.0 * math.pi),
        )
        for name, center, axis, radius, amplitude, period in specs
    )


def _entities(
    definition: EpisodeDefinition,
    world: DynamicObstacleWorld,
) -> tuple[PublicEntityObservation, ...]:
    return _static_entities(definition) + _dynamic_entities(world)


def _static_entities(definition: EpisodeDefinition) -> tuple[PublicEntityObservation, ...]:
    entities = []
    for entity in definition.obstacles:
        metadata = dict(entity.metadata)
        metadata.setdefault("shape", entity.shape)
        if entity.shape == "rectangle":
            metadata.setdefault("half_width", entity.half_width)
            metadata.setdefault("half_depth", entity.half_depth)
        entities.append(
            PublicEntityObservation(
                id=entity.id,
                kind=entity.kind,
                x=entity.x,
                y=entity.y,
                radius=entity.radius,
                role=entity.role,
                metadata=metadata,
            )
        )
    return tuple(entities)


def _range_readings(world: DynamicObstacleWorld, pose) -> tuple[float, ...]:
    static_ranges = tuple(
        max(0.0, _distance_to_rect_boundary(rect, pose.x, pose.y))
        for rect in world.static_rects.values()
    )
    dynamic_ranges = tuple(
        max(0.0, math.hypot(entity.x - pose.x, entity.y - pose.y) - entity.radius)
        for entity in _dynamic_entities(world)
    )
    return static_ranges + dynamic_ranges


def _dynamic_entities(world: DynamicObstacleWorld) -> tuple[PublicEntityObservation, ...]:
    return tuple(
        PublicEntityObservation(
            id=cylinder.name,
            kind="human",
            x=world.positions[cylinder.name][0],
            y=world.positions[cylinder.name][1],
            radius=cylinder.radius,
            role="dynamic_obstacle",
            velocity=world.velocities[cylinder.name],
            posture="moving",
            metadata={
                "source": "g1_slam_dynamic_cylinder",
                "period_s": cylinder.period_s,
                "amplitude_m": cylinder.amplitude_m,
            },
        )
        for cylinder in world.cylinders
    )


def _collisions(world: DynamicObstacleWorld, pose, robot_radius: float) -> list[str]:
    return _static_collisions(world, pose, robot_radius) + _dynamic_collisions(
        world,
        pose,
        robot_radius,
    )


def _static_collisions(world: DynamicObstacleWorld, pose, robot_radius: float) -> list[str]:
    return [
        entity_id
        for entity_id, rect in world.static_rects.items()
        if rect.contains(pose.x, pose.y, margin=robot_radius)
    ]


def _dynamic_collisions(world: DynamicObstacleWorld, pose, robot_radius: float) -> list[str]:
    return [
        entity.id
        for entity in _dynamic_entities(world)
        if math.hypot(entity.x - pose.x, entity.y - pose.y) <= entity.radius + robot_radius
    ]


def _rect_from_obstacle(entity: EntityDefinition) -> RectObstacle:
    half_width = float(entity.half_width or entity.metadata.get("half_width", entity.radius))
    half_depth = float(entity.half_depth or entity.metadata.get("half_depth", entity.radius))
    return RectObstacle(
        entity.x - half_width,
        entity.y - half_depth,
        entity.x + half_width,
        entity.y + half_depth,
    )


def _distance_to_rect_boundary(rect: RectObstacle, x: float, y: float) -> float:
    dx = max(rect.x_min - x, 0.0, x - rect.x_max)
    dy = max(rect.y_min - y, 0.0, y - rect.y_max)
    return math.hypot(dx, dy)


def _distance_to_goal(goal: GoalDefinition | None, pose) -> float | None:
    if goal is None or goal.x is None or goal.y is None:
        return None
    return math.hypot(goal.x - pose.x, goal.y - pose.y)


def _goal_tolerance(definition: EpisodeDefinition) -> float:
    if definition.goal and definition.goal.stop_distance_m is not None:
        return definition.goal.stop_distance_m
    return 0.45


def _bounds(definition: EpisodeDefinition) -> tuple[float, float, float, float]:
    return definition.bounds or (-12.0, -7.0, 14.0, 7.0)


def _outside_bounds(definition: EpisodeDefinition, pose, margin: float) -> bool:
    min_x, min_y, max_x, max_y = _bounds(definition)
    return (
        pose.x < min_x + margin
        or pose.x > max_x - margin
        or pose.y < min_y + margin
        or pose.y > max_y - margin
    )


def _unit(vector: tuple[float, float]) -> tuple[float, float]:
    length = math.hypot(vector[0], vector[1])
    if length == 0:
        raise ValueError("Cannot normalize a zero-length vector")
    return vector[0] / length, vector[1] / length


def _attach_mujoco_scene(definition: EpisodeDefinition, world: DynamicObstacleWorld) -> None:
    try:
        import mujoco
    except ModuleNotFoundError:
        return
    model = mujoco.MjModel.from_xml_string(_mujoco_scene_xml(definition, world))
    data = mujoco.MjData(model)
    robot_joint = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, "robot_freejoint")
    if robot_joint >= 0:
        world.robot_qpos_addr = int(model.jnt_qposadr[robot_joint])
    for cylinder in world.cylinders:
        joint_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_JOINT, f"{_xml_name(cylinder.name)}_joint")
        if joint_id >= 0:
            world.cylinder_qpos_addr[cylinder.name] = int(model.jnt_qposadr[joint_id])
    world.mujoco = mujoco
    world.model = model
    world.data = data


def _sync_mujoco(world: DynamicObstacleWorld, pose) -> None:
    if world.mujoco is None or world.model is None or world.data is None:
        return
    if world.robot_qpos_addr is not None:
        addr = world.robot_qpos_addr
        world.data.qpos[addr + 0] = pose.x
        world.data.qpos[addr + 1] = pose.y
        world.data.qpos[addr + 2] = 0.18
        half_yaw = 0.5 * pose.yaw
        world.data.qpos[addr + 3] = math.cos(half_yaw)
        world.data.qpos[addr + 4] = 0.0
        world.data.qpos[addr + 5] = 0.0
        world.data.qpos[addr + 6] = math.sin(half_yaw)
    for name, addr in world.cylinder_qpos_addr.items():
        x, y = world.positions.get(name, (0.0, 0.0))
        world.data.qpos[addr + 0] = x
        world.data.qpos[addr + 1] = y
        world.data.qpos[addr + 2] = 0.35
    world.mujoco.mj_forward(world.model, world.data)


def _mujoco_scene_xml(definition: EpisodeDefinition, world: DynamicObstacleWorld) -> str:
    min_x, min_y, max_x, max_y = _bounds(definition)
    goal_x = definition.goal.x if definition.goal and definition.goal.x is not None else 0.0
    goal_y = definition.goal.y if definition.goal and definition.goal.y is not None else 0.0
    center_x = 0.5 * (min_x + max_x)
    center_y = 0.5 * (min_y + max_y)
    static_obstacles = "\n".join(
        f"""    <geom name="{_xml_name(entity_id)}" type="box" pos="{0.5 * (rect.x_min + rect.x_max):.4f} {0.5 * (rect.y_min + rect.y_max):.4f} 0.30" size="{0.5 * (rect.x_max - rect.x_min):.4f} {0.5 * (rect.y_max - rect.y_min):.4f} 0.30" rgba="0.8 0.18 0.12 1"/>"""
        for entity_id, rect in world.static_rects.items()
    )
    cylinders = "\n".join(
        f"""    <body name="{_xml_name(cylinder.name)}" pos="{cylinder.center[0]:.4f} {cylinder.center[1]:.4f} 0.35">
      <freejoint name="{_xml_name(cylinder.name)}_joint"/>
      <geom type="cylinder" size="{cylinder.radius:.4f} {cylinder.half_height:.4f}" rgba="0.1 0.35 0.95 1"/>
    </body>"""
        for cylinder in world.cylinders
    )
    return f"""<mujoco model="asimovbm_dynamic_obstacles">
  <option timestep="{definition.control_dt:.4f}"/>
  <asset>
    <material name="floor_mat" rgba="0.22 0.24 0.25 1"/>
    <material name="goal_mat" rgba="0.1 0.8 0.35 1"/>
    <material name="robot_mat" rgba="0.12 0.42 0.95 1"/>
  </asset>
  <worldbody>
    <light name="top_light" directional="true" pos="0 0 8" dir="0 0 -1"/>
    <camera name="overview" pos="{center_x:.4f} {center_y - 9.0:.4f} 9.0" xyaxes="1 0 0 0 0.82 0.57"/>
    <geom name="floor" type="plane" pos="{0.5 * (min_x + max_x):.4f} {0.5 * (min_y + max_y):.4f} 0" size="{0.5 * (max_x - min_x):.4f} {0.5 * (max_y - min_y):.4f} 0.05" material="floor_mat"/>
    <geom name="goal_agent" type="cylinder" pos="{goal_x:.4f} {goal_y:.4f} 0.45" size="0.20 0.45" material="goal_mat"/>
{static_obstacles}
{cylinders}
    <body name="robot_marker" pos="0 0 0.18">
      <freejoint name="robot_freejoint"/>
      <geom type="cylinder" size="0.25 0.18" material="robot_mat"/>
    </body>
  </worldbody>
</mujoco>
"""


def _xml_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_]", "_", value)
    if not name or name[0].isdigit():
        return f"entity_{name}"
    return name
