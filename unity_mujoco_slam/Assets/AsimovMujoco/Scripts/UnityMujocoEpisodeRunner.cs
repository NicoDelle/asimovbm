using System.Collections.Generic;
using UnityEngine;

namespace Asimov.UnityMujoco
{
    public sealed class UnityMujocoEpisodeRunner : MonoBehaviour
    {
        [Header("Episode")]
        public string episodeId = "g1_lateral_open";
        public string repoRoot = "..";

        [Header("Runtime")]
        public Transform importedSceneRoot;
        public bool bindImportedScene = true;
        public Transform robotRoot;
        public bool buildUnityVisualProxy = true;
        public bool driveKinematicProxy;
        public float robotProxyHeight = 0.8f;

        EpisodeConfig episode = new EpisodeConfig();
        RobotPolicyEntry robotPolicy = new RobotPolicyEntry();
        PolicyProvider policyProvider;
        PurePursuitController controller;
        Pose2D pose;
        readonly List<GameObject> spawned = new List<GameObject>();
        readonly Dictionary<DynamicObstacleRuntime, Transform> dynamicProxies = new Dictionary<DynamicObstacleRuntime, Transform>();
        float simTime;

        void Start()
        {
            LoadEpisode();
            if (buildUnityVisualProxy)
            {
                BuildVisualProxy();
            }

            ConfigureCamera();
        }

        void FixedUpdate()
        {
            if (controller == null)
            {
                return;
            }

            simTime += Time.fixedDeltaTime;
            UpdateDynamicObstacles();

            Vector2 goal = new Vector2(episode.goal.x, episode.goal.y);
            VelocityCommand command = controller.Command(pose, goal);
            policyProvider?.ApplyCommand(command, Time.fixedDeltaTime);

            if (driveKinematicProxy && robotRoot != null)
            {
                pose = pose.Moved(command, Time.fixedDeltaTime);
                robotRoot.position = pose.ToUnity(robotProxyHeight);
                robotRoot.rotation = Quaternion.Euler(0.0f, -pose.Yaw * Mathf.Rad2Deg, 0.0f);
            }
        }

        [ContextMenu("Reload Episode")]
        public void LoadEpisode()
        {
            TextAsset asset = Resources.Load<TextAsset>($"Episodes/{episodeId}");
            if (asset == null)
            {
                throw new UnityException($"Missing episode Resources/Episodes/{episodeId}.json.");
            }

            episode = JsonUtility.FromJson<EpisodeConfig>(asset.text);
            robotPolicy = RobotPolicyCatalog.Load().Require(episode.RobotId);
            PolicyProviderFactory.ValidatePolicyCompatibility(episode, robotPolicy);
            controller = new PurePursuitController(episode.controller);
            pose = Pose2D.FromConfig(episode.start);
            simTime = 0.0f;
            policyProvider = PolicyProviderFactory.Attach(gameObject, episode, robotPolicy, repoRoot);

            if (bindImportedScene)
            {
                BindImportedScene();
            }

            if (robotRoot != null)
            {
                robotRoot.position = pose.ToUnity(robotProxyHeight);
                robotRoot.rotation = Quaternion.Euler(0.0f, -pose.Yaw * Mathf.Rad2Deg, 0.0f);
            }
        }

        [ContextMenu("Rebuild Visual Proxy")]
        public void BuildVisualProxy()
        {
            ClearSpawned();
            BuildFloor();
            BuildGoal();
            BuildStaticObstacles();
            BuildDynamicObstacleProxies();
        }

        [ContextMenu("Bind Imported Scene")]
        public void BindImportedScene()
        {
            Transform searchRoot = importedSceneRoot != null ? importedSceneRoot : transform.root;
            if (robotRoot == null)
            {
                robotRoot = FindDeepChild(searchRoot, episode.RobotId == "go2" ? "base_link" : "pelvis");
            }

            if (robotRoot != null)
            {
                robotProxyHeight = robotRoot.position.y;
            }

            if (!buildUnityVisualProxy)
            {
                BindImportedDynamicObstacles(searchRoot);
            }
        }

        void BuildFloor()
        {
            float width = episode.world.x_max - episode.world.x_min;
            float depth = episode.world.y_max - episode.world.y_min;
            GameObject floor = GameObject.CreatePrimitive(PrimitiveType.Cube);
            floor.name = $"{episode.episode.id}_floor";
            floor.transform.SetParent(transform, false);
            floor.transform.position = new Vector3(
                episode.world.x_min + width * 0.5f,
                -0.015f,
                episode.world.y_min + depth * 0.5f);
            floor.transform.localScale = new Vector3(width, 0.03f, depth);
            Paint(floor, new Color(0.72f, 0.74f, 0.70f));
            spawned.Add(floor);
        }

        void BuildGoal()
        {
            GameObject goal = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            goal.name = $"{episode.episode.id}_goal";
            goal.transform.SetParent(transform, false);
            goal.transform.position = new Vector3(episode.goal.x, 0.025f, episode.goal.y);
            goal.transform.localScale = new Vector3(0.56f, 0.025f, 0.56f);
            Paint(goal, new Color(0.0f, 0.82f, 0.25f));
            spawned.Add(goal);
        }

