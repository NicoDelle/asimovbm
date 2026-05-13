using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

namespace AsimovBM.Editor
{
    public static class AsimovMujocoVisualRepair
    {
        private const string ImportRoot = "Assets/Local/MjImports";

        [MenuItem("AsimovBM/MuJoCo/Repair Materials And Lighting")]
        public static void RepairOpenScene()
        {
            var changedMaterials = RepairImportedMaterials();
            ConfigureOpenScene();
            UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(
                UnityEditor.SceneManagement.EditorSceneManager.GetActiveScene()
            );
            Debug.Log($"AsimovBM visual repair complete. Materials updated: {changedMaterials}.");
        }

        public static int RepairImportedMaterials()
        {
            var shader = Shader.Find("Universal Render Pipeline/Lit");
            if (shader == null)
            {
                shader = Shader.Find("Standard");
            }

            if (shader == null)
            {
                Debug.LogWarning("AsimovBM visual repair could not find a supported lit shader.");
                return 0;
            }

            var changed = 0;
            var materialGuids = AssetDatabase.FindAssets("t:Material", new[] { ImportRoot });
            foreach (var guid in materialGuids)
            {
                var path = AssetDatabase.GUIDToAssetPath(guid);
                var material = AssetDatabase.LoadAssetAtPath<Material>(path);
                if (material == null)
                {
                    continue;
                }

                material.shader = shader;
                SetMaterialColor(material, ColorForMaterial(material.name));
                SetMaterialFloat(material, "_Metallic", material.name.ToLowerInvariant().Contains("floor") ? 0.05f : 0f);
                SetMaterialFloat(material, "_Smoothness", 0.42f);
                material.enableInstancing = true;
                EditorUtility.SetDirty(material);
                changed++;
            }

            AssetDatabase.SaveAssets();
            return changed;
        }

        public static void ConfigureOpenScene()
        {
            EnsureDirectionalLight(
                "AsimovBM Key Light",
                new Vector3(50f, -35f, 20f),
                new Color(1.0f, 0.94f, 0.86f),
                3.2f
            );
            EnsureDirectionalLight(
                "AsimovBM Fill Light",
                new Vector3(-30f, 45f, 0f),
                new Color(0.55f, 0.68f, 1.0f),
                0.75f
            );
            EnsureCamera();

            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(0.42f, 0.46f, 0.52f);
            RenderSettings.ambientEquatorColor = new Color(0.28f, 0.30f, 0.34f);
            RenderSettings.ambientGroundColor = new Color(0.16f, 0.15f, 0.14f);
            RenderSettings.ambientIntensity = 0.85f;
        }

        private static void EnsureDirectionalLight(string name, Vector3 rotation, Color color, float intensity)
        {
            var lightObject = GameObject.Find(name);
            if (lightObject == null)
            {
                lightObject = new GameObject(name);
            }

            lightObject.transform.rotation = Quaternion.Euler(rotation);
            var light = lightObject.GetComponent<Light>();
            if (light == null)
            {
                light = lightObject.AddComponent<Light>();
            }

            light.type = LightType.Directional;
            light.color = color;
            light.intensity = intensity;
            light.shadows = LightShadows.Soft;
            light.shadowStrength = 0.75f;
            EditorUtility.SetDirty(lightObject);
            EditorUtility.SetDirty(light);
        }

        private static void EnsureCamera()
        {
            var cameraObject = GameObject.Find("AsimovBM Review Camera");
            if (cameraObject == null)
            {
                cameraObject = new GameObject("AsimovBM Review Camera");
            }

            cameraObject.transform.position = new Vector3(-5.8f, -8.2f, 4.8f);
            cameraObject.transform.rotation = Quaternion.Euler(56f, -35f, 0f);

            var camera = cameraObject.GetComponent<Camera>();
            if (camera == null)
            {
                camera = cameraObject.AddComponent<Camera>();
            }

            camera.fieldOfView = 45f;
            camera.nearClipPlane = 0.05f;
            camera.farClipPlane = 80f;
            camera.clearFlags = CameraClearFlags.Skybox;
            camera.depth = 10f;
            cameraObject.tag = "MainCamera";
            EditorUtility.SetDirty(cameraObject);
            EditorUtility.SetDirty(camera);
        }

        private static void SetMaterialColor(Material material, Color color)
        {
            if (material.HasProperty("_BaseColor"))
            {
                material.SetColor("_BaseColor", color);
            }
            if (material.HasProperty("_Color"))
            {
                material.SetColor("_Color", color);
            }
        }

        private static void SetMaterialFloat(Material material, string property, float value)
        {
            if (material.HasProperty(property))
            {
                material.SetFloat(property, value);
            }
        }

        private static Color ColorForMaterial(string materialName)
        {
            var key = materialName.ToLowerInvariant();
            var palette = new Dictionary<string, Color>
            {
                { "floor", new Color(0.32f, 0.34f, 0.36f, 1f) },
                { "robot", new Color(0.78f, 0.82f, 0.86f, 1f) },
                { "joint", new Color(0.07f, 0.09f, 0.12f, 1f) },
                { "obstacle", new Color(0.78f, 0.18f, 0.12f, 1f) },
                { "goal", new Color(0.08f, 0.80f, 0.34f, 1f) },
                { "lidar", new Color(0.02f, 0.02f, 0.025f, 1f) },
                { "g1", new Color(0.74f, 0.78f, 0.82f, 1f) }
            };

            foreach (var entry in palette)
            {
                if (key.Contains(entry.Key))
                {
                    return entry.Value;
                }
            }

            return new Color(0.70f, 0.72f, 0.76f, 1f);
        }
    }
}
