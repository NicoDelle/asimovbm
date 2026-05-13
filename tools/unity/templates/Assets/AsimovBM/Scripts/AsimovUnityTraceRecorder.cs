using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using Mujoco;
using UnityEngine;
using Debug = UnityEngine.Debug;

namespace AsimovBM.Mujoco
{
    public unsafe sealed class AsimovUnityTraceRecorder : MonoBehaviour
    {
        public string sceneId = "unity_scene";
        public string episodeId = "unity_scene";
        public string tierId = "unity_validation";
        public string robotSelector = "unity_mujoco";
        public string canonicalBackendId = "unity_mujoco";
        public string expectedMotion = "moving";
        public float goalX = 1.2f;
        public float goalY = 0f;
        public int iteration = 0;
        public int maxSteps = 90;
        public string runId = "";
        public string artifactRootProject = "";
        public bool runPythonPostprocess = true;
        public bool stopWhenFinished = false;

        private readonly List<AsimovUnityTraceStep> steps = new List<AsimovUnityTraceStep>();
        private MjScene scene;
        private AsimovUnityMovementVerifier movementVerifier;
        private string rawTracePath;
        private bool finished;
        private bool warnedNoScene;

        private static bool testOverridesEnabled;
        private static string testRunId;
        private static string testArtifactRootProject;
        private static int testMaxSteps;
        private static bool testRunPythonPostprocess;

        public bool HasWrittenTrace => finished && !string.IsNullOrEmpty(rawTracePath) && File.Exists(rawTracePath);
        public string RawTracePath => rawTracePath;

        public static void ConfigureTestOverrides(
            string overrideRunId,
            string overrideArtifactRootProject,
            int overrideMaxSteps,
            bool overrideRunPythonPostprocess)
        {
            testOverridesEnabled = true;
            testRunId = overrideRunId;
            testArtifactRootProject = overrideArtifactRootProject;
            testMaxSteps = overrideMaxSteps;
            testRunPythonPostprocess = overrideRunPythonPostprocess;
        }

        public static void ClearTestOverrides()
        {
            testOverridesEnabled = false;
            testRunId = "";
            testArtifactRootProject = "";
            testMaxSteps = 0;
            testRunPythonPostprocess = false;
        }

        private void Start()
        {
            var settings = AsimovUnityRuntimeSettings.Load();
            if (testOverridesEnabled)
            {
                runId = testRunId;
                artifactRootProject = testArtifactRootProject;
                maxSteps = testMaxSteps > 0 ? testMaxSteps : maxSteps;
                runPythonPostprocess = testRunPythonPostprocess;
            }

            if (string.IsNullOrEmpty(runId))
            {
                runId = Application.isBatchMode ? "unity-batch" : "press-play";
            }

            if (string.IsNullOrEmpty(artifactRootProject))
            {
                artifactRootProject = settings.artifact_root_project;
            }

            runPythonPostprocess = runPythonPostprocess && settings.run_python_postprocess;
            movementVerifier = GetComponent<AsimovUnityMovementVerifier>();
            if (movementVerifier == null)
            {
                movementVerifier = gameObject.AddComponent<AsimovUnityMovementVerifier>();
            }
            movementVerifier.expectedMotion = expectedMotion;

            scene = UnityEngine.Object.FindObjectOfType<MjScene>();
            if (scene == null)
            {
                warnedNoScene = true;
                Debug.LogWarning("AsimovBM trace recorder did not find an MjScene.");
                return;
            }

            scene.postUpdateEvent += OnPostUpdate;
        }

        private void OnDestroy()
        {
            if (scene != null)
            {
                scene.postUpdateEvent -= OnPostUpdate;
            }

            if (!finished)
            {
                FinishAndWriteTrace("stopped");
            }
        }

        private void OnPostUpdate(object sender, MjStepArgs args)
        {
            if (finished)
            {
                return;
            }

            if (args.model == null || args.data == null)
            {
                if (!warnedNoScene)
                {
                    warnedNoScene = true;
                    Debug.LogWarning("AsimovBM trace recorder received an empty MuJoCo model/data pointer.");
                }
                return;
            }

            steps.Add(BuildStep(args.model, args.data));
            if (steps.Count >= Math.Max(maxSteps, 1))
            {
                FinishAndWriteTrace("success");
            }
        }