        void BuildStaticObstacles()
        {
            foreach (RectObstacleConfig obstacle in episode.world.obstacles)
            {
                float width = obstacle.x_max - obstacle.x_min;
                float depth = obstacle.y_max - obstacle.y_min;
                GameObject block = GameObject.CreatePrimitive(PrimitiveType.Cube);
                block.name = $"{episode.episode.id}_static_obstacle";
                block.transform.SetParent(transform, false);
                block.transform.position = new Vector3(
                    obstacle.x_min + width * 0.5f,
                    0.25f,
                    obstacle.y_min + depth * 0.5f);
                block.transform.localScale = new Vector3(width, 0.5f, depth);
                Paint(block, new Color(0.82f, 0.05f, 0.03f));
                spawned.Add(block);
            }
        }

        void BuildDynamicObstacleProxies()
        {
            dynamicProxies.Clear();
            foreach (DynamicObstacleRuntime obstacle in DynamicObstacleRuntime.Build(episode.dynamic_obstacles, episode.world))
            {
                PrimitiveType primitive = obstacle.Mode == "npc" ? PrimitiveType.Capsule : PrimitiveType.Cylinder;
                GameObject proxy = GameObject.CreatePrimitive(primitive);
                proxy.name = obstacle.Name;
                proxy.transform.SetParent(transform, false);
                proxy.transform.localScale = obstacle.Mode == "npc"
                    ? new Vector3(obstacle.Radius * 2.0f, obstacle.HalfHeight, obstacle.Radius * 2.0f)
                    : new Vector3(obstacle.Radius * 2.0f, obstacle.HalfHeight * 2.0f, obstacle.Radius * 2.0f);
                Paint(proxy, obstacle.Mode == "npc" ? new Color(0.12f, 0.16f, 0.22f) : new Color(0.05f, 0.2f, 1.0f));
                spawned.Add(proxy);
                dynamicProxies.Add(obstacle, proxy.transform);
            }

            UpdateDynamicObstacles();
        }

        void BindImportedDynamicObstacles(Transform searchRoot)
        {
            dynamicProxies.Clear();
            foreach (DynamicObstacleRuntime obstacle in DynamicObstacleRuntime.Build(episode.dynamic_obstacles, episode.world))
            {
                Transform imported = FindDeepChild(searchRoot, obstacle.Name);
                if (imported == null)
                {
                    continue;
                }

                dynamicProxies.Add(obstacle, imported);
            }

            UpdateDynamicObstacles();
        }

        void UpdateDynamicObstacles()
        {
            foreach (KeyValuePair<DynamicObstacleRuntime, Transform> entry in dynamicProxies)
            {
                Vector2 position = entry.Key.PositionAt(simTime);
                entry.Value.position = new Vector3(position.x, entry.Key.HalfHeight, position.y);
                entry.Value.rotation = Quaternion.Euler(0.0f, -entry.Key.YawAt(simTime) * Mathf.Rad2Deg, 0.0f);
            }
        }

        void ConfigureCamera()
        {
            if (Camera.main == null || episode.visualization == null || episode.visualization.camera == null)
            {
                return;
            }

            CameraConfig cameraConfig = episode.visualization.camera;
            Vector3 lookat = new Vector3(cameraConfig.lookat.x, cameraConfig.lookat.z, cameraConfig.lookat.y);
            float distance = cameraConfig.distance > 0.05f ? cameraConfig.distance : Mathf.Max(5.0f, episode.world.x_max - episode.world.x_min);
            float azimuth = cameraConfig.azimuth * Mathf.Deg2Rad;
            float elevation = cameraConfig.elevation * Mathf.Deg2Rad;
            Vector3 offset = new Vector3(
                Mathf.Sin(azimuth) * Mathf.Cos(elevation),
                Mathf.Sin(elevation),
                Mathf.Cos(azimuth) * Mathf.Cos(elevation)) * distance;
            Camera.main.transform.position = lookat + offset;
            Camera.main.transform.LookAt(lookat);
        }

        void Paint(GameObject target, Color color)
        {
            Renderer renderer = target.GetComponent<Renderer>();
            if (renderer == null)
            {
                return;
            }

            renderer.sharedMaterial = new Material(Shader.Find("Standard"))
            {
                color = color
            };
        }

        void ClearSpawned()
        {
            for (int i = spawned.Count - 1; i >= 0; i -= 1)
            {
                if (spawned[i] == null)
                {
                    continue;
                }

                if (Application.isPlaying)
                {
                    Destroy(spawned[i]);
                }
                else
                {
                    DestroyImmediate(spawned[i]);
                }
            }

            spawned.Clear();
            dynamicProxies.Clear();
        }

        static Transform FindDeepChild(Transform parent, string childName)
        {
            if (parent == null)
            {
                return null;
            }

            if (parent.name == childName)
            {
                return parent;
            }

            for (int i = 0; i < parent.childCount; i += 1)
            {
                Transform found = FindDeepChild(parent.GetChild(i), childName);
                if (found != null)
                {
                    return found;
                }
            }

            return null;
        }
    }
}
