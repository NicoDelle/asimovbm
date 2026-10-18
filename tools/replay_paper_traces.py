"""Render archived paper joint poses; never rerun a policy or claim original stimuli."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ROBOT_XML = ROOT / "g1_slam/third_party/RoboJuDo/assets/robots/g1/g1_29dof_rev_1_0.xml"
BLOCKS = {
    "q1": "Policy A / arrival",
    "q2": "Policy B / arrival",
    "q3": "Policy A / bystander",
    "q4": "Policy B / bystander",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frame_indices(times: np.ndarray, fps: int) -> np.ndarray:
    """Nearest recorded samples on a real-time frame grid, including terminal pose."""
    if fps < 1 or len(times) == 0 or not np.all(np.isfinite(times)):
        raise ValueError("require positive fps and nonempty finite timestamps")
    if times[0] < 0 or np.any(np.diff(times) <= 0):
        raise ValueError("trace timestamps must be nonnegative and strictly increasing")
    grid = np.arange(max(1, math.ceil(times[-1] * fps))) / fps
    right = np.searchsorted(times, grid).clip(0, len(times) - 1)
    left = (right - 1).clip(0)
    chosen = np.where(abs(times[left] - grid) <= abs(times[right] - grid), left, right)
    chosen[-1] = len(times) - 1
    return chosen


def scene_xml(trace: dict, config: dict) -> str:
    """Use the same navigation scene builder as the recorded RoboJuDo backend."""
    from g1_slam.dynamic_obstacles import DynamicObstacle
    from g1_slam.robojudo_backend import _robojudo_navigation_scene_tail
    from g1_slam.world import RectObstacle, World2D

    source = ROBOT_XML.read_text()
    prefix, separator, _ = source.partition("  <!-- setup scene -->")
    if not separator:
        raise ValueError("pinned robot XML has no expected scene boundary")
    first = trace["steps"][0]
    bounds = config["world"]
    obstacles = tuple(
        RectObstacle(**{key: e[key] for key in ("x_min", "y_min", "x_max", "y_max")})
        for e in first["static_entities"]
        if e["type"] == "obstacle"
    )
    world = World2D(
        **{key: bounds[key] for key in ("x_min", "y_min", "x_max", "y_max")}, obstacles=obstacles
    )
    people = tuple(
        DynamicObstacle(
            name=e["id"],
            center=tuple(e["pose"][:2]),
            axis=(1, 0),
            radius=e["radius"],
            half_height=0.8,
            amplitude_m=0,
            period_s=1,
            phase_rad=0,
            mode="npc",
        )
        for e in first["dynamic_entities"]
    )
    xml = ET.fromstring(prefix + _robojudo_navigation_scene_tail(world, people))
    xml.find("compiler").set("meshdir", str(ROBOT_XML.parent / "meshes"))
    return ET.tostring(xml, encoding="unicode")


def render_trace(path: Path, output: Path, args: argparse.Namespace, font) -> dict:
    import mujoco
    from g1_slam.mujoco_runner import (
        _offscreen_camera,
        _offscreen_scene_option,
        _suppress_robot_collision_visuals,
    )

    from g1_slam.config import load_navigation_config, visualization_for_camera_view

    trace = json.loads(path.read_text())
    config_path = ROOT / trace["config_path"]
    if sha256(config_path) != trace["config_checksum_sha256"]:
        raise ValueError(f"config checksum differs from archived run: {config_path}")
    config = json.loads(config_path.read_text())
    scene = scene_xml(trace, config)
    model = mujoco.MjModel.from_xml_string(scene)
    # Replay needs forward kinematics, not a contact solve. Suppress the same
    # duplicate collision visuals as the simulator, retaining NPC geoms.
    _suppress_robot_collision_visuals(
        mujoco,
        model,
        tuple(SimpleNamespace(name=e["id"]) for e in trace["steps"][0]["dynamic_entities"]),
    )
    model.opt.disableflags |= mujoco.mjtDisableBit.mjDSBL_CONTACT
    model.vis.quality.offsamples = 0
    data = mujoco.MjData(model)
    steps = trace["steps"]
    poses = np.asarray([s["qpos"] for s in steps], dtype=float)
    times = np.asarray([s["time_s"] for s in steps])
    if poses.shape != (len(steps), model.nq) or not np.all(np.isfinite(poses)):
        raise ValueError(f"recorded joint dimensions do not match model: {path}")
    view = trace["metadata"]["camera_view"]
    visual = visualization_for_camera_view(
        load_navigation_config(config_path).visualization, camera_view=view
    )
    camera = _offscreen_camera(mujoco, model, visual)
    option = _offscreen_scene_option(mujoco)
    goal_id = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "goal")
    model.geom_pos[goal_id, :2] = trace["metadata"]["goal"]
    indices = frame_indices(times, args.fps)
    temporary = output.with_suffix(".partial.mp4")
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "rawvideo",
        "-pixel_format",
        "rgb24",
        "-video_size",
        f"{args.width}x{args.height}",
        "-framerate",
        str(args.fps),
        "-i",
        "-",
        "-an",
        "-c:v",
        "libx264",
        "-threads",
        "2",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(temporary),
    ]
    try:
        with (
            tempfile.TemporaryFile() as errors,
            mujoco.Renderer(model, height=args.height, width=args.width) as renderer,
        ):
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=errors)
            try:
                for index in indices:
                    step = steps[index]
                    data.qpos[:] = poses[index]
                    data.time = step["time_s"]
                    for person in step["dynamic_entities"]:
                        body = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, person["id"])
                        if body < 0 or model.body_mocapid[body] < 0:
                            raise ValueError(f"unknown recorded NPC: {person['id']}")
                        mocap = model.body_mocapid[body]
                        x, y, yaw = person["pose"]
                        data.mocap_pos[mocap] = (x, y, 0)
                        data.mocap_quat[mocap] = (math.cos(yaw / 2), 0, 0, math.sin(yaw / 2))
                    mujoco.mj_forward(model, data)
                    renderer.update_scene(data, camera=camera, scene_option=option)
                    renderer.scene.flags[mujoco.mjtRndFlag.mjRND_SHADOW] = False
                    renderer.scene.flags[mujoco.mjtRndFlag.mjRND_REFLECTION] = False
                    frame = Image.fromarray(renderer.render())
                    draw = ImageDraw.Draw(frame)
                    draw.rectangle((0, 0, args.width, 29), fill=(12, 22, 33))
                    label = f"{BLOCKS[path.parts[-5]]} | {trace['episode_id'].removeprefix('g1_point_to_point_')}"
                    draw.text((12, 5), label, font=font, fill="white")
                    draw.rectangle(
                        (0, args.height - 29, args.width, args.height), fill=(12, 22, 33)
                    )
                    draw.text(
                        (12, args.height - 25),
                        f"{data.time:.2f}s | 1x playback",
                        font=font,
                        fill="white",
                    )
                    if index == indices[len(indices) // 2]:
                        frame.save(output.with_suffix(".jpg"))
                    process.stdin.write(frame.tobytes())
            finally:
                process.stdin.close()
                returncode = process.wait()
            if returncode:
                errors.seek(0)
                raise RuntimeError(errors.read().decode(errors="replace"))
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    relative = path.relative_to(ROOT).as_posix()
    return {
        "trace": relative,
        "trace_sha256": sha256(path),
        "config": config_path.relative_to(ROOT).as_posix(),
        "config_sha256": sha256(config_path),
        "scene_xml_sha256": hashlib.sha256(scene.encode()).hexdigest(),
        "block": path.parts[-5],
        "episode": trace["episode_id"],
        "policy": trace["metadata"]["policy_id"],
        "view": view,
        "terminal_status": trace["terminal_status"],
        "recorded_duration_s": float(times[-1]),
        "frames": len(indices),
        "video": output.relative_to(args.output).as_posix(),
        "video_sha256": sha256(output),
        "poster": output.with_suffix(".jpg").relative_to(args.output).as_posix(),
        "poster_sha256": sha256(output.with_suffix(".jpg")),
    }


def write_gallery(output: Path, clips: list[dict], montages: list[dict]) -> None:
    cards = []
    for clip in [*montages, *clips]:
        title = html.escape(
            clip.get("title", f"{BLOCKS[clip['block']]} / {clip.get('episode', '')}")
        )
        video = html.escape(clip["video"], quote=True)
        poster = html.escape(clip.get("poster", ""), quote=True)
        cards.append(
            f'<article><h2>{title}</h2><video controls preload="metadata" poster="{poster}" src="{video}"></video>'
            f'<p><a href="{video}">Download MP4</a></p></article>'
        )
    output.joinpath("index.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>AsimovBM episode videos</title><style>"
        "body{font:17px system-ui;margin:32px auto;padding:0 20px;max-width:1100px;color:#192b3b}"
        "main{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:24px}"
        "article{border:1px solid #cbd3d9;border-radius:10px;padding:16px}h2{font-size:18px}"
        "video{width:100%;background:#122231}a{color:#135c91}</style>"
        '<h1>AsimovBM episode videos</h1>'
        '<p>Two policies, three scenarios, two viewpoints. Playback is real time (1x).</p>'
        '<p><a href="manifest.json">Sources and rendering settings</a> · '
        '<a href="../historical-videos/index.html">Archived videos</a> · '
        '<a href="../../paper/README.md#view-or-regenerate-episode-videos">Reproduction guide</a></p><main>'
        + "".join(cards)
        + "</main></html>"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/reconstructed-videos")
    parser.add_argument("--block", choices=BLOCKS, action="append")
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--width", type=int, default=960)
    parser.add_argument("--height", type=int, default=540)
    args = parser.parse_args()
    if args.fps < 1 or args.width < 640 or args.height < 360 or args.width % 2 or args.height % 2:
        parser.error("require fps >= 1 and even dimensions >= 640x360")
    if not ROBOT_XML.exists():
        parser.error(
            "initialize pinned RoboJuDo assets: git submodule update --init g1_slam/third_party/RoboJuDo"
        )
    if shutil.which("ffmpeg") is None:
        parser.error("ffmpeg with libx264 is required")
    os.environ.setdefault("MUJOCO_GL", "egl")
    import mujoco

    args.output = args.output.resolve()
    protected = (ROOT / "paper", ROOT / "artifacts/local-validation", ROOT / "artifacts/survey")
    if any(
        args.output == p or p in args.output.parents or args.output in p.parents for p in protected
    ):
        parser.error("choose a separate output directory for reconstructions")
    if args.block and len(set(args.block)) != len(args.block):
        parser.error("choose each block only once")
    args.output.mkdir(parents=True, exist_ok=True)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
    clips, montages = [], []
    for block in args.block or BLOCKS:
        paths = sorted(
            (ROOT / "artifacts/local-validation" / block).glob("*/*/iteration-*/trace.json")
        )
        if len(paths) != 3:
            raise ValueError(f"expected three curated traces for {block}, found {len(paths)}")
        for path in paths:
            destination = args.output / block / f"{path.parent.parent.name}.mp4"
            print(f"Rendering {block}: {path.parent.parent.name}", flush=True)
            clips.append(render_trace(path, destination, args, font))
        destination = args.output / f"{block}-three-scenarios.mp4"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", dir=args.output) as listing:
            for clip in clips[-3:]:
                listing.write(f"file '{clip['video']}'\n")
            listing.flush()
            subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    listing.name,
                    "-c",
                    "copy",
                    "-movflags",
                    "+faststart",
                    str(destination),
                ],
                check=True,
            )
        montages.append(
            {
                "block": block,
                "title": BLOCKS[block] + " / all three scenarios",
                "video": destination.name,
                "video_sha256": sha256(destination),
                "source_videos": [c["video"] for c in clips[-3:]],
            }
        )
    model_assets = [ROBOT_XML, *sorted((ROBOT_XML.parent / "meshes").glob("*.STL"))]
    manifest = {
        "schema": "asimovbm.archived_trace_replay.v1",
        "original_survey_stimuli": False,
        "method": "Recorded full qpos and NPC poses; mj_forward only, no dynamics/policy rerun",
        "sampling": "Nearest recorded sample at 1x playback; final frame uses terminal pose",
        "fps": args.fps,
        "width": args.width,
        "height": args.height,
        "mujoco_version": mujoco.__version__,
        "rendering": {
            "shadows": False,
            "reflections": False,
            "multisampling": False,
            "duplicate_collision_visuals": False,
            "contact_solving": False,
        },
        "ffmpeg_version": subprocess.check_output(["ffmpeg", "-version"], text=True).splitlines()[
            0
        ],
        "encoding": {"codec": "libx264", "crf": 23, "preset": "fast", "pixel_format": "yuv420p"},
        "generator_sha256": sha256(Path(__file__)),
        "scene_helper_sha256": {
            name: sha256(ROOT / "g1_slam/src/g1_slam" / name)
            for name in ("scene_visuals.py", "robojudo_backend.py", "mujoco_runner.py")
        },
        "robojudo_commit": subprocess.check_output(
            ["git", "-C", str(ROBOT_XML.parents[3]), "rev-parse", "HEAD"], text=True
        ).strip(),
        "model_assets": {p.relative_to(ROOT).as_posix(): sha256(p) for p in model_assets},
        "clips": clips,
        "montages": montages,
    }
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    write_gallery(args.output, clips, montages)
    print(f"Gallery: {args.output / 'index.html'}")


if __name__ == "__main__":
    main()
