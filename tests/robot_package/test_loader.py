import json
import unittest

from asimovbm_client.robot_package import PackageLoadError, load_robot_package


def write_package(root, config):
    (root / "robot.xml").write_text("<mujoco/>", encoding="utf-8")
    path = root / "robot_package.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def base_config():
    return {
        "name": "testbot",
        "model": {"format": "mjcf", "path": "robot.xml"},
        "sensors": [{"name": "lidar", "kind": "lidar"}],
        "action_mapping": {"mode": "joint_target", "joints": ["left", "right"]},
        "robot_metadata": {"forward_axis": "x+"},
    }


class RobotPackageLoaderTests(unittest.TestCase):
    def test_minimal_package_serializes_to_submission(self):
        with self.subTest():
            from tempfile import TemporaryDirectory
            from pathlib import Path

            with TemporaryDirectory() as tmp:
                root = Path(tmp)
                write_package(root, base_config())

                package = load_robot_package(root)

            self.assertEqual(package.name, "testbot")
            self.assertEqual(package.sensors[0]["name"], "lidar")
            self.assertEqual(package.action_mapping["joints"], ["left", "right"])

    def test_package_preserves_visual_asset_reference(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "visual.glb").write_text("placeholder", encoding="utf-8")
            config = base_config()
            config["visual_assets"] = [{"kind": "render_mesh", "path": "visual.glb"}]
            write_package(root, config)

            package = load_robot_package(root)

        self.assertEqual(package.visual_assets, [{"kind": "render_mesh", "path": "visual.glb"}])

    def test_missing_package_config_fails(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(PackageLoadError, "Missing robot package config"):
                load_robot_package(Path(tmp))

    def test_duplicate_sensor_names_fail(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = base_config()
            config["sensors"].append({"name": "lidar", "kind": "lidar"})
            write_package(root, config)

            with self.assertRaisesRegex(PackageLoadError, "Duplicate sensor stream name"):
                load_robot_package(root)

    def test_visual_assets_are_optional(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_package(root, base_config())

            package = load_robot_package(root)

        self.assertEqual(package.visual_assets, [])

    def test_rejects_model_path_outside_package(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root.parent / "outside.xml"
            outside.write_text("<mujoco/>", encoding="utf-8")
            config = base_config()
            config["model"]["path"] = "../outside.xml"
            (root / "robot_package.json").write_text(json.dumps(config), encoding="utf-8")

            with self.assertRaisesRegex(PackageLoadError, "within the package directory"):
                load_robot_package(root)

    def test_rejects_malformed_element_shapes_with_package_error(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path

        bad_configs = [
            ("sensors", ["not an object"], "sensors"),
            ("visual_assets", ["not an object"], "visual_assets"),
            ("robot_metadata", ["not an object"], "robot_metadata"),
        ]
        for field, value, message in bad_configs:
            with self.subTest(field=field), TemporaryDirectory() as tmp:
                root = Path(tmp)
                config = base_config()
                config[field] = value
                write_package(root, config)

                with self.assertRaisesRegex(PackageLoadError, message):
                    load_robot_package(root)
