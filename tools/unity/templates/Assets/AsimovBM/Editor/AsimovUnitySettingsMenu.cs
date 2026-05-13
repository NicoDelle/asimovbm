using System.IO;
using AsimovBM.Mujoco;
using UnityEditor;
using UnityEngine;

namespace AsimovBM.Editor
{
    public static class AsimovUnitySettingsMenu
    {
        [MenuItem("AsimovBM/MuJoCo/Print Runtime Settings")]
        public static void PrintRuntimeSettings()
        {
            var path = AsimovUnitySceneManifest.ProjectPath(
                "Assets/AsimovBM/RuntimeSettings/asimovbm_unity_settings.json"
            );
            Debug.Log(File.Exists(path) ? File.ReadAllText(path) : "AsimovBM runtime settings file is missing.");
        }
    }
}
