using UnityEngine;
using UnityEngine.Networking;
using System.Collections;
using System.IO;
using System;

public class OpenAITTS : MonoBehaviour
{
    private string apiKey;

    void Start()
    {
        // Carrega as variáveis do .env antes de pegar a API Key
        EnvLoader.LoadEnv();

        // Agora a chave pode ser acessada pelo Environment
        apiKey = Environment.GetEnvironmentVariable("OPENAI_API_KEY");

        if (string.IsNullOrEmpty(apiKey))
        {
            Debug.LogError("Erro: A variável de ambiente OPENAI_API_KEY não foi encontrada!");
            return;
        }

        // Teste inicial ao iniciar a cena
        StartCoroutine(GenerateSpeech("Olá, mundo! Este é um teste de voz da OpenAI."));
    }

    public IEnumerator GenerateSpeech(string text)
    {
        string url = "https://api.openai.com/v1/audio/speech";
        string voiceModel = "alloy"; // Modelos disponíveis: alloy, echo, fable, onyx, nova, shimmer
        string tempFilePath = Path.Combine(Application.persistentDataPath, "speech.mp3");

        // Criando JSON da requisição
        string jsonData = $"{{\"model\":\"tts-1\",\"input\":\"{text}\",\"voice\":\"{voiceModel}\"}}";

        using (UnityWebRequest request = UnityWebRequest.PostWwwForm(url, ""))
        {
            byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(jsonData);
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            request.SetRequestHeader("Authorization", "Bearer " + apiKey);

            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                File.WriteAllBytes(tempFilePath, request.downloadHandler.data);
                PlayAudio(tempFilePath);
            }
            else
            {
                Debug.LogError("Erro ao acessar OpenAI API: " + request.error);
            }
        }
    }

    private void PlayAudio(string filePath)
    {
        StartCoroutine(LoadAndPlayAudio(filePath));
    }

    private IEnumerator LoadAndPlayAudio(string filePath)
    {
        using (UnityWebRequest www = UnityWebRequestMultimedia.GetAudioClip("file://" + filePath, AudioType.MPEG))
        {
            yield return www.SendWebRequest();

            if (www.result == UnityWebRequest.Result.Success)
            {
                AudioClip clip = DownloadHandlerAudioClip.GetContent(www);
                AudioSource audioSource = gameObject.AddComponent<AudioSource>();
                audioSource.clip = clip;
                audioSource.Play();
            }
            else
            {
                Debug.LogError("Erro ao carregar áudio: " + www.error);
            }
        }
    }
}