        private AsimovUnityTraceStep BuildStep(MujocoLib.mjModel_* model, MujocoLib.mjData_* data)
        {
            var qpos = CopyArray(data->qpos, (int)model->nq);
            var qvel = CopyArray(data->qvel, (int)model->nv);
            var pose = PoseFromQpos(qpos);
            var velocity = VelocityFromQvel(qvel);
            var action = ActionFromCtrl(model, data);
            var dx = goalX - pose[0];
            var dy = goalY - pose[1];
            var status = steps.Count + 1 >= Math.Max(maxSteps, 1) ? "success" : "running";

            var step = new AsimovUnityTraceStep
            {
                step_id = steps.Count,
                time_s = data->time,
                dt_s = Time.fixedDeltaTime,
                robot_pose = pose,
                robot_velocity = velocity,
                action = action,
                distance_to_goal = Math.Sqrt((dx * dx) + (dy * dy)),
                qpos = qpos,
                qvel = qvel,
                status = status,
                metadata = new AsimovUnityTraceStepMetadata
                {
                    contact_count = data->ncon
                }
            };

            if (data->ncon > 0)
            {
                step.collisions = new[]
                {
                    new AsimovUnityTraceCollision
                    {
                        id = "mujoco_contacts",
                        count = data->ncon
                    }
                };
            }

            return step;
        }

        private void FinishAndWriteTrace(string terminalStatus)
        {
            if (finished)
            {
                return;
            }

            finished = true;
            var proof = movementVerifier != null
                ? movementVerifier.Evaluate(steps)
                : new AsimovUnityMovementProof { passed = expectedMotion == "static", reason = "no verifier" };
            var technicalValid = proof.passed && steps.Count > 0;
            var envelope = new AsimovUnityTraceEnvelope
            {
                scene_id = sceneId,
                episode_id = episodeId,
                iteration = iteration,
                tier_id = tierId,
                technical_valid = technicalValid,
                terminal_status = technicalValid ? terminalStatus : "robot_failure",
                config_checksum_sha256 = "unity_scene_manifest",
                config_path = "Assets/AsimovBM/MuJoCo/SceneManifest.json",
                robot_selector = robotSelector,
                canonical_backend_id = canonicalBackendId,
                execution_backend_id = "unity_mujoco_trace_v1",
                viewer_mode = Application.isBatchMode ? "unity_batchmode" : "unity_editor_play",
                movement_proof = proof,
                metadata = new AsimovUnityTraceMetadata
                {
                    start = StartFromSteps(),
                    goal = new[] { (double)goalX, (double)goalY },
                    unity_scene_name = gameObject.scene.name
                },
                steps = steps.ToArray()
            };

            rawTracePath = TracePath();
            Directory.CreateDirectory(Path.GetDirectoryName(rawTracePath));
            File.WriteAllText(rawTracePath, JsonUtility.ToJson(envelope, prettyPrint: true));
            Debug.Log($"AsimovBM Unity trace written: {rawTracePath}");

            if (runPythonPostprocess)
            {
                TryRunPythonPostprocess(rawTracePath);
            }

            if (stopWhenFinished)
            {
                Application.Quit();
            }
        }

        private void TryRunPythonPostprocess(string tracePath)
        {
            var settings = AsimovUnityRuntimeSettings.Load();
            if (string.IsNullOrEmpty(settings.repo_root_wsl))
            {
                Debug.LogWarning("AsimovBM Python postprocess skipped: repo_root_wsl is not configured.");
                return;
            }

            var traceWsl = ToWslPath(tracePath);
            var command =
                $"cd {ShellQuote(settings.repo_root_wsl)} && "
                + $"PYTHONPATH=src:g1_slam/src {settings.python_executable} "
                + "-m asimovbm.local_runner.unity_runner ingest "
                + $"--trace {ShellQuote(traceWsl)} "
                + $"--artifact-root {ShellQuote(settings.artifact_root_wsl)} "
                + $"--run-id {ShellQuote(runId)}";

            try
            {
                var process = new Process
                {
                    StartInfo = new ProcessStartInfo
                    {
                        FileName = "wsl.exe",
                        Arguments = "bash -lc " + ShellQuote(command),
                        UseShellExecute = false,
                        RedirectStandardOutput = true,
                        RedirectStandardError = true,
                        CreateNoWindow = true
                    }
                };
                process.Start();
                var stdout = process.StandardOutput.ReadToEnd();
                var stderr = process.StandardError.ReadToEnd();
                process.WaitForExit(120000);
                if (process.ExitCode == 0)
                {
                    Debug.Log("AsimovBM Python postprocess completed.\n" + stdout);
                }
                else
                {
                    Debug.LogWarning(
                        $"AsimovBM Python postprocess failed with exit code {process.ExitCode}.\n{stdout}\n{stderr}"
                    );
                }
            }
            catch (Exception exc)
            {
                Debug.LogWarning("AsimovBM Python postprocess failed: " + exc.Message);
            }
        }

