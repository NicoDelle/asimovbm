#if UNITY_EDITOR

using System.IO;
using AsimovBM.Editor;
using AsimovBM.Mujoco;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace AsimovBM.Tests
{
    public sealed class AsimovGeneratedSceneEditModeTests
    {
        [Test]
        public void GeneratedScenesLoadWithRequiredRuntimeComponents()
        {
            var generated = AsimovMujocoSceneGenerator.GenerateAllScenes();
            Assert.That(generated.Count, Is.GreaterThanOrEqualTo(1));

            foreach (var scenePath in generated)
            {
                Assert.That(File.Exists(AsimovUnitySceneManifest.ProjectPath(scenePath)), Is.True, scenePath);
                var scene = EditorSceneManager.OpenScene(scenePath);
                Assert.That(scene.IsValid(), Is.True, scenePath);
                Assert.That(Object.FindObjectOfType<AsimovUnityTraceRecorder>(), Is.Not.Null, scenePath);
                Assert.That(Object.FindObjectOfType<AsimovUnityMovementVerifier>(), Is.Not.Null, scenePath);
                AssertNoMissingScripts(scenePath);
                AssertMaterialsAreRenderable();
            }
        }

        private static void AssertNoMissingScripts(string scenePath)
        {
            foreach (var gameObject in Object.FindObjectsByType<GameObject>(FindObjectsSortMode.None))
            {
                foreach (var component in gameObject.GetComponents<Component>())
                {
                    Assert.That(component, Is.Not.Null, $"{scenePath} has a missing script on {gameObject.name}");
                }
            }
        }

        private static void AssertMaterialsAreRenderable()
        {
            foreach (var renderer in Object.FindObjectsByType<Renderer>(FindObjectsSortMode.None))
            {
                foreach (var material in renderer.sharedMaterials)
                {
                    if (material == null)
                    {
                        continue;
                    }

                    Assert.That(material.shader, Is.Not.Null, material.name);
                    Assert.That(material.shader.name, Is.Not.EqualTo("Hidden/InternalErrorShader"), material.name);
                }
            }
        }
    }
}

#endif
