#if UNITY_EDITOR

using System.Collections;
using System.IO;
using AsimovBM.Mujoco;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.TestTools;

namespace AsimovBM.Tests
{
    public sealed class AsimovGeneratedScenePlayModeTests
    {
        [UnityTest]
        public IEnumerator GeneratedScenesWriteTraceArtifacts()
        {
            var manifest = AsimovUnitySceneManifest.Load();
            var tested = 0;
            foreach (var entry in manifest.scenes)
            {
                if (!File.Exists(AsimovUnitySceneManifest.ProjectPath(entry.generated_scene)))
                {
                    continue;
                }

                AsimovUnityTraceRecorder.ConfigureTestOverrides(
                    "unity-playmode-test",
                    Path.Combine("Temp", "AsimovBMUnityTests"),
                    Mathf.Min(Mathf.Max(entry.max_steps, 2), 12),
                    false
                );
                SceneManager.LoadScene(Path.GetFileNameWithoutExtension(entry.generated_scene));
                yield return null;
                yield return null;

                var recorder = Object.FindObjectOfType<AsimovUnityTraceRecorder>();
                Assert.That(recorder, Is.Not.Null, entry.scene_id);

                for (var frame = 0; frame < 80 && !recorder.HasWrittenTrace; frame++)
                {
                    yield return new WaitForFixedUpdate();
                }

                Assert.That(recorder.HasWrittenTrace, Is.True, entry.scene_id);
                Assert.That(File.Exists(recorder.RawTracePath), Is.True, recorder.RawTracePath);
                tested++;
            }

            AsimovUnityTraceRecorder.ClearTestOverrides();
            Assert.That(tested, Is.GreaterThanOrEqualTo(1));
        }
    }

}

#endif
