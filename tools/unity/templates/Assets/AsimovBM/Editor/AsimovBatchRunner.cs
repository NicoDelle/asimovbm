using System;
using AsimovBM.Mujoco;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace AsimovBM.Editor
{
    public static class AsimovBatchRunner
    {
        public static void GenerateScenes()
        {
            try
            {
                AsimovMujocoSceneGenerator.GenerateAllScenes();
                EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                Debug.Log("AsimovBM batch scene generation completed.");
            }
            catch (Exception exc)
            {
                Debug.LogException(exc);
                EditorApplication.Exit(1);
            }
        }

        public static void RunAll()
        {
            GenerateScenes();
        }
    }
}
