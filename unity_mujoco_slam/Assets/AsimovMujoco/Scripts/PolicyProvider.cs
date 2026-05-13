using System;
using UnityEngine;

namespace Asimov.UnityMujoco
{
    public abstract class PolicyProvider : MonoBehaviour
    {
        public abstract void Configure(EpisodeConfig episode, RobotPolicyEntry robotPolicy, string repoRoot);

        public virtual void ApplyCommand(VelocityCommand command, float fixedDeltaTime)
        {
        }
    }

    public sealed class MetadataPolicyProvider : PolicyProvider
    {
        EpisodeConfig episode = new EpisodeConfig();
        RobotPolicyEntry robotPolicy = new RobotPolicyEntry();
        string repoRoot = "";
        bool logged;

        public override void Configure(EpisodeConfig episode, RobotPolicyEntry robotPolicy, string repoRoot)
        {
            this.episode = episode;
            this.robotPolicy = robotPolicy;
            this.repoRoot = repoRoot;
            logged = false;
        }

        public override void ApplyCommand(VelocityCommand command, float fixedDeltaTime)
        {
            if (logged)
            {
                return;
            }

            logged = true;
            Debug.Log(
                $"Episode '{episode.episode.id}' uses policy provider '{robotPolicy.policy_provider}' " +
                $"with locomotion '{robotPolicy.locomotion_mode}' at repo root '{repoRoot}'.");
        }
    }

    public static class PolicyProviderFactory
    {
        public static PolicyProvider Attach(GameObject target, EpisodeConfig episode, RobotPolicyEntry entry, string repoRoot)
        {
            PolicyProvider provider = target.GetComponent<PolicyProvider>();
            if (provider == null)
            {
                provider = target.AddComponent<MetadataPolicyProvider>();
            }

            provider.Configure(episode, entry, repoRoot);
            return provider;
        }

        public static void ValidatePolicyCompatibility(EpisodeConfig episode, RobotPolicyEntry entry)
        {
            if (!string.Equals(episode.locomotion.mode, entry.locomotion_mode, StringComparison.Ordinal))
            {
                Debug.LogWarning(
                    $"Episode '{episode.episode.id}' declares locomotion '{episode.locomotion.mode}', " +
                    $"but robot catalog declares '{entry.locomotion_mode}'.");
            }

            if (entry.robot_id == "go2" && episode.locomotion.observation_profile != "dias_ai_master_go2_velocity_flat")
            {
                Debug.LogWarning($"Go2 episode '{episode.episode.id}' is not using the current Go2 observation profile.");
            }

            if (entry.robot_id == "g1" && episode.locomotion.mode != "robojudo")
            {
                Debug.LogWarning($"G1 episode '{episode.episode.id}' should stay on the RoboJuDo policy adapter.");
            }
        }
    }
}
