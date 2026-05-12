from __future__ import annotations

from .dynamic_obstacles import DynamicObstacle
from .world import RectObstacle, World2D


def navigation_scene_assets() -> str:
    return """    <texture name="nav_sky" type="skybox" builtin="gradient" rgb1="0.50 0.58 0.66" rgb2="0.82 0.86 0.88" width="512" height="512"/>
    <material name="nav_floor_mat" rgba="0.43 0.44 0.42 1" reflectance="0.03" specular="0.10" shininess="0.18"/>
    <material name="nav_obstacle_mat" rgba="0.58 0.12 0.09 1" reflectance="0.03" specular="0.10" shininess="0.20"/>
    <material name="nav_dynamic_cylinder_mat" rgba="0.05 0.25 0.75 1" reflectance="0.05" specular="0.20" shininess="0.30"/>
    <material name="nav_npc_clothes_mat" rgba="0.16 0.30 0.38 1" reflectance="0.03" specular="0.08" shininess="0.20"/>
    <material name="nav_npc_skin_mat" rgba="0.76 0.58 0.43 1" reflectance="0.02" specular="0.05" shininess="0.15"/>
    <material name="nav_npc_leg_mat" rgba="0.08 0.08 0.09 1" reflectance="0.02"/>
    <material name="nav_goal_mat" rgba="0.08 0.58 0.24 1" emission="0.08" reflectance="0.02"/>
    <material name="nav_shadow_mat" rgba="0.02 0.02 0.02 0.22"/>"""


def navigation_lights_and_camera() -> str:
    return """    <light name="key_area_light" directional="true" pos="-4 -6 7" dir="0.45 0.60 -1" ambient="0.18 0.18 0.18" diffuse="0.58 0.55 0.50" specular="0.05 0.05 0.05"/>
    <light name="soft_fill_light" directional="true" pos="5 4 5" dir="-0.45 -0.30 -1" ambient="0.10 0.10 0.11" diffuse="0.22 0.24 0.26" specular="0.02 0.02 0.02"/>
    <light name="warm_side_light" directional="true" pos="-6 2 4" dir="0.70 -0.10 -1" ambient="0.04 0.04 0.04" diffuse="0.18 0.14 0.10" specular="0.02 0.02 0.02"/>
    <camera name="nav_overview" pos="1 -8 7" xyaxes="1 0 0 0 0.65 0.76"/>"""


def navigation_visual_settings() -> str:
    return """  <visual>
    <global azimuth="125" elevation="-32"/>
    <headlight ambient="0.22 0.22 0.22" diffuse="0.18 0.18 0.18" specular="0.01 0.01 0.01"/>
    <rgba haze="0.58 0.63 0.66 1"/>
  </visual>"""


def static_obstacle_geom(index: int, obstacle: RectObstacle) -> str:
    center_x = 0.5 * (obstacle.x_min + obstacle.x_max)
    center_y = 0.5 * (obstacle.y_min + obstacle.y_max)
    size_x = 0.5 * (obstacle.x_max - obstacle.x_min)
    size_y = 0.5 * (obstacle.y_max - obstacle.y_min)
    return (
        f'    <geom name="obs_{index}" type="box" pos="{center_x:.4f} {center_y:.4f} 0.36" '
        f'size="{size_x:.4f} {size_y:.4f} 0.36" material="nav_obstacle_mat"/>'
    )


def environment_scene_geoms(world: World2D) -> str:
    width = world.x_max - world.x_min
    height = world.y_max - world.y_min
    center_x = 0.5 * (world.x_min + world.x_max)
    center_y = 0.5 * (world.y_min + world.y_max)
    floor_size_x = 0.5 * width + 1.0
    floor_size_y = 0.5 * height + 1.0
    return (
        f'    <geom name="floor" type="plane" pos="{center_x:.4f} {center_y:.4f} 0" '
        f'size="{floor_size_x:.4f} {floor_size_y:.4f} 0.05" material="nav_floor_mat"/>'
    )


def dynamic_obstacle_scene_body(obstacle: DynamicObstacle) -> str:
    x, y = obstacle.center
    if obstacle.mode == "npc":
        return (
            f'    <body name="{obstacle.name}" mocap="true" '
            f'pos="{x:.4f} {y:.4f} 0.0000">\n'
            f'      <geom name="{obstacle.name}_shadow" type="cylinder" '
            'pos="0 0 0.006" size="0.24 0.006" material="nav_shadow_mat" '
            'contype="0" conaffinity="0"/>\n'
            f'      <geom name="{obstacle.name}_torso" type="capsule" '
            'fromto="0 0 0.72 0 0 1.32" size="0.16" '
            'material="nav_npc_clothes_mat"/>\n'
            f'      <geom name="{obstacle.name}_head" type="sphere" '
            'pos="0 0 1.55" size="0.14" material="nav_npc_skin_mat"/>\n'
            f'      <geom name="{obstacle.name}_left_leg" type="capsule" '
            'fromto="0 0.075 0.05 0 0.075 0.72" size="0.055" '
            'material="nav_npc_leg_mat"/>\n'
            f'      <geom name="{obstacle.name}_right_leg" type="capsule" '
            'fromto="0 -0.075 0.05 0 -0.075 0.72" size="0.055" '
            'material="nav_npc_leg_mat"/>\n'
            "    </body>"
        )
    return (
        f'    <body name="{obstacle.name}" mocap="true" '
        f'pos="{x:.4f} {y:.4f} {obstacle.half_height:.4f}">\n'
        f'      <geom name="{obstacle.name}_geom" type="cylinder" '
        f'size="{obstacle.radius:.4f} {obstacle.half_height:.4f}" '
        'material="nav_dynamic_cylinder_mat"/>\n'
        "    </body>"
    )
