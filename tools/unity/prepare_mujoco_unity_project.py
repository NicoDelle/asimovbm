#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import pickle
import shutil
import struct
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path, PurePosixPath

DEFAULT_MUJOCO_VERSION = "3.8.1"
MUJOCO_REPO_GIT_URL = "https://github.com/google-deepmind/mujoco.git"
MUJOCO_RELEASE_BASE_URL = "https://github.com/google-deepmind/mujoco/releases/download"
MUJOCO_SOURCE_ZIP_URL = "https://github.com/google-deepmind/mujoco/archive/refs/tags"
PACKAGE_NAME = "org.mujoco"
STL_BINARY_HEADER = b"asimovbm binary stl".ljust(80, b" ")


class PreparationError(RuntimeError):
    """Raised when the Unity project cannot be safely prepared."""


@dataclass(frozen=True)
class PreparationConfig:
    unity_project: Path
    repo_root: Path
    mujoco_version: str = DEFAULT_MUJOCO_VERSION
    package_mode: str = "auto"
    source_mjcf: Path | None = None
    native_archive: Path | None = None
    package_archive: Path | None = None
    mimickit_data_root: Path | None = None
    stage_real_g1: bool = False
    g1_motions: tuple[str, ...] = ("g1_walk", "g1_run")
    dry_run: bool = False
    skip_dll: bool = False


@dataclass
class PreparationSummary:
    unity_project: Path
    mujoco_version: str
    package_mode: str
    changes: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def add_change(self, message: str) -> None:
        self.changes.append(message)

    def add_note(self, message: str) -> None:
        self.notes.append(message)

    def render(self) -> str:
        lines = [
            f"Unity project: {self.unity_project}",
            f"MuJoCo version: {self.mujoco_version}",
            f"Package mode: {self.package_mode}",
            "",
            "Changes:",
        ]
        lines.extend(f"- {change}" for change in (self.changes or ["No file changes needed."]))
        if self.notes:
            lines.append("")
            lines.append("Notes:")
            lines.extend(f"- {note}" for note in self.notes)
        return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    try:
        config = parse_args(argv)
        summary = prepare_unity_project(config)
    except PreparationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(summary.render())
    return 0


def parse_args(argv: list[str] | None = None) -> PreparationConfig:
    parser = argparse.ArgumentParser(
        description="Prepare a Unity project to import and run the MuJoCo AsimovBM scene."
    )
    parser.add_argument(
        "--unity-project",
        required=True,
        type=Path,
        help="Unity project root, for example /mnt/d/_PROJECTS/Unity/AsimovBM",
    )
    parser.add_argument(
        "--mujoco-version",
        default=DEFAULT_MUJOCO_VERSION,
        help=f"MuJoCo release tag to pin. Default: {DEFAULT_MUJOCO_VERSION}",
    )
    parser.add_argument(
        "--package-mode",
        choices=("auto", "git", "embedded"),
        default="auto",
        help="Use Unity's Git dependency, embed the package under Packages/, or auto-detect.",
    )
    parser.add_argument(
        "--source-mjcf",
        type=Path,
        help="MJCF scene to copy into the Unity project. Defaults to g1_slam/assets/g1_kinematic.xml.",
    )
    parser.add_argument(
        "--native-archive",
        type=Path,
        help="Use a local MuJoCo Windows zip instead of downloading the official release asset.",
    )
    parser.add_argument(
        "--package-archive",
        type=Path,
        help="Use a local MuJoCo source zip when --package-mode embedded is selected.",
    )
    parser.add_argument(
        "--mimickit-data-root",
        type=Path,
        help=(
            "Root of MimicKit_Data. Defaults to /home/anthor/projects/neogenesis/MimicKit_Data "
            "when --stage-real-g1 is used."
        ),
    )
    parser.add_argument(
        "--stage-real-g1",
        action="store_true",
        help="Copy the real MimicKit G1 MJCF/USD/meshes and convert selected motion PKLs to CSV.",
    )
    parser.add_argument(
        "--g1-motion",
        action="append",
        dest="g1_motions",
        help=(
            "G1 motion name to convert from MimicKit_Data/motions/g1/<name>.pkl. "
            "May be repeated. Defaults to g1_walk and g1_run."
        ),
    )
    parser.add_argument(
        "--skip-dll",
        action="store_true",
        help="Do not copy or download mujoco.dll. Useful for package-only dry runs.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report intended changes without modifying the Unity project.",
    )
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[2]
    return PreparationConfig(
        unity_project=args.unity_project.expanduser().resolve(),
        repo_root=repo_root,
        mujoco_version=args.mujoco_version,
        package_mode=args.package_mode,
        source_mjcf=args.source_mjcf.expanduser().resolve() if args.source_mjcf else None,
        native_archive=args.native_archive.expanduser().resolve() if args.native_archive else None,
        package_archive=args.package_archive.expanduser().resolve() if args.package_archive else None,
        mimickit_data_root=(
            args.mimickit_data_root.expanduser().resolve() if args.mimickit_data_root else None
        ),
        stage_real_g1=args.stage_real_g1,
        g1_motions=tuple(args.g1_motions) if args.g1_motions else ("g1_walk", "g1_run"),
        dry_run=args.dry_run,
        skip_dll=args.skip_dll,
    )


