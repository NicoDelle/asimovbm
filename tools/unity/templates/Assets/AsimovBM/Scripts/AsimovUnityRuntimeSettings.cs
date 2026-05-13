using System;
using System.IO;
using UnityEngine;

namespace AsimovBM.Mujoco
{
    [Serializable]
    public sealed class AsimovUnityRuntimeSettings
    {
        public string schema_version = "asimovbm.unity_runtime_settings.v1";
        public string repo_root_wsl = "";
        public string python_executable = "python3";
        public string artifact_root_wsl = "artifacts/unity-validation";
        public string artifact_root_project = "Artifacts/AsimovBM/Unity";
        public bool run_python_postprocess = true;

        public static AsimovUnityRuntimeSettings Load()
        {
            var path = AsimovUnitySceneManifest.ProjectPath(
                "Assets/AsimovBM/RuntimeSettings/asimovbm_unity_settings.json"
            );
            if (!File.Exists(path))
            {
                return new AsimovUnityRuntimeSettings();
            }

            var settings = JsonUtility.FromJson<AsimovUnityRuntimeSettings>(File.ReadAllText(path));
            return settings ?? new AsimovUnityRuntimeSettings();
        }
    }
}