        private string TracePath()
        {
            var root = string.IsNullOrEmpty(artifactRootProject)
                ? "Artifacts/AsimovBM/Unity"
                : artifactRootProject;
            if (!Path.IsPathRooted(root))
            {
                root = AsimovUnitySceneManifest.ProjectPath(root);
            }

            return Path.Combine(root, runId, sceneId, $"iteration-{iteration:000}", "raw-unity-trace.json");
        }

        private double[] StartFromSteps()
        {
            if (steps.Count == 0 || steps[0].robot_pose == null || steps[0].robot_pose.Length < 2)
            {
                return new[] { 0.0, 0.0 };
            }

            return new[] { steps[0].robot_pose[0], steps[0].robot_pose[1] };
        }

        private static double[] CopyArray(double* source, int length)
        {
            var values = new double[Math.Max(length, 0)];
            for (var i = 0; i < values.Length; i++)
            {
                values[i] = source[i];
            }

            return values;
        }

        private static double[] PoseFromQpos(double[] qpos)
        {
            if (qpos == null || qpos.Length < 3)
            {
                return new[] { 0.0, 0.0, 0.0 };
            }

            var yaw = 0.0;
            if (qpos.Length >= 7)
            {
                var w = qpos[3];
                var x = qpos[4];
                var y = qpos[5];
                var z = qpos[6];
                yaw = Math.Atan2(2.0 * ((w * z) + (x * y)), 1.0 - (2.0 * ((y * y) + (z * z))));
            }

            return new[] { qpos[0], qpos[1], yaw };
        }

        private static double[] VelocityFromQvel(double[] qvel)
        {
            return new[]
            {
                qvel != null && qvel.Length > 0 ? qvel[0] : 0.0,
                qvel != null && qvel.Length > 1 ? qvel[1] : 0.0,
                qvel != null && qvel.Length > 5 ? qvel[5] : 0.0
            };
        }

        private static double[] ActionFromCtrl(MujocoLib.mjModel_* model, MujocoLib.mjData_* data)
        {
            return new[]
            {
                model->nu > 0 ? data->ctrl[0] : 0.0,
                model->nu > 1 ? data->ctrl[1] : 0.0
            };
        }

        private static string ToWslPath(string path)
        {
            var full = Path.GetFullPath(path).Replace('\\', '/');
            if (full.Length >= 3 && full[1] == ':' && full[2] == '/')
            {
                var drive = char.ToLowerInvariant(full[0]);
                return $"/mnt/{drive}/{full.Substring(3)}";
            }

            return full;
        }

        private static string ShellQuote(string value)
        {
            return "'" + value.Replace("'", "'\"'\"'") + "'";
        }
    }

    [Serializable]
    public sealed class AsimovUnityTraceEnvelope
    {
        public string schema_version = "asimovbm.unity_trace.v1";
        public string scene_id;
        public string episode_id;
        public int iteration;
        public string tier_id;
        public bool technical_valid;
        public string terminal_status;
        public string config_checksum_sha256;
        public string config_path;
        public string robot_selector;
        public string canonical_backend_id;
        public string execution_backend_id;
        public string viewer_mode;
        public AsimovUnityMovementProof movement_proof;
        public AsimovUnityTraceMetadata metadata;
        public AsimovUnityTraceStep[] steps;
    }

    [Serializable]
    public sealed class AsimovUnityTraceMetadata
    {
        public double[] start;
        public double[] goal;
        public string unity_scene_name;
    }

    [Serializable]
    public sealed class AsimovUnityTraceStep
    {
        public int step_id;
        public double time_s;
        public double dt_s;
        public double[] robot_pose;
        public double[] robot_velocity;
        public double[] action;
        public double distance_to_goal;
        public double[] lidar_ranges = Array.Empty<double>();
        public AsimovUnityTraceCollision[] collisions = Array.Empty<AsimovUnityTraceCollision>();
        public double[] qpos;
        public double[] qvel;
        public string status;
        public AsimovUnityTraceStepMetadata metadata;
    }

    [Serializable]
    public sealed class AsimovUnityTraceStepMetadata
    {
        public int contact_count;
    }

    [Serializable]
    public sealed class AsimovUnityTraceCollision
    {
        public string id;
        public int count;
    }
}
