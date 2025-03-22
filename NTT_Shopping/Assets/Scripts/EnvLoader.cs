using UnityEngine;
using System;
using System.IO;

public static class EnvLoader
{
    public static void LoadEnv()
    {
        string envPath = Path.Combine(Application.dataPath, ".env");

        if (!File.Exists(envPath))
        {
            Debug.LogError("Arquivo .env não encontrado!");
            return;
        }

        foreach (var line in File.ReadAllLines(envPath))
        {
            if (!string.IsNullOrWhiteSpace(line) && line.Contains("="))
            {
                var parts = line.Split('=');
                string key = parts[0].Trim();
                string value = parts[1].Trim();
                Environment.SetEnvironmentVariable(key, value);
            }
        }

        Debug.Log("Variáveis do .env carregadas!");
    }
}
