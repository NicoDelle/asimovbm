using System;
using System.Linq;
using UnityEngine;

namespace Asimov.UnityMujoco
{
    [Serializable]
    public sealed class RobotPolicyCatalog
    {
        public RobotPolicyEntry[] robots = Array.Empty<RobotPolicyEntry>();

        public RobotPolicyEntry Require(string robotId)
        {
            RobotPolicyEntry entry = robots.FirstOrDefault(robot => robot.robot_id == robotId);
            if (entry == null)
            {
                throw new InvalidOperationException($"No robot policy entry found for '{robotId}'.");
            }

            return entry;
        }

        public static RobotPolicyCatalog Load()
        {
            TextAsset asset = Resources.Load<TextAsset>("RobotPolicies/robot_policy_catalog");
            if (asset == null)
            {
                throw new InvalidOperationException("Missing Resources/RobotPolicies/robot_policy_catalog.json.");
            }

            return JsonUtility.FromJson<RobotPolicyCatalog>(asset.text);
        }
    }

    [Serializable]
    public sealed class RobotPolicyEntry
    {
        public string robot_id = "";
        public string mujoco_robot = "";
        public string model_path = "";
        public string locomotion_mode = "";
        public string policy_provider = "";
        public string policy_path = "";
        public string robojudo_repo = "";
        public string robojudo_config = "";
        public string observation_profile = "generic";
        public int observation_size;
        public float action_scale;
        public float kp;
        public float kd;
    }
}
