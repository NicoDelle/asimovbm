using System;
using System.IO;
using UnityEngine;

namespace AsimovBM.Mujoco
{
    [Serializable]
    public sealed class AsimovUnitySceneManifest
    {
        public string schema_version = "asimovbm.unity_scene_manifest.v1";
        public string default_scene_id = "g1_real_motion";
        public AsimovUnitySceneEntry[] scenes = Array.Empty<AsimovUnitySceneEntry>();

        public static string ProjectPath(string assetPath)
        {
            var projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            return Path.GetFullPath(Path.Combine(projectRoot, assetPath.Replace('/', Path.DirectorySeparatorChar)));
        }

        public static AsimovUnitySceneManifest Load()
        {
            var path = ProjectPath("Assets/AsimovBM/MuJoCo/SceneManifest.json");
            if (!File.Exists(path))
            {
                throw new FileNotFoundException("AsimovBM Unity scene manifest was not found.", path);
            }

            var manifest = JsonUtility.FromJson<AsimovUnitySceneManifest>(File.ReadAllText(path));
            if (manifest == null || manifest.scenes == null)
            {
                throw new InvalidDataException("AsimovBM Unity scene manifest is malformed.");
            }

            return manifest;
        }

        public AsimovUnitySceneEntry DefaultScene()
        {
            foreach (var scene in scenes)
            {
                if (scene.scene_id == default_scene_id)
                {
                    return scene;
                }
            }

            return scenes.Length > 0 ? scenes[0] : null;
        }
    }

    [Serializable]
    public sealed class AsimovUnitySceneEntry
    {
        public string scene_id;
        public string episode_id;
        public string display_name;
        public string source_mjcf;
        public string generated_scene;
        public string motion_csv;
        public string expected_motion = "moving";
        public string tier_id = "unity_validation";
        public string robot_selector = "unity_mujoco";
        public string canonical_backend_id = "unity_mujoco";
        public float goal_x = 1.2f;
        public float goal_y = 0f;
        public int max_steps = 90;
        public bool unavailable_if_missing;

        public bool HasMotionClip => !string.IsNullOrEmpty(motion_csv);
    }
}
