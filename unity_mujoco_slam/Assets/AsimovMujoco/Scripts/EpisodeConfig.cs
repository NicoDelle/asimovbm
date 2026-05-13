using System;

namespace Asimov.UnityMujoco
{
    [Serializable]
    public sealed class EpisodeConfig
    {
        public EpisodeMetadata episode = new EpisodeMetadata();
        public Pose2DConfig start = new Pose2DConfig();
        public GoalConfig goal = new GoalConfig();
        public int steps;
        public WorldConfig world = new WorldConfig();
        public DynamicObstaclesConfig dynamic_obstacles = new DynamicObstaclesConfig();
        public ControllerConfig controller = new ControllerConfig();
        public LocomotionConfig locomotion = new LocomotionConfig();
        public VisualizationConfig visualization = new VisualizationConfig();

        public string RobotId
        {
            get
            {
                if (episode != null && !string.IsNullOrEmpty(episode.id) && episode.id.StartsWith("go2_"))
                {
                    return "go2";
                }

                return "g1";
            }
        }
    }

    [Serializable]
    public sealed class EpisodeMetadata
    {
        public string id = "";
        public string title = "";
        public string description = "";
    }

    [Serializable]
    public sealed class Pose2DConfig
    {
        public float x;
        public float y;
        public float yaw;
    }

    [Serializable]
    public sealed class GoalConfig
    {
        public float x;
        public float y;
    }

    [Serializable]
    public sealed class WorldConfig
    {
        public float x_min;
        public float y_min;
        public float x_max;
        public float y_max;
        public RectObstacleConfig[] obstacles = Array.Empty<RectObstacleConfig>();
    }

    [Serializable]
    public sealed class RectObstacleConfig
    {
        public float x_min;
        public float y_min;
        public float x_max;
        public float y_max;
    }

    [Serializable]
    public sealed class DynamicObstaclesConfig
    {
        public string mode = "";
        public bool blue_cylinders;
        public int blue_cylinder_seed;
        public int seed;
        public int count;
        public string npc_policy = "social_patrol";

        public string NormalizedMode
        {
            get
            {
                if (!string.IsNullOrWhiteSpace(mode))
                {
                    return mode.Replace("-", "_");
                }

                return blue_cylinders ? "blue_cylinders" : "none";
            }
        }

        public int Seed => seed != 0 ? seed : blue_cylinder_seed;
        public int Count => count > 0 ? count : 0;
    }

    [Serializable]
    public sealed class ControllerConfig
    {
        public float lookahead = 0.55f;
        public float waypoint_tolerance = 0.25f;
        public float goal_tolerance = 0.28f;
        public float max_linear_speed = 0.65f;
        public float max_yaw_rate = 1.4f;
        public float start_delay_s;
    }

    [Serializable]
    public sealed class LocomotionConfig
    {
        public string mode = "";
        public string policy_path = "";
        public string robojudo_config = "g1_asap_loco";
        public int observation_size;
        public string observation_profile = "generic";
        public float action_scale = 0.25f;
        public float kp = 35.0f;
        public float kd = 1.0f;
    }

    [Serializable]
    public sealed class VisualizationConfig
    {
        public CameraConfig camera = new CameraConfig();
        public bool show_trajectory;
        public int trajectory_interval_steps = 20;
    }

    [Serializable]
    public sealed class CameraConfig
    {
        public bool @fixed;
        public CameraLookatConfig lookat = new CameraLookatConfig();
        public float distance;
        public float azimuth;
        public float elevation;
    }

    [Serializable]
    public sealed class CameraLookatConfig
    {
        public float x;
        public float y;
        public float z = 1.0f;
    }
}