def prepare_unity_project(config: PreparationConfig) -> PreparationSummary:
    if not config.unity_project.exists():
        raise PreparationError(f"Unity project root does not exist: {config.unity_project}")

    manifest_path = config.unity_project / "Packages" / "manifest.json"
    if not manifest_path.exists():
        raise PreparationError(f"Unity package manifest not found: {manifest_path}")

    package_mode = resolve_package_mode(config.package_mode)
    summary = PreparationSummary(config.unity_project, config.mujoco_version, package_mode)

    if package_mode == "git":
        configure_manifest_git_dependency(manifest_path, config.mujoco_version, config.dry_run, summary)
    else:
        prepare_embedded_package(config, summary)

    stage_mjcf(config, summary)
    if config.stage_real_g1:
        stage_real_g1_assets(config, summary)
    stage_unity_templates(config, summary)
    write_unity_runtime_settings(config, summary)
    prepare_native_dll(config, summary)
    write_unity_readme(config, package_mode, summary)
    remove_obsolete_unity_files(config, summary)
    return summary


def resolve_package_mode(requested: str) -> str:
    if requested != "auto":
        return requested
    return "git" if windows_git_available() else "embedded"


def windows_git_available() -> bool:
    windows_cwd = Path("/mnt/c/Windows/System32")
    try:
        result = subprocess.run(
            ["cmd.exe", "/c", "where", "git"],
            cwd=windows_cwd if windows_cwd.exists() else None,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def configure_manifest_git_dependency(
    manifest_path: Path,
    mujoco_version: str,
    dry_run: bool,
    summary: PreparationSummary,
) -> None:
    manifest = load_manifest(manifest_path)
    dependencies = manifest.setdefault("dependencies", {})
    if not isinstance(dependencies, dict):
        raise PreparationError(f"{manifest_path} has a non-object dependencies field")

    reference = mujoco_package_git_reference(mujoco_version)
    current = dependencies.get(PACKAGE_NAME)
    if current == reference:
        summary.add_note(f"{PACKAGE_NAME} is already pinned to {reference}")
        return

    if dry_run:
        summary.add_change(f"Would set {PACKAGE_NAME} dependency to {reference}")
        return

    dependencies[PACKAGE_NAME] = reference
    write_json(manifest_path, manifest)
    if current:
        summary.add_change(f"Updated {PACKAGE_NAME} dependency from {current} to {reference}")
    else:
        summary.add_change(f"Added {PACKAGE_NAME} dependency: {reference}")


def load_manifest(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PreparationError(f"Could not parse {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PreparationError(f"{path} must contain a JSON object")
    return data


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def mujoco_package_git_reference(version: str) -> str:
    return f"{MUJOCO_REPO_GIT_URL}?path=/unity#{version}"


def prepare_embedded_package(config: PreparationConfig, summary: PreparationSummary) -> None:
    destination = config.unity_project / "Packages" / PACKAGE_NAME
    if config.dry_run:
        summary.add_change(f"Would prepare embedded package at {relative_to_project(destination, config)}")
        return

    with tempfile.TemporaryDirectory(prefix="mujoco-unity-package-") as tmp:
        archive_path = config.package_archive or download_source_archive(
            config.mujoco_version, Path(tmp)
        )
        unity_package_dir = extract_unity_package_from_archive(archive_path, Path(tmp) / "src")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(unity_package_dir, destination, dirs_exist_ok=True)

    summary.add_change(f"Prepared embedded package at {relative_to_project(destination, config)}")
    summary.add_note(
        "Embedded packages override manifest dependencies with the same package name in Unity."
    )


def download_source_archive(version: str, destination_dir: Path) -> Path:
    url = f"{MUJOCO_SOURCE_ZIP_URL}/{version}.zip"
    destination = destination_dir / f"mujoco-{version}-source.zip"
    download_file(url, destination)
    return destination


def extract_unity_package_from_archive(archive_path: Path, destination_dir: Path) -> Path:
    if not archive_path.exists():
        raise PreparationError(f"Package archive does not exist: {archive_path}")

    unity_prefix: tuple[str, ...] | None = None
    with zipfile.ZipFile(archive_path) as archive:
        for name in archive.namelist():
            parts = archive_path_parts(name)
            if len(parts) >= 2 and parts[-2:] == ("unity", "package.json"):
                unity_prefix = parts[:-1]
                break
        if unity_prefix is None:
            raise PreparationError(f"Could not find unity/package.json in {archive_path}")

        destination_dir.mkdir(parents=True, exist_ok=True)
        for member in archive.infolist():
            parts = archive_path_parts(member.filename)
            if len(parts) < len(unity_prefix) or parts[: len(unity_prefix)] != unity_prefix:
                continue
            relative_parts = parts[len(unity_prefix) :]
            if not relative_parts:
                continue
            target = destination_dir.joinpath(*relative_parts)
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, target.open("wb") as destination:
                shutil.copyfileobj(source, destination)

    package_json = destination_dir / "package.json"
    validate_package_json(package_json)
    return destination_dir


def validate_package_json(path: Path) -> None:
    package = load_manifest(path)
    if package.get("name") != PACKAGE_NAME:
        raise PreparationError(f"{path} is not the {PACKAGE_NAME} package")


def stage_mjcf(config: PreparationConfig, summary: PreparationSummary) -> None:
    source = config.source_mjcf or config.repo_root / "g1_slam" / "assets" / "g1_kinematic.xml"
    if not source.exists():
        raise PreparationError(f"Source MJCF does not exist: {source}")

    destination = (
        config.unity_project
        / "Assets"
        / "AsimovBM"
        / "MuJoCo"
        / "Models"
        / source.name
    )
    if config.dry_run:
        summary.add_change(f"Would copy {source} to {relative_to_project(destination, config)}")
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    summary.add_change(f"Copied MJCF to {relative_to_project(destination, config)}")


def stage_real_g1_assets(config: PreparationConfig, summary: PreparationSummary) -> None:
    data_root = resolve_mimickit_data_root(config)
    source_g1 = data_root / "assets" / "g1"
    required_files = [
        source_g1 / "g1.xml",
        source_g1 / "g1_mesh.xml",
        source_g1 / "g1.usd",
        source_g1 / "LICENSE.txt",
    ]
    missing = [str(path) for path in required_files if not path.exists()]
    meshes_dir = source_g1 / "meshes"
    if not meshes_dir.exists():
        missing.append(str(meshes_dir))
    if missing:
        raise PreparationError("MimicKit G1 source is incomplete: " + ", ".join(missing))

    model_destination = config.unity_project / "Assets" / "AsimovBM" / "MuJoCo" / "Models" / "g1"
    motion_destination = config.unity_project / "Assets" / "AsimovBM" / "MuJoCo" / "Motions" / "g1"

    if config.dry_run:
        summary.add_change(
            f"Would copy real G1 model assets to {relative_to_project(model_destination, config)}"
        )
        for motion_name in config.g1_motions:
            summary.add_change(
                "Would convert "
                f"{data_root / 'motions' / 'g1' / f'{motion_name}.pkl'} "
                f"to {relative_to_project(motion_destination / f'{motion_name}.csv', config)}"
            )
        return

    model_destination.mkdir(parents=True, exist_ok=True)
    for source_file in required_files:
        destination_file = model_destination / source_file.name
        if source_file.suffix.lower() == ".xml":
            copy_mjcf_with_lowercase_stl_refs(source_file, destination_file)
        else:
            shutil.copy2(source_file, destination_file)
    copy_meshes_with_lowercase_stl_extensions(meshes_dir, model_destination / "meshes")
    summary.add_change(f"Copied real G1 model assets to {relative_to_project(model_destination, config)}")

    motion_destination.mkdir(parents=True, exist_ok=True)
    for motion_name in config.g1_motions:
        source_motion = data_root / "motions" / "g1" / f"{motion_name}.pkl"
        if not source_motion.exists():
            raise PreparationError(f"MimicKit G1 motion does not exist: {source_motion}")
        csv_path = motion_destination / f"{motion_name}.csv"
        fps, frame_count = convert_mimickit_motion_to_csv(source_motion, csv_path)
        summary.add_change(
            "Converted "
            f"{source_motion.name} to {relative_to_project(csv_path, config)} "
            f"({frame_count} frames at {fps} fps)"
        )

    summary.add_note("Real G1 import path: Assets/AsimovBM/MuJoCo/Models/g1/g1.xml")


def copy_mjcf_with_lowercase_stl_refs(source: Path, destination: Path) -> None:
    text = source.read_text(encoding="utf-8")
    destination.write_text(text.replace(".STL", ".stl"), encoding="utf-8")


def copy_meshes_with_lowercase_stl_extensions(source_dir: Path, destination_dir: Path) -> None:
    if destination_dir.exists():
        shutil.rmtree(destination_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    for source in sorted(path for path in source_dir.iterdir() if path.is_file()):
        destination_name = source.name
        if source.suffix.lower() == ".stl":
            destination_name = source.with_suffix(".stl").name
            normalize_stl_for_unity(source, destination_dir / destination_name)
        else:
            shutil.copy2(source, destination_dir / destination_name)


def normalize_stl_for_unity(source: Path, destination: Path) -> None:
    data = source.read_bytes()
    if is_binary_stl(data):
        destination.write_bytes(STL_BINARY_HEADER + data[80:])
    else:
        destination.write_bytes(serialize_ascii_stl_as_binary(data))
    shutil.copystat(source, destination)


def is_binary_stl(data: bytes) -> bool:
    if len(data) < 84:
        return False
    triangle_count = struct.unpack_from("<I", data, 80)[0]
    return len(data) == 84 + (triangle_count * 50)


def serialize_ascii_stl_as_binary(data: bytes) -> bytes:
    triangles = parse_ascii_stl(data)
    output = bytearray(STL_BINARY_HEADER)
    output.extend(struct.pack("<I", len(triangles)))
    for normal, vertices in triangles:
        output.extend(
            struct.pack(
                "<12fH",
                *normal,
                *vertices[0],
                *vertices[1],
                *vertices[2],
                0,
            )
        )
    return bytes(output)


def parse_ascii_stl(data: bytes) -> list[tuple[tuple[float, float, float], tuple[tuple[float, float, float], ...]]]:
    text = data.decode("utf-8", errors="replace")
    triangles: list[
        tuple[tuple[float, float, float], tuple[tuple[float, float, float], ...]]
    ] = []
    normal = (0.0, 0.0, 0.0)
    vertices: list[tuple[float, float, float]] = []

    for raw_line in text.splitlines():
        parts = raw_line.strip().split()
        if not parts:
            continue
        keyword = parts[0].lower()
        if keyword == "facet" and len(parts) >= 5 and parts[1].lower() == "normal":
            normal = parse_stl_float_triplet(parts[2:5])
            vertices = []
        elif keyword == "vertex" and len(parts) >= 4:
            vertices.append(parse_stl_float_triplet(parts[1:4]))
        elif keyword == "endfacet":
            if len(vertices) == 3:
                triangles.append((normal, tuple(vertices)))
            vertices = []

    return triangles


def parse_stl_float_triplet(values: list[str]) -> tuple[float, float, float]:
    return (float(values[0]), float(values[1]), float(values[2]))


def stage_unity_templates(config: PreparationConfig, summary: PreparationSummary) -> None:
    template_root = config.repo_root / "tools" / "unity" / "templates" / "Assets"
    if not template_root.exists():
        raise PreparationError(f"Unity template root does not exist: {template_root}")

    staged_count = 0
    for source in sorted(path for path in template_root.rglob("*") if path.is_file()):
        relative = source.relative_to(template_root)
        destination = config.unity_project / "Assets" / relative
        if config.dry_run:
            summary.add_change(f"Would copy Unity template to {relative_to_project(destination, config)}")
            staged_count += 1
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.read_bytes() == source.read_bytes():
            continue
        shutil.copy2(source, destination)
        staged_count += 1

    if staged_count:
        summary.add_change(f"Staged {staged_count} Unity template file(s) under Assets/AsimovBM")
    else:
        summary.add_note("Unity template files are already up to date.")


def write_unity_runtime_settings(config: PreparationConfig, summary: PreparationSummary) -> None:
    settings_path = (
        config.unity_project
        / "Assets"
        / "AsimovBM"
        / "RuntimeSettings"
        / "asimovbm_unity_settings.json"
    )
    payload = {
        "schema_version": "asimovbm.unity_runtime_settings.v1",
        "repo_root_wsl": str(config.repo_root),
        "python_executable": sys.executable,
        "artifact_root_wsl": "artifacts/unity-validation",
        "artifact_root_project": "Artifacts/AsimovBM/Unity",
        "run_python_postprocess": True,
    }
    if config.dry_run:
        summary.add_change(f"Would write Unity runtime settings at {relative_to_project(settings_path, config)}")
        return

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(settings_path, payload)
    summary.add_change(f"Wrote Unity runtime settings at {relative_to_project(settings_path, config)}")


def resolve_mimickit_data_root(config: PreparationConfig) -> Path:
    if config.mimickit_data_root:
        data_root = config.mimickit_data_root
    else:
        data_root = Path("/home/anthor/projects/neogenesis/MimicKit_Data")
    if not data_root.exists():
        raise PreparationError(
            "MimicKit_Data root does not exist. Pass --mimickit-data-root or install it at "
            f"{data_root}"
        )
    return data_root


def convert_mimickit_motion_to_csv(source_motion: Path, csv_path: Path) -> tuple[int, int]:
    with source_motion.open("rb") as fh:
        data = pickle.load(fh)

    if isinstance(data, dict):
        fps = int(data["fps"])
        frames = data["frames"]
    else:
        fps = int(data.fps)
        frames = data.frames

    if len(frames) == 0:
        raise PreparationError(f"Motion has no frames: {source_motion}")

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        for frame in frames:
            if len(frame) < 7:
                raise PreparationError(f"Motion frame is too short in {source_motion}")
            root_pos = [float(value) for value in frame[0:3]]
            quat_xyzw = axis_angle_to_quaternion_xyzw(frame[3:6])
            joints = [float(value) for value in frame[6:]]
            writer.writerow(format_float(value) for value in [*root_pos, *quat_xyzw, *joints])

    return fps, len(frames)


def axis_angle_to_quaternion_xyzw(axis_angle: list[float]) -> list[float]:
    x, y, z = (float(value) for value in axis_angle)
    angle = math.sqrt((x * x) + (y * y) + (z * z))
    if angle < 1e-9:
        return [0.0, 0.0, 0.0, 1.0]

    scale = math.sin(angle / 2.0) / angle
    return [x * scale, y * scale, z * scale, math.cos(angle / 2.0)]


def format_float(value: float) -> str:
    return f"{value:.8f}"


def prepare_native_dll(config: PreparationConfig, summary: PreparationSummary) -> None:
    destination = config.unity_project / "Assets" / "Plugins" / "x86_64" / "mujoco.dll"
    if config.skip_dll:
        summary.add_note("Skipped native DLL preparation by request.")
        return
    if config.dry_run:
        summary.add_change(f"Would place native DLL at {relative_to_project(destination, config)}")
        return

    with tempfile.TemporaryDirectory(prefix="mujoco-windows-") as tmp:
        if config.native_archive:
            archive_path = config.native_archive
        else:
            archive_path = download_windows_archive(config.mujoco_version, Path(tmp))
            summary.add_note(
                "Downloaded and verified official native archive "
                f"{windows_archive_filename(config.mujoco_version)}"
            )
        dll_bytes = read_mujoco_dll_from_archive(archive_path)

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(dll_bytes)
    summary.add_change(f"Placed native DLL at {relative_to_project(destination, config)}")


def download_windows_archive(version: str, destination_dir: Path) -> Path:
    filename = windows_archive_filename(version)
    archive_url = windows_archive_url(version)
    checksum_url = f"{archive_url}.sha256"
    archive_path = destination_dir / filename
    checksum_path = destination_dir / f"{filename}.sha256"

    download_file(archive_url, archive_path)
    download_file(checksum_url, checksum_path)
    expected = parse_sha256_file(checksum_path, expected_filename=filename)
    actual = sha256_file(archive_path)
    if actual != expected:
        raise PreparationError(
            f"Checksum mismatch for {filename}: expected {expected}, got {actual}"
        )
    return archive_path


def windows_archive_filename(version: str) -> str:
    return f"mujoco-{version}-windows-x86_64.zip"


def windows_archive_url(version: str) -> str:
    return f"{MUJOCO_RELEASE_BASE_URL}/{version}/{windows_archive_filename(version)}"


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            destination.write_bytes(response.read())
    except OSError as exc:
        raise PreparationError(f"Could not download {url}: {exc}") from exc


def parse_sha256_file(path: Path, *, expected_filename: str) -> str:
    text = path.read_text(encoding="utf-8").strip()
    parts = text.split()
    if len(parts) < 2:
        raise PreparationError(f"Invalid checksum file: {path}")
    digest, filename = parts[0], parts[-1]
    if filename != expected_filename:
        raise PreparationError(
            f"Checksum file {path} refers to {filename}, expected {expected_filename}"
        )
    if len(digest) != 64:
        raise PreparationError(f"Invalid sha256 digest in {path}: {digest}")
    return digest.lower()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_mujoco_dll_from_archive(archive_path: Path) -> bytes:
    if not archive_path.exists():
        raise PreparationError(f"Native archive does not exist: {archive_path}")

    with zipfile.ZipFile(archive_path) as archive:
        candidates = [
            name
            for name in archive.namelist()
            if PurePosixPath(name.replace("\\", "/")).name.lower() == "mujoco.dll"
        ]
        if not candidates:
            raise PreparationError(f"Could not find mujoco.dll in {archive_path}")
        preferred = next((name for name in candidates if "/bin/" in name), candidates[0])
        return archive.read(preferred)


def write_unity_readme(
    config: PreparationConfig,
    package_mode: str,
    summary: PreparationSummary,
) -> None:
    readme_path = config.unity_project / "Assets" / "AsimovBM" / "MuJoCo" / "README.md"
    model_path = "Assets/AsimovBM/MuJoCo/Models/g1_kinematic.xml"
    dll_path = "Assets/Plugins/x86_64/mujoco.dll"
    content = f"""# AsimovBM MuJoCo Unity Setup

Prepared on {date.today().isoformat()} from the AsimovBM WSL workspace.

- MuJoCo version: `{config.mujoco_version}`
- Package mode: `{package_mode}`
- First import model: `{model_path}`
- Real G1 import model: `{real_g1_model_path(config)}`
- Real G1 motion clips: `{real_g1_motion_path(config)}`
- Native Windows DLL: `{dll_path}`
- Native archive source: `{native_archive_source(config)}`

## Unity Editor Handoff

1. Open this Unity project in Unity.
2. Wait for package resolution and C# compilation to finish.
3. Open the Console and enable Error Pause.
4. Use `Assets > Import MuJoCo Scene` and select `{model_path}` for the quick static check.
   For the real MimicKit robot, select `{real_g1_model_path(config)}`.
5. Save the imported scene as `Assets/Scenes/AsimovMujoco.unity`.
6. Run `AsimovBM > MuJoCo > Repair Materials And Lighting`.
7. Run `AsimovBM > MuJoCo > Add Runtime Motion Diagnostics`.
8. Press Play. The diagnostic marker should move in any scene. The G1 robot itself moves only
   when the imported model has the real G1 free root plus 29 joints.

If package resolution fails in Git mode, rerun the preparation tool with
`--package-mode embedded` and reopen Unity.
"""
    if config.dry_run:
        summary.add_change(f"Would write Unity setup README at {relative_to_project(readme_path, config)}")
        return

    readme_path.parent.mkdir(parents=True, exist_ok=True)
    readme_path.write_text(content, encoding="utf-8")
    summary.add_change(f"Wrote setup README at {relative_to_project(readme_path, config)}")


def remove_obsolete_unity_files(config: PreparationConfig, summary: PreparationSummary) -> None:
    obsolete = [
        config.unity_project / "Assets" / "AsimovBM" / "Editor" / "AsimovMujocoVisualSetup.cs",
        config.unity_project / "Assets" / "AsimovBM" / "Scripts" / "AsimovUnityRunProbe.cs",
    ]
    removed = 0
    for path in obsolete:
        for candidate in (path, path.with_suffix(path.suffix + ".meta")):
            if not candidate.exists():
                continue
            if config.dry_run:
                summary.add_change(f"Would remove obsolete Unity file {relative_to_project(candidate, config)}")
                removed += 1
                continue
            candidate.unlink()
            removed += 1
    if removed and not config.dry_run:
        summary.add_change(f"Removed {removed} obsolete Unity generated file(s)")


def relative_to_project(path: Path, config: PreparationConfig) -> str:
    try:
        return str(path.relative_to(config.unity_project))
    except ValueError:
        return str(path)


def archive_path_parts(name: str) -> tuple[str, ...]:
    return PurePosixPath(name.replace("\\", "/")).parts


def native_archive_source(config: PreparationConfig) -> str:
    if config.skip_dll:
        return "skipped"
    if config.native_archive:
        return str(config.native_archive)
    return f"{windows_archive_url(config.mujoco_version)} verified with matching .sha256"


def real_g1_model_path(config: PreparationConfig) -> str:
    if not config.stage_real_g1:
        return "not staged"
    return "Assets/AsimovBM/MuJoCo/Models/g1/g1.xml"


def real_g1_motion_path(config: PreparationConfig) -> str:
    if not config.stage_real_g1:
        return "not staged"
    return "Assets/AsimovBM/MuJoCo/Motions/g1/*.csv"


if __name__ == "__main__":
    raise SystemExit(main())
