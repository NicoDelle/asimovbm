using System;
using System.Collections.Generic;
using UnityEngine;

namespace Asimov.UnityMujoco
{
    public sealed class DynamicObstacleRuntime
    {
        public string Name { get; private set; } = "";
        public Vector2 Center { get; private set; }
        public Vector2 Axis { get; private set; }
        public float Radius { get; private set; }
        public float HalfHeight { get; private set; }
        public float AmplitudeMeters { get; private set; }
        public float PeriodSeconds { get; private set; }
        public float PhaseRadians { get; private set; }
        public string Mode { get; private set; } = "npc";
        public string Policy { get; private set; } = "social_patrol";

        public Vector2 PositionAt(float simTime)
        {
            float phase = (Mathf.PI * 2.0f * simTime / PeriodSeconds) + PhaseRadians;
            float offset = AmplitudeMeters * Mathf.Sin(phase);
            return Center + Axis * offset;
        }

        public float YawAt(float simTime)
        {
            float phase = (Mathf.PI * 2.0f * simTime / PeriodSeconds) + PhaseRadians;
            float direction = Mathf.Cos(phase) >= 0.0f ? 1.0f : -1.0f;
            Vector2 facing = Axis * direction;
            return Mathf.Atan2(facing.y, facing.x);
        }

        public static IReadOnlyList<DynamicObstacleRuntime> Build(DynamicObstaclesConfig config, WorldConfig world)
        {
            string mode = Normalize(config.NormalizedMode);
            if (mode == "none")
            {
                return Array.Empty<DynamicObstacleRuntime>();
            }

            int targetCount = config.Count > 0 ? config.Count : 3;
            uint state = (uint)Mathf.Max(1, config.Seed);
            List<DynamicObstacleRuntime> candidates = DefaultPatrolSpecs(mode, config.npc_policy, ref state);
            List<DynamicObstacleRuntime> selected = new List<DynamicObstacleRuntime>();
            for (int i = 0; i < candidates.Count && selected.Count < targetCount; i += 1)
            {
                selected.Add(WithName(candidates[i], NameForMode(mode, selected.Count)));
            }

            return selected;
        }

        static List<DynamicObstacleRuntime> DefaultPatrolSpecs(string mode, string npcPolicy, ref uint randomState)
        {
            float radius = mode == "npcs" ? 0.28f : 0.22f;
            float halfHeight = mode == "npcs" ? 0.85f : 0.35f;
            string visualMode = mode == "npcs" ? "npc" : "blue_cylinder";
            string policy = mode == "npcs" ? npcPolicy : "sinusoidal_patrol";
            float periodBias = mode == "npcs" ? 1.6f : 1.0f;

            return new List<DynamicObstacleRuntime>
            {
                Create(new Vector2(-3.0f, -1.25f), Vector2.up, radius, halfHeight, 1.05f, 11.0f * periodBias, visualMode, policy, ref randomState),
                Create(new Vector2(0.15f, 1.25f), Vector2.up, radius, halfHeight, 1.0f, 12.5f * periodBias, visualMode, policy, ref randomState),
                Create(new Vector2(3.2f, -1.15f), Vector2.up, radius, halfHeight, 1.05f, 13.5f * periodBias, visualMode, policy, ref randomState),
                Create(new Vector2(-1.9f, 2.35f), Vector2.right, radius, halfHeight, 0.9f, 10.5f * periodBias, visualMode, policy, ref randomState),
                Create(new Vector2(1.9f, -2.3f), Vector2.right, radius, halfHeight, 0.9f, 14.0f * periodBias, visualMode, policy, ref randomState)
            };
        }

        static DynamicObstacleRuntime Create(
            Vector2 center,
            Vector2 axis,
            float radius,
            float halfHeight,
            float amplitudeMeters,
            float periodSeconds,
            string mode,
            string policy,
            ref uint randomState)
        {
            return new DynamicObstacleRuntime
            {
                Center = center,
                Axis = axis.normalized,
                Radius = radius,
                HalfHeight = halfHeight,
                AmplitudeMeters = amplitudeMeters,
                PeriodSeconds = periodSeconds,
                PhaseRadians = NextUnit(ref randomState) * Mathf.PI * 2.0f,
                Mode = mode,
                Policy = policy
            };
        }

        static DynamicObstacleRuntime WithName(DynamicObstacleRuntime obstacle, string name)
        {
            return new DynamicObstacleRuntime
            {
                Name = name,
                Center = obstacle.Center,
                Axis = obstacle.Axis,
                Radius = obstacle.Radius,
                HalfHeight = obstacle.HalfHeight,
                AmplitudeMeters = obstacle.AmplitudeMeters,
                PeriodSeconds = obstacle.PeriodSeconds,
                PhaseRadians = obstacle.PhaseRadians,
                Mode = obstacle.Mode,
                Policy = obstacle.Policy
            };
        }

        static float NextUnit(ref uint state)
        {
            state = 1664525u * state + 1013904223u;
            return (state & 0x00FFFFFF) / (float)0x01000000;
        }

        static string Normalize(string mode)
        {
            string normalized = string.IsNullOrWhiteSpace(mode) ? "none" : mode.Replace("-", "_");
            if (normalized == "npc" || normalized == "people" || normalized == "persons" || normalized == "pedestrians")
            {
                return "npcs";
            }

            if (normalized == "blue" || normalized == "blue_cylinder" || normalized == "cylinders")
            {
                return "blue_cylinders";
            }

            return normalized;
        }

        static string NameForMode(string mode, int index)
        {
            return mode == "npcs" ? $"person_npc_{index}" : $"blue_cylinder_{index}";
        }
    }
}
