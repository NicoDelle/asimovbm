from __future__ import annotations

import importlib.util
import json
import pickle
import struct
import sys
import zipfile
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "tools/unity/prepare_mujoco_unity_project.py"
SPEC = importlib.util.spec_from_file_location("prepare_mujoco_unity_project", MODULE_PATH)
assert SPEC is not None
prepare_module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = prepare_module
SPEC.loader.exec_module(prepare_module)

PreparationConfig = prepare_module.PreparationConfig
PreparationError = prepare_module.PreparationError
prepare_unity_project = prepare_module.prepare_unity_project


def make_unity_project(tmp_path: Path) -> Path:
    project = tmp_path / "UnityProject"
    packages = project / "Packages"
    packages.mkdir(parents=True)
    (packages / "manifest.json").write_text(
        json.dumps(
            {
                "dependencies": {
                    "com.unity.inputsystem": "1.19.0",
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return project


def make_repo_root(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    assets = repo / "g1_slam" / "assets"
    assets.mkdir(parents=True)
    (assets / "g1_kinematic.xml").write_text("<mujoco model=\"test\"/>\n", encoding="utf-8")
    template_dir = repo / "tools" / "unity" / "templates" / "Assets" / "AsimovBM" / "Scripts"
    template_dir.mkdir(parents=True)
    (template_dir / "AsimovTemplateProbe.cs").write_text("// template\n", encoding="utf-8")
    return repo


def make_native_archive(tmp_path: Path, *, include_dll: bool = True) -> Path:
    archive_path = tmp_path / "mujoco-test-windows-x86_64.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        if include_dll:
            archive.writestr("mujoco-test\\bin\\mujoco.dll", b"dll-bytes")
        else:
            archive.writestr("mujoco-test/bin/README.txt", "missing")
    return archive_path


def make_package_archive(tmp_path: Path) -> Path:
    archive_path = tmp_path / "mujoco-source.zip"
    package_json = {
        "name": "org.mujoco",
        "displayName": "MuJoCo",
        "version": "test",
    }
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("mujoco-test/unity/package.json", json.dumps(package_json))
        archive.writestr("mujoco-test/unity/Runtime/MjScene.cs", "// test\n")
    return archive_path


def make_ascii_stl() -> str:
    return """solid pelvis
facet normal 0 0 1
  outer loop
    vertex 0 0 0
    vertex 1 0 0
    vertex 0 1 0
  endloop
endfacet
endsolid pelvis
"""


def make_binary_stl_with_solid_header() -> bytes:
    header = b"solid binary header".ljust(80, b" ")
    triangle = struct.pack(
        "<12fH",
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0,
    )
    return header + struct.pack("<I", 1) + triangle


def make_mimickit_data_root(tmp_path: Path) -> Path:
    data_root = tmp_path / "MimicKit_Data"
    g1_assets = data_root / "assets" / "g1"
    meshes = g1_assets / "meshes"
    meshes.mkdir(parents=True)
    (g1_assets / "g1.xml").write_text(
        '<mujoco model="g1"><asset><mesh file="meshes/pelvis.STL"/></asset></mujoco>\n',
        encoding="utf-8",
    )
    (g1_assets / "g1_mesh.xml").write_text(
        '<mujoco model="g1_mesh"><asset><mesh file="meshes/pelvis.STL"/></asset></mujoco>\n',
        encoding="utf-8",
    )
    (g1_assets / "g1.usd").write_text("#usda 1.0\n", encoding="utf-8")
    (g1_assets / "LICENSE.txt").write_text("test license\n", encoding="utf-8")
    (meshes / "pelvis.STL").write_text(make_ascii_stl(), encoding="utf-8")

    motions = data_root / "motions" / "g1"
    motions.mkdir(parents=True)
    frame = [
        1.0,
        2.0,
        3.0,
        0.0,
        0.0,
        3.141592653589793,
        *[0.1 for _ in range(29)],
    ]
    with (motions / "g1_walk.pkl").open("wb") as fh:
        pickle.dump({"fps": 120, "loop_mode": 1, "frames": [frame]}, fh)
    return data_root


def test_git_mode_updates_manifest_and_stages_assets(tmp_path: Path) -> None:
    unity_project = make_unity_project(tmp_path)
    repo_root = make_repo_root(tmp_path)
    native_archive = make_native_archive(tmp_path)

    summary = prepare_unity_project(
        PreparationConfig(
            unity_project=unity_project,
            repo_root=repo_root,
            mujoco_version="3.8.1",
            package_mode="git",
            native_archive=native_archive,
        )
    )

    manifest = json.loads((unity_project / "Packages" / "manifest.json").read_text())
    assert manifest["dependencies"]["com.unity.inputsystem"] == "1.19.0"
    assert (
        manifest["dependencies"]["org.mujoco"]
        == "https://github.com/google-deepmind/mujoco.git?path=/unity#3.8.1"
    )
    assert (unity_project / "Assets/AsimovBM/MuJoCo/Models/g1_kinematic.xml").read_text() == (
        repo_root / "g1_slam/assets/g1_kinematic.xml"
    ).read_text()
    assert (unity_project / "Assets/Plugins/x86_64/mujoco.dll").read_bytes() == b"dll-bytes"
    assert (unity_project / "Assets/AsimovBM/MuJoCo/README.md").exists()
    assert (unity_project / "Assets/AsimovBM/Scripts/AsimovTemplateProbe.cs").read_text() == (
        "// template\n"
    )
    runtime_settings = json.loads(
        (unity_project / "Assets/AsimovBM/RuntimeSettings/asimovbm_unity_settings.json").read_text()
    )
    assert runtime_settings["schema_version"] == "asimovbm.unity_runtime_settings.v1"
    assert runtime_settings["repo_root_wsl"] == str(repo_root)
    assert "Added org.mujoco dependency" in summary.render()


def test_stage_real_g1_assets_and_motion_csv(tmp_path: Path) -> None:
    unity_project = make_unity_project(tmp_path)
    repo_root = make_repo_root(tmp_path)
    native_archive = make_native_archive(tmp_path)
    mimickit_data_root = make_mimickit_data_root(tmp_path)

    summary = prepare_unity_project(
        PreparationConfig(
            unity_project=unity_project,
            repo_root=repo_root,
            package_mode="git",
            native_archive=native_archive,
            mimickit_data_root=mimickit_data_root,
            stage_real_g1=True,
            g1_motions=("g1_walk",),
        )
    )

    real_model = unity_project / "Assets/AsimovBM/MuJoCo/Models/g1/g1.xml"
    mesh = unity_project / "Assets/AsimovBM/MuJoCo/Models/g1/meshes/pelvis.stl"
    motion_csv = unity_project / "Assets/AsimovBM/MuJoCo/Motions/g1/g1_walk.csv"
    assert "pelvis.stl" in real_model.read_text(encoding="utf-8")
    assert mesh.exists()
    assert mesh.read_bytes()[:5] != b"solid"
    assert len(mesh.read_bytes()) == 134
    row = motion_csv.read_text(encoding="utf-8").strip().split(",")
    assert len(row) == 36
    assert row[:3] == ["1.00000000", "2.00000000", "3.00000000"]
    assert row[3:7] == ["0.00000000", "0.00000000", "1.00000000", "0.00000000"]
    assert "Converted g1_walk.pkl" in summary.render()


def test_stage_real_g1_rewrites_binary_stl_solid_headers(tmp_path: Path) -> None:
    unity_project = make_unity_project(tmp_path)
    repo_root = make_repo_root(tmp_path)
    native_archive = make_native_archive(tmp_path)
    mimickit_data_root = make_mimickit_data_root(tmp_path)
    source_mesh = mimickit_data_root / "assets/g1/meshes/pelvis.STL"
    source_mesh.write_bytes(make_binary_stl_with_solid_header())

    prepare_unity_project(
        PreparationConfig(
            unity_project=unity_project,
            repo_root=repo_root,
            package_mode="git",
            native_archive=native_archive,
            mimickit_data_root=mimickit_data_root,
            stage_real_g1=True,
            g1_motions=("g1_walk",),
        )
    )

    mesh = unity_project / "Assets/AsimovBM/MuJoCo/Models/g1/meshes/pelvis.stl"
    mesh_bytes = mesh.read_bytes()
    assert mesh_bytes[:5] != b"solid"
    assert struct.unpack_from("<I", mesh_bytes, 80)[0] == 1
    assert len(mesh_bytes) == len(make_binary_stl_with_solid_header())


def test_removes_obsolete_unity_scripts(tmp_path: Path) -> None:
    unity_project = make_unity_project(tmp_path)
    repo_root = make_repo_root(tmp_path)
    native_archive = make_native_archive(tmp_path)
    obsolete = unity_project / "Assets/AsimovBM/Editor/AsimovMujocoVisualSetup.cs"
    obsolete.parent.mkdir(parents=True)
    obsolete.write_text("// old\n", encoding="utf-8")
    obsolete.with_suffix(".cs.meta").write_text("meta\n", encoding="utf-8")

    prepare_unity_project(
        PreparationConfig(
            unity_project=unity_project,
            repo_root=repo_root,
            package_mode="git",
            native_archive=native_archive,
        )
    )

    assert not obsolete.exists()
    assert not obsolete.with_suffix(".cs.meta").exists()


def test_git_mode_is_idempotent_for_matching_dependency(tmp_path: Path) -> None:
    unity_project = make_unity_project(tmp_path)
    repo_root = make_repo_root(tmp_path)
    native_archive = make_native_archive(tmp_path)
    manifest_path = unity_project / "Packages" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["dependencies"]["org.mujoco"] = (
        "https://github.com/google-deepmind/mujoco.git?path=/unity#3.8.1"
    )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    summary = prepare_unity_project(
        PreparationConfig(
            unity_project=unity_project,
            repo_root=repo_root,
            package_mode="git",
            native_archive=native_archive,
        )
    )

    assert "already pinned" in summary.render()


def test_embedded_mode_copies_package_without_manifest_dependency(tmp_path: Path) -> None:
    unity_project = make_unity_project(tmp_path)
    repo_root = make_repo_root(tmp_path)
    package_archive = make_package_archive(tmp_path)

    prepare_unity_project(
        PreparationConfig(
            unity_project=unity_project,
            repo_root=repo_root,
            package_mode="embedded",
            package_archive=package_archive,
            skip_dll=True,
        )
    )

    package_path = unity_project / "Packages/org.mujoco"
    assert json.loads((package_path / "package.json").read_text())["name"] == "org.mujoco"
    assert (package_path / "Runtime/MjScene.cs").exists()
    manifest = json.loads((unity_project / "Packages/manifest.json").read_text())
    assert "org.mujoco" not in manifest["dependencies"]


def test_dry_run_does_not_modify_project(tmp_path: Path) -> None:
    unity_project = make_unity_project(tmp_path)
    repo_root = make_repo_root(tmp_path)
    manifest_before = (unity_project / "Packages/manifest.json").read_text()

    summary = prepare_unity_project(
        PreparationConfig(
            unity_project=unity_project,
            repo_root=repo_root,
            package_mode="git",
            dry_run=True,
        )
    )

    assert (unity_project / "Packages/manifest.json").read_text() == manifest_before
    assert not (unity_project / "Assets").exists()
    assert "Would set org.mujoco dependency" in summary.render()


def test_missing_manifest_fails_before_creating_assets(tmp_path: Path) -> None:
    unity_project = tmp_path / "UnityProject"
    unity_project.mkdir()
    repo_root = make_repo_root(tmp_path)

    with pytest.raises(PreparationError, match="manifest not found"):
        prepare_unity_project(
            PreparationConfig(unity_project=unity_project, repo_root=repo_root, package_mode="git")
        )

    assert not (unity_project / "Assets").exists()


def test_malformed_manifest_fails_before_copying_assets(tmp_path: Path) -> None:
    unity_project = make_unity_project(tmp_path)
    (unity_project / "Packages/manifest.json").write_text("{bad json", encoding="utf-8")
    repo_root = make_repo_root(tmp_path)

    with pytest.raises(PreparationError, match="Could not parse"):
        prepare_unity_project(
            PreparationConfig(unity_project=unity_project, repo_root=repo_root, package_mode="git")
        )

    assert not (unity_project / "Assets").exists()


def test_native_archive_without_dll_fails(tmp_path: Path) -> None:
    unity_project = make_unity_project(tmp_path)
    repo_root = make_repo_root(tmp_path)
    native_archive = make_native_archive(tmp_path, include_dll=False)

    with pytest.raises(PreparationError, match="Could not find mujoco.dll"):
        prepare_unity_project(
            PreparationConfig(
                unity_project=unity_project,
                repo_root=repo_root,
                package_mode="git",
                native_archive=native_archive,
            )
        )
