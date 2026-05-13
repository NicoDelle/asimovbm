using UnityEngine;

namespace Asimov.UnityMujoco
{
    public readonly struct Pose2D
    {
        public Pose2D(float x, float y, float yaw)
        {
            X = x;
            Y = y;
            Yaw = yaw;
        }

        public float X { get; }
        public float Y { get; }
        public float Yaw { get; }

        public Vector3 ToUnity(float height = 0.0f)
        {
            return new Vector3(X, height, Y);
        }

        public Pose2D Moved(VelocityCommand command, float dt)
        {
            float nextYaw = WrapAngle(Yaw + command.YawRate * dt);
            return new Pose2D(
                X + Mathf.Cos(nextYaw) * command.Linear * dt,
                Y + Mathf.Sin(nextYaw) * command.Linear * dt,
                nextYaw);
        }

        public static Pose2D FromConfig(Pose2DConfig config)
        {
            return new Pose2D(config.x, config.y, config.yaw);
        }

        public static float WrapAngle(float value)
        {
            while (value > Mathf.PI)
            {
                value -= Mathf.PI * 2.0f;
            }

            while (value < -Mathf.PI)
            {
                value += Mathf.PI * 2.0f;
            }

            return value;
        }
    }

    public readonly struct VelocityCommand
    {
        public VelocityCommand(float linear, float yawRate)
        {
            Linear = linear;
            YawRate = yawRate;
        }

        public float Linear { get; }
        public float YawRate { get; }
    }

    public sealed class PurePursuitController
    {
        readonly ControllerConfig config;

        public PurePursuitController(ControllerConfig config)
        {
            this.config = config;
        }

        public VelocityCommand Command(Pose2D pose, Vector2 goal)
        {
            float distanceToGoal = Vector2.Distance(new Vector2(pose.X, pose.Y), goal);
            if (distanceToGoal <= config.goal_tolerance)
            {
                return new VelocityCommand(0.0f, 0.0f);
            }

            float heading = Mathf.Atan2(goal.y - pose.Y, goal.x - pose.X);
            float headingError = Pose2D.WrapAngle(heading - pose.Yaw);
            float yawRate = Mathf.Clamp(2.0f * headingError, -config.max_yaw_rate, config.max_yaw_rate);
            float speedScale = Mathf.Max(0.15f, 1.0f - Mathf.Abs(headingError) / 1.7f);
            return new VelocityCommand(config.max_linear_speed * speedScale, yawRate);
        }
    }
}
