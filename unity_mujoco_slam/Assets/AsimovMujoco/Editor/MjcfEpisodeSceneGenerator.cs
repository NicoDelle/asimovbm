using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using Mujoco;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace Asimov.UnityMujoco.Editor
{
    public static class MjcfEpisodeSceneGenerator
    {
        const string OutputDirectory = "Assets/AsimovMujoco/GeneratedMjcf";
        const string SceneDirectory = "Assets/AsimovMujoco/Scenes";
        const string RunnerScenePath = "Assets/AsimovMujoco/Scenes/AsimovMujocoEpisodes.unity";
        const string G1MeshDir = "../../../../g1_slam/third_party/unitree_mujoco/unitree_robots/g1/meshes";
        const string G1UnityMeshDir = "../GeneratedMeshes/g1";
        const string G1GeneratedMeshDirectory = "Assets/AsimovMujoco/GeneratedMeshes/g1";
        const string Go2MeshDir = "../../../../g1_slam/third_party/unitree_mujoco/unitree_robots/go2/assets";

        [MenuItem("Asimov/MuJoCo Episodes/Bootstrap Project")]
        public static void BootstrapProject()
        {
            GenerateAll();
            ImportAllEpisodeScenes();
            CreateEpisodeLauncherScene();
        }

        [MenuItem("Asimov/MuJoCo Episodes/Generate All MJCF Scenes")]
        public static void GenerateAll()
        {
            Directory.CreateDirectory(OutputDirectory);
            EnsureG1UnityMeshCopies();
            foreach (TextAsset asset in Resources.LoadAll<TextAsset>("Episodes"))
            {
                EpisodeConfig episode = JsonUtility.FromJson<EpisodeConfig>(asset.text);
                string path = Path.Combine(OutputDirectory, $"{episode.episode.id}.xml");
                File.WriteAllText(path, BuildSceneXml(episode), Encoding.UTF8);
                Debug.Log($"Generated {path}");
            }

            AssetDatabase.Refresh();
        }

        [MenuItem("Asimov/MuJoCo Episodes/Import All Episode Scenes")]
        public static void ImportAllEpisodeScenes()
        {
            Directory.CreateDirectory(SceneDirectory);
            foreach (TextAsset asset in Resources.LoadAll<TextAsset>("Episodes").OrderBy(asset => asset.name))
            {
                EpisodeConfig episode = JsonUtility.FromJson<EpisodeConfig>(asset.text);
                ImportEpisodeScene(episode);
            }

            AssetDatabase.Refresh();
        }

        [MenuItem("Asimov/MuJoCo Episodes/Create Episode Launcher Scene")]
        public static void CreateEpisodeLauncherScene()
        {
            Directory.CreateDirectory(SceneDirectory);
            Scene scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            GameObject runner = new GameObject("EpisodeRunner");
            UnityMujocoEpisodeRunner episodeRunner = runner.AddComponent<UnityMujocoEpisodeRunner>();
            episodeRunner.episodeId = "g1_lateral_open";
            episodeRunner.repoRoot = "..";
            episodeRunner.bindImportedScene = false;
            episodeRunner.buildUnityVisualProxy = true;
            episodeRunner.driveKinematicProxy = false;

            CreateCamera(JsonUtility.FromJson<EpisodeConfig>(Resources.Load<TextAsset>("Episodes/g1_lateral_open").text));
            CreateDirectionalLight();

            EditorSceneManager.SaveScene(scene, RunnerScenePath);
            AssetDatabase.Refresh();
            Debug.Log($"Created {RunnerScenePath}");
        }

        static void ImportEpisodeScene(EpisodeConfig episode)
        {
            string mjcfAssetPath = Path.Combine(OutputDirectory, $"{episode.episode.id}.xml");
            string mjcfAbsolutePath = Path.GetFullPath(mjcfAssetPath);
            if (!File.Exists(mjcfAbsolutePath))
            {
                File.WriteAllText(mjcfAbsolutePath, BuildSceneXml(episode), Encoding.UTF8);
            }

            Scene scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            EnsureG1UnityMeshCopies();
            ClearPreviousImportedAssets(episode);
            GameObject importedRoot = ImportExpandedEpisodeScene(episode, mjcfAbsolutePath);
            if (importedRoot == null)
            {
                throw new UnityException($"MuJoCo importer failed to create a scene for {episode.episode.id}.");
            }

            importedRoot.name = "ImportedMuJoCoScene";
            PlaceImportedRobotRoot(importedRoot.transform, episode);

            GameObject runner = new GameObject("EpisodeRunner");
            UnityMujocoEpisodeRunner episodeRunner = runner.AddComponent<UnityMujocoEpisodeRunner>();
            episodeRunner.episodeId = episode.episode.id;
            episodeRunner.repoRoot = "..";
            episodeRunner.importedSceneRoot = importedRoot.transform;
            episodeRunner.bindImportedScene = true;
            episodeRunner.buildUnityVisualProxy = false;
            episodeRunner.driveKinematicProxy = true;
            episodeRunner.robotProxyHeight = episode.RobotId == "go2" ? 0.445f : 0.793f;
            episodeRunner.robotRoot = FindDeepChild(importedRoot.transform, episode.RobotId == "go2" ? "base_link" : "pelvis");

            CreateCamera(episode);
            CreateDirectionalLight();

            string scenePath = Path.Combine(SceneDirectory, $"{episode.episode.id}.unity");
            EditorSceneManager.SaveScene(scene, scenePath);
            Debug.Log($"Created imported MuJoCo episode scene {scenePath}");
        }

        static GameObject ImportExpandedEpisodeScene(EpisodeConfig episode, string mjcfAbsolutePath)
        {
            string mjcf = File.ReadAllText(mjcfAbsolutePath, Encoding.UTF8).TrimStart('\uFEFF');

            return new MjImporterWithAssets().ImportString(
                mjcf,
                $"{episode.episode.id}_imported",
                mjcfAbsolutePath);
        }

        static void ClearPreviousImportedAssets(EpisodeConfig episode)
        {
            string importAssetPath = $"Assets/Local/MjImports/{episode.episode.id}_imported";
            if (AssetDatabase.IsValidFolder(importAssetPath))
            {
                AssetDatabase.DeleteAsset(importAssetPath);
            }
        }

        public static string BuildSceneXml(EpisodeConfig episode)
        {
            string meshDir = episode.RobotId == "go2" ? Go2MeshDir : G1UnityMeshDir;
            string modelName = XmlValue($"{episode.episode.id}_unity_nav");
            string statisticCenter = episode.RobotId == "go2" ? "0 0 0.35" : "0 0 0.8";
            string statisticExtent = episode.RobotId == "go2" ? "6.0" : "8.0";
            string robotXml = File.ReadAllText(RobotXmlPath(episode), Encoding.UTF8).TrimStart('\uFEFF');
            if (episode.RobotId == "g1")
            {
                robotXml = robotXml.Replace(".STL", ".stl");
            }

            robotXml = NameAnonymousMeshes(robotXml);
            robotXml = ReplaceOpeningTag(robotXml, "mujoco", $"<mujoco model=\"{modelName}\">");
            robotXml = ReplaceOrInsertCompiler(robotXml, $"  <compiler angle=\"radian\" meshdir=\"{meshDir}\" autolimits=\"true\" />");
            robotXml = InsertAfterOpeningTag(
                robotXml,
                "mujoco",
                $"  <statistic center=\"{statisticCenter}\" extent=\"{statisticExtent}\"/>\n{VisualXml()}");
            robotXml = InsertBeforeClosingTag(robotXml, "asset", AssetMaterialXml());
            robotXml = InsertBeforeClosingTag(robotXml, "worldbody", WorldBodyOverlayXml(episode));
            return robotXml;
        }

        static string RobotXmlPath(EpisodeConfig episode)
        {
            string robotRelativePath = episode.RobotId == "go2"
                ? Path.Combine("g1_slam", "third_party", "unitree_mujoco", "unitree_robots", "go2", "go2.xml")
                : Path.Combine("g1_slam", "third_party", "unitree_mujoco", "unitree_robots", "g1", "g1_29dof.xml");
            return Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", robotRelativePath));
        }

        static void EnsureG1UnityMeshCopies()
        {
            string meshesDir = Path.GetFullPath(
                Path.Combine(Application.dataPath, "..", "..", "g1_slam", "third_party", "unitree_mujoco", "unitree_robots", "g1", "meshes"));
            if (!Directory.Exists(meshesDir))
            {
                Debug.LogWarning($"G1 meshes directory not found: {meshesDir}");
                return;
            }

            Directory.CreateDirectory(G1GeneratedMeshDirectory);
            foreach (string source in Directory.GetFiles(meshesDir, "*.STL"))
            {
                string target = Path.Combine(
                    G1GeneratedMeshDirectory,
                    Path.GetFileNameWithoutExtension(source) + ".stl");
                byte[] contents = File.ReadAllBytes(source);
                if (contents.Length >= 5
                    && contents[0] == (byte)'s'
                    && contents[1] == (byte)'o'
                    && contents[2] == (byte)'l'
                    && contents[3] == (byte)'i'
                    && contents[4] == (byte)'d')
                {
                    contents[0] = (byte)'b';
                    contents[1] = (byte)'i';
                    contents[2] = (byte)'n';
                    contents[3] = (byte)'r';
                    contents[4] = (byte)'y';
                }

                if (File.Exists(target) && File.ReadAllBytes(target).SequenceEqual(contents))
                {
                    continue;
                }

                File.WriteAllBytes(target, contents);
            }
        }

        static string NameAnonymousMeshes(string xml)
        {
            return Regex.Replace(
                xml,
                "<mesh\\s+file=\"([^\"]+)\"\\s*/>",
                match =>
                {
                    string file = match.Groups[1].Value;
                    string name = Path.GetFileNameWithoutExtension(file);
                    return $"<mesh name=\"{XmlValue(name)}\" file=\"{XmlValue(file)}\" />";
                });
        }

        static void PlaceImportedRobotRoot(Transform importedRoot, EpisodeConfig episode)
        {
            Transform robot = FindDeepChild(importedRoot, episode.RobotId == "go2" ? "base_link" : "pelvis");
            if (robot == null)
            {
                Debug.LogWarning($"Could not find imported robot root for {episode.episode.id}.");
                return;
            }

            float height = episode.RobotId == "go2" ? 0.445f : 0.793f;
            robot.position = new Vector3(episode.start.x, height, episode.start.y);
            robot.rotation = Quaternion.Euler(0.0f, -episode.start.yaw * Mathf.Rad2Deg, 0.0f);
        }

        static Camera CreateCamera(EpisodeConfig episode)
        {
            GameObject cameraObject = new GameObject("Main Camera");
            Camera camera = cameraObject.AddComponent<Camera>();
            camera.tag = "MainCamera";

            CameraConfig cameraConfig = episode.visualization.camera;
            Vector3 lookat = new Vector3(cameraConfig.lookat.x, cameraConfig.lookat.z, cameraConfig.lookat.y);
            float distance = cameraConfig.distance > 0.05f
                ? cameraConfig.distance
                : Mathf.Max(5.0f, episode.world.x_max - episode.world.x_min);
            float azimuth = cameraConfig.azimuth * Mathf.Deg2Rad;
            float elevation = cameraConfig.elevation * Mathf.Deg2Rad;
            Vector3 offset = new Vector3(
                Mathf.Sin(azimuth) * Mathf.Cos(elevation),
                Mathf.Sin(elevation),
                Mathf.Cos(azimuth) * Mathf.Cos(elevation)) * distance;
            camera.transform.position = lookat + offset;
            camera.transform.LookAt(lookat);
            return camera;
        }

        static Light CreateDirectionalLight()
        {
            GameObject lightObject = new GameObject("Directional Light");
            Light light = lightObject.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.2f;
            lightObject.transform.rotation = Quaternion.Euler(50.0f, -30.0f, 0.0f);
            return light;
        }

        static Transform FindDeepChild(Transform parent, string childName)
        {
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

        static void AppendFloor(StringBuilder xml, WorldConfig world)
        {
            float centerX = (world.x_min + world.x_max) * 0.5f;
            float centerY = (world.y_min + world.y_max) * 0.5f;
            float halfX = (world.x_max - world.x_min) * 0.5f;
            float halfY = (world.y_max - world.y_min) * 0.5f;
            xml.AppendLine(
                $"    <geom name=\"nav_floor\" type=\"box\" pos=\"{F(centerX)} {F(centerY)} -0.015\" size=\"{F(halfX)} {F(halfY)} 0.015\" material=\"floor_mat\"/>");
        }

        static void AppendGoal(StringBuilder xml, GoalConfig goal)
        {
            xml.AppendLine(
                $"    <geom name=\"goal\" type=\"cylinder\" pos=\"{F(goal.x)} {F(goal.y)} 0.02\" size=\"0.28 0.02\" material=\"goal_mat\"/>");
        }

        static void AppendStaticObstacles(StringBuilder xml, RectObstacleConfig[] obstacles)
        {
            for (int i = 0; i < obstacles.Length; i += 1)
            {
                RectObstacleConfig obstacle = obstacles[i];
                float centerX = (obstacle.x_min + obstacle.x_max) * 0.5f;
                float centerY = (obstacle.y_min + obstacle.y_max) * 0.5f;
                float halfX = (obstacle.x_max - obstacle.x_min) * 0.5f;
                float halfY = (obstacle.y_max - obstacle.y_min) * 0.5f;
                xml.AppendLine(
                    $"    <geom name=\"static_obstacle_{i}\" type=\"box\" pos=\"{F(centerX)} {F(centerY)} 0.25\" size=\"{F(halfX)} {F(halfY)} 0.25\" material=\"obstacle_mat\"/>");
            }
        }

        static void AppendDynamicObstacles(StringBuilder xml, EpisodeConfig episode)
        {
            IReadOnlyList<DynamicObstacleRuntime> obstacles = DynamicObstacleRuntime.Build(episode.dynamic_obstacles, episode.world);
            foreach (DynamicObstacleRuntime obstacle in obstacles)
            {
                Vector2 position = obstacle.PositionAt(0.0f);
                string material = obstacle.Mode == "npc" ? "npc_mat" : "blue_cylinder_mat";
                xml.AppendLine($"    <body name=\"{XmlValue(obstacle.Name)}\" mocap=\"true\" pos=\"{F(position.x)} {F(position.y)} 0\">");
                if (obstacle.Mode == "npc")
                {
                    xml.AppendLine(
                        $"      <geom type=\"capsule\" fromto=\"0 0 0.05 0 0 {F(obstacle.HalfHeight * 2.0f)}\" size=\"{F(obstacle.Radius)}\" material=\"{material}\"/>");
                }
                else
                {
                    xml.AppendLine(
                        $"      <geom type=\"cylinder\" pos=\"0 0 {F(obstacle.HalfHeight)}\" size=\"{F(obstacle.Radius)} {F(obstacle.HalfHeight)}\" material=\"{material}\"/>");
                }

                xml.AppendLine("    </body>");
            }
        }

        static string VisualXml()
        {
            return
                "  <visual>\n" +
                "    <headlight diffuse=\"0.55 0.55 0.55\" ambient=\"0.35 0.35 0.35\" specular=\"0.2 0.2 0.2\"/>\n" +
                "    <rgba haze=\"0.76 0.82 0.9 1\"/>\n" +
                "    <global azimuth=\"120\" elevation=\"-20\"/>\n" +
                "  </visual>";
        }

        static string AssetMaterialXml()
        {
            return
                "    <material name=\"floor_mat\" rgba=\"0.72 0.74 0.70 1\"/>\n" +
                "    <material name=\"obstacle_mat\" rgba=\"0.82 0.05 0.03 1\"/>\n" +
                "    <material name=\"goal_mat\" rgba=\"0 0.82 0.25 1\"/>\n" +
                "    <material name=\"npc_mat\" rgba=\"0.12 0.16 0.22 1\"/>\n" +
                "    <material name=\"blue_cylinder_mat\" rgba=\"0.05 0.2 1 1\"/>\n";
        }

        static string WorldBodyOverlayXml(EpisodeConfig episode)
        {
            StringBuilder xml = new StringBuilder();
            xml.AppendLine("    <light name=\"key\" pos=\"0 -4 8\" dir=\"0 0 -1\" directional=\"true\" diffuse=\"0.75 0.75 0.72\"/>");
            xml.AppendLine("    <light name=\"fill\" pos=\"-4 3 5\" dir=\"0 0 -1\" directional=\"true\" diffuse=\"0.25 0.28 0.32\"/>");
            AppendFloor(xml, episode.world);
            AppendGoal(xml, episode.goal);
            AppendStaticObstacles(xml, episode.world.obstacles);
            AppendDynamicObstacles(xml, episode);
            return xml.ToString();
        }

        static string ReplaceOpeningTag(string xml, string tagName, string replacement)
        {
            int start = xml.IndexOf($"<{tagName}", System.StringComparison.Ordinal);
            int end = xml.IndexOf(">", start, System.StringComparison.Ordinal);
            return xml.Substring(0, start) + replacement + xml.Substring(end + 1);
        }

        static string ReplaceOrInsertCompiler(string xml, string compilerXml)
        {
            int start = xml.IndexOf("<compiler", System.StringComparison.Ordinal);
            if (start >= 0)
            {
                int end = xml.IndexOf("/>", start, System.StringComparison.Ordinal);
                if (end >= 0)
                {
                    return xml.Substring(0, start) + compilerXml + xml.Substring(end + 2);
                }
            }

            return InsertAfterOpeningTag(xml, "mujoco", compilerXml);
        }

        static string InsertAfterOpeningTag(string xml, string tagName, string insertion)
        {
            int start = xml.IndexOf($"<{tagName}", System.StringComparison.Ordinal);
            int end = xml.IndexOf(">", start, System.StringComparison.Ordinal);
            return xml.Substring(0, end + 1) + "\n" + insertion + xml.Substring(end + 1);
        }

        static string InsertBeforeClosingTag(string xml, string tagName, string insertion)
        {
            int index = xml.LastIndexOf($"</{tagName}>", System.StringComparison.Ordinal);
            return xml.Substring(0, index) + insertion + xml.Substring(index);
        }

        static string F(float value)
        {
            return value.ToString("0.######", CultureInfo.InvariantCulture);
        }

        static string XmlValue(string value)
        {
            return value
                .Replace("&", "&amp;")
                .Replace("\"", "&quot;")
                .Replace("<", "&lt;")
                .Replace(">", "&gt;");
        }
    }
}
