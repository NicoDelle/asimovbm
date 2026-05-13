using System;
using System.Collections.Generic;
using UnityEngine;

namespace AsimovBM.Mujoco
{
    public sealed class AsimovUnityMovementVerifier : MonoBehaviour
    {
        public string expectedMotion = "moving";
        public double minPoseDelta = 0.005;
        public double minQposDelta = 0.005;

        public AsimovUnityMovementProof Evaluate(IReadOnlyList<AsimovUnityTraceStep> steps)
        {
            var proof = new AsimovUnityMovementProof
            {
                expected_motion = expectedMotion,
                evaluated_step_count = steps == null ? 0 : steps.Count
            };

            if (steps == null || steps.Count < 2)
            {
                proof.passed = expectedMotion == "static";
                proof.reason = proof.passed ? "static scene has fewer than two samples" : "not enough samples";
                return proof;
            }

            var first = steps[0];
            foreach (var step in steps)
            {
                proof.max_pose_delta = Math.Max(proof.max_pose_delta, PoseDelta(first.robot_pose, step.robot_pose));
                proof.max_qpos_delta = Math.Max(proof.max_qpos_delta, ArrayDelta(first.qpos, step.qpos));
            }

            var moved = proof.max_pose_delta >= minPoseDelta || proof.max_qpos_delta >= minQposDelta;
            proof.passed = expectedMotion == "static" ? !moved : moved;
            proof.reason = proof.passed
                ? "movement expectation satisfied"
                : $"expected {expectedMotion}, pose_delta={proof.max_pose_delta:F6}, qpos_delta={proof.max_qpos_delta:F6}";
            return proof;
        }

        private static double PoseDelta(double[] first, double[] current)
        {
            if (first == null || current == null || first.Length < 3 || current.Length < 3)
            {
                return 0.0;
            }

            var dx = current[0] - first[0];
            var dy = current[1] - first[1];
            var dyaw = current[2] - first[2];
            return Math.Sqrt((dx * dx) + (dy * dy) + (dyaw * dyaw));
        }

        private static double ArrayDelta(double[] first, double[] current)
        {
            if (first == null || current == null)
            {
                return 0.0;
            }

            var length = Math.Min(first.Length, current.Length);
            var max = 0.0;
            for (var i = 0; i < length; i++)
            {
                max = Math.Max(max, Math.Abs(current[i] - first[i]));
            }

            return max;
        }
    }

    [Serializable]
    public sealed class AsimovUnityMovementProof
    {
        public bool passed;
        public string expected_motion;
        public int evaluated_step_count;
        public double max_pose_delta;
        public double max_qpos_delta;
        public string reason;
    }
}
