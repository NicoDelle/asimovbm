using System;
using System.Collections.Generic;
using System.Globalization;
using Mujoco;
using UnityEngine;

namespace AsimovBM.Mujoco
{
    public unsafe sealed class AsimovG1MotionPlayer : MonoBehaviour
    {
        public TextAsset motionCsv;
        public float clipFps = 120f;
        public bool playOnStart = true;
        public bool loop = true;
        public bool zeroVelocities = true;
        public bool zeroControls = true;

        private readonly List<double[]> frames = new List<double[]>();
        private MjScene scene;
        private float elapsedSeconds;
        private bool warnedNoScene;
        private bool warnedNoClip;
        private bool warnedMismatch;

        private const int RootPositionColumns = 3;
        private const int RootQuaternionColumns = 4;
        private const int ExpectedG1JointColumns = 29;
        private const int ExpectedG1Qpos = RootPositionColumns + RootQuaternionColumns + ExpectedG1JointColumns;

        private void Start()
        {
            LoadClip();
            scene = UnityEngine.Object.FindObjectOfType<MjScene>();
            if (scene == null)
            {
                warnedNoScene = true;
                Debug.LogWarning("AsimovBM G1 motion player did not find an MjScene in this Unity scene.");
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
        }

        private void OnPostUpdate(object sender, MjStepArgs args)
        {
            if (!playOnStart || frames.Count == 0 || args.model == null || args.data == null)
            {
                WarnIfNotReady();
                return;
            }

            var modelQpos = (int)args.model->nq;
            if (modelQpos < ExpectedG1Qpos)
            {
                WarnQposMismatch(modelQpos);
                return;
            }

            var frameIndex = FrameIndexForTime();
            ApplyFrame(args.model, args.data, frames[frameIndex]);
            MujocoLib.mj_forward(args.model, args.data);

            if (sender is MjScene activeScene)
            {
                activeScene.SyncUnityToMjState();
            }
        }

        private int FrameIndexForTime()
        {
            elapsedSeconds += Time.fixedDeltaTime;
            var index = Mathf.FloorToInt(elapsedSeconds * Mathf.Max(clipFps, 1f));
            if (loop)
            {
                return index % frames.Count;
            }

            return Mathf.Clamp(index, 0, frames.Count - 1);
        }

        private void ApplyFrame(MujocoLib.mjModel_* model, MujocoLib.mjData_* data, double[] frame)
        {
            data->qpos[0] = frame[0];
            data->qpos[1] = frame[1];
            data->qpos[2] = frame[2];

            data->qpos[3] = frame[6];
            data->qpos[4] = frame[3];
            data->qpos[5] = frame[4];
            data->qpos[6] = frame[5];

            for (var i = 0; i < ExpectedG1JointColumns; i++)
            {
                data->qpos[7 + i] = frame[7 + i];
            }

            if (zeroVelocities)
            {
                for (var i = 0; i < (int)model->nv; i++)
                {
                    data->qvel[i] = 0.0;
                }
            }

            if (zeroControls)
            {
                for (var i = 0; i < (int)model->nu; i++)
                {
                    data->ctrl[i] = 0.0;
                }
            }
        }

        private void LoadClip()
        {
            frames.Clear();
            if (motionCsv == null)
            {
                return;
            }

            var lines = motionCsv.text.Split(new[] { '\r', '\n' }, StringSplitOptions.RemoveEmptyEntries);
            foreach (var line in lines)
            {
                if (line.StartsWith("#", StringComparison.Ordinal))
                {
                    continue;
                }

                var columns = line.Split(',');
                if (columns.Length < ExpectedG1Qpos)
                {
                    Debug.LogWarning(
                        $"Skipping short G1 motion row in {motionCsv.name}: expected {ExpectedG1Qpos}, got {columns.Length}."
                    );
                    continue;
                }

                var frame = new double[ExpectedG1Qpos];
                for (var i = 0; i < frame.Length; i++)
                {
                    frame[i] = double.Parse(columns[i], CultureInfo.InvariantCulture);
                }

                frames.Add(frame);
            }

            if (frames.Count > 0)
            {
                Debug.Log($"Loaded AsimovBM G1 motion clip {motionCsv.name}: {frames.Count} frames at {clipFps} fps.");
            }
        }

        private void WarnIfNotReady()
        {
            if (!warnedNoClip && motionCsv == null)
            {
                warnedNoClip = true;
                Debug.LogWarning("AsimovBM G1 motion player has no motion CSV assigned.");
            }

            if (!warnedNoScene && scene == null)
            {
                warnedNoScene = true;
                Debug.LogWarning("AsimovBM G1 motion player has no MjScene to drive.");
            }
        }

        private void WarnQposMismatch(int modelQpos)
        {
            if (warnedMismatch)
            {
                return;
            }

            warnedMismatch = true;
            Debug.LogWarning(
                "AsimovBM G1 motion clip needs the real G1 model with 36 qpos values "
                    + $"(free root + 29 joints). The current MuJoCo scene has {modelQpos}. "
                    + "Import Assets/AsimovBM/MuJoCo/Models/g1/g1.xml or regenerate Unity scenes."
            );
        }
    }
}
