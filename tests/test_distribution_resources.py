"""Check the portable runner from wheel contents, outside the source checkout."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


def test_wheel_preserves_catalog_and_runs_without_checkout(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    source = tmp_path / "source"
    source.mkdir()
    for filename in ("pyproject.toml", "README.md"):
        shutil.copy2(repo / filename, source / filename)
    for directory in ("asimovbm", "g1_slam/src/g1_slam", "g1_slam/config/episodes"):
        shutil.copytree(
            repo / directory,
            source / directory,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )

    # Build only in the staged tree, so this check never mutates checkout build
    # directories or egg-info. No dependency installation or network is needed.
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    subprocess.run(
        [sys.executable, "-c", "from setuptools.build_meta import build_wheel; build_wheel('dist')"],
        cwd=source,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next((source / "dist").glob("*.whl"))
    installed = tmp_path / "installed"
    expected = {}
    with zipfile.ZipFile(wheel) as archive:
        assert not any("third_party/" in name for name in archive.namelist())
        for config in (repo / "g1_slam/config/episodes").glob("*.json"):
            if "point_to_point" not in config.stem:
                continue
            packaged = archive.read(f"g1_slam/episode_configs/{config.name}")
            assert packaged == config.read_bytes()
            expected[config.stem] = hashlib.sha256(packaged).hexdigest()
        assert len(expected) == 6
        archive.extractall(installed)

    # Remove the staged source as well; only unpacked wheel files and the
    # interpreter's existing runtime dependencies remain available to the child.
    shutil.rmtree(source)
    code = f"""
import sys
from pathlib import Path
sys.path.insert(0, {str(installed)!r})
from asimovbm.local_runner import load_default_catalog
from asimovbm.local_runner.runner import LocalRunConfig, run_local_validation
catalog = load_default_catalog()
assert {{s.id: s.checksum_sha256 for s in catalog}} == {expected!r}
for robot in ('g1', 'go2'):
    result = run_local_validation(LocalRunConfig(
        robot_id=robot, visible=False, episode_steps=5,
        artifact_root=Path('artifacts'), run_id=robot,
    ))
    assert len(result.records) == 3
    assert result.report_path.is_file()
    assert result.metrics_csv_path.is_file()
"""
    subprocess.run(
        [sys.executable, "-I", "-c", code],
        cwd=tmp_path,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
