using System;
using System.Collections.Generic;
using System.IO;
using AsimovBM.Mujoco;
using Mujoco;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace AsimovBM.Editor
{
    public static class AsimovMujocoSceneGenerator
    {
        [MenuItem("AsimovBM/MuJoCo/Generate Validation Scenes")]
        public static void GenerateAllFromMenu()
        {
            GenerateAllScenes();
        }

        public static IReadOnlyList<string> GenerateAllScenes()
        {
            var manifest = AsimovUnitySceneManifest.Load();
            var generated = new List<string>();
            CleanImporterScratchAssets();
            foreach (var entry in manifest.scenes)
            {
                if (TryGenerateScene(entry, out var scenePath))
                {
                    generated.Add(scenePath);
                }
            }

            UpdateEditorBuildSettings(generated);
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Debug.Log($"AsimovBM generated {generated.Count} Unity validation scene(s).");
            return generated;
        }

        private static void CleanImporterScratchAssets()
        {
            const string importPath = "Assets/Local/MjImports";
            if (AssetDatabase.IsValidFolder(importPath))
            {
                AssetDatabase.DeleteAsset(importPath);
                AssetDatabase.Refresh();
                return;
            }

            var absolutePath = AsimovUnitySceneManifest.ProjectPath(importPath);
            if (Directory.Exists(absolutePath))
            {
                Directory.Delete(absolutePath, recursive: true);
                AssetDatabase.Refresh();
            }
        }

        public static bool TryGenerateScene(AsimovUnitySceneEntry entry, out string scenePath)
        {
            scenePath = entry.generated_scene;
            var sourcePath = AsimovUnitySceneManifest.ProjectPath(entry.source_mjcf);
            if (!File.Exists(sourcePath))
            {
                var message = $"AsimovBM scene source is missing for {entry.scene_id}: {entry.source_mjcf}";
                if (entry.unavailable_if_missing)
                {
                    Debug.LogWarning(message);
                    return false;
                }

                throw new FileNotFoundException(message, sourcePath);
            }

            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var importer = new MjImporterWithAssets();
            var importedRoot = importer.ImportFile(sourcePath);
            if (importedRoot == null)
            {
                throw new InvalidOperationException($"MuJoCo importer returned no scene root for {entry.source_mjcf}");
            }
            importedRoot.name = entry.scene_id + " MuJoCo";

            ConfigureRuntime(entry);
            AsimovMujocoVisualRepair.RepairImportedMaterials();
            AsimovMujocoVisualRepair.ConfigureOpenScene();

            var targetPath = AsimovUnitySceneManifest.ProjectPath(entry.generated_scene);
            Directory.CreateDirectory(Path.GetDirectoryName(targetPath));
            EditorSceneManager.SaveScene(SceneManager.GetActiveScene(), entry.generated_scene);
            return true;
        }

        private static void ConfigureRuntime(AsimovUnitySceneEntry entry)
        {
            var runtimeObject = GameObject.Find("AsimovBM Runtime");
            if (runtimeObject == null)
            {
                runtimeObject = new GameObject("AsimovBM Runtime");
            }

            var verifier = runtimeObject.GetComponent<AsimovUnityMovementVerifier>();
            if (verifier == null)
            {
                verifier = runtimeObject.AddComponent<AsimovUnityMovementVerifier>();
            }
            verifier.expectedMotion = entry.expected_motion;

            var recorder = runtimeObject.GetComponent<AsimovUnityTraceRecorder>();
            if (recorder == null)
            {
                recorder = runtimeObject.AddComponent<AsimovUnityTraceRecorder>();
            }
            recorder.sceneId = entry.scene_id;
            recorder.episodeId = entry.episode_id;
            recorder.tierId = entry.tier_id;
            recorder.robotSelector = entry.robot_selector;
            recorder.canonicalBackendId = entry.canonical_backend_id;
            recorder.expectedMotion = entry.expected_motion;
            recorder.goalX = entry.goal_x;
            recorder.goalY = entry.goal_y;
            recorder.maxSteps = Mathf.Max(entry.max_steps, 1);

            var player = runtimeObject.GetComponent<AsimovG1MotionPlayer>();
            if (entry.HasMotionClip)
            {
                if (player == null)
                {
                    player = runtimeObject.AddComponent<AsimovG1MotionPlayer>();
                }
                player.motionCsv = AssetDatabase.LoadAssetAtPath<TextAsset>(entry.motion_csv);
                player.clipFps = 120f;
                player.loop = true;
            }
            else if (player != null)
            {
                UnityEngine.Object.DestroyImmediate(player);
            }

            EditorUtility.SetDirty(runtimeObject);
        }

        private static void UpdateEditorBuildSettings(IReadOnlyList<string> generatedScenes)
        {
            var scenes = new List<EditorBuildSettingsScene>();
            foreach (var existing in EditorBuildSettings.scenes)
            {
                if (!existing.path.StartsWith("Assets/AsimovBM/GeneratedScenes/", StringComparison.Ordinal))
                {
                    scenes.Add(existing);
                }
            }

            foreach (var path in generatedScenes)
            {
                scenes.Add(new EditorBuildSettingsScene(path, true));
            }

            EditorBuildSettings.scenes = scenes.ToArray();
        }
    }
}
