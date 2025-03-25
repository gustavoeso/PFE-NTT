using UnityEngine;
using UnityEngine.Networking;
using System;
using System.IO;
using System.Threading.Tasks;

public class TTSManager : MonoBehaviour
{
    public static TTSManager Instance;

    [Header("Voices disponíveis")]
    public string voiceClient = "shimmer";
    public string voiceGuide = "alloy";

    [Header("Config da API")]
    public string openAIEndpoint = "https://api.openai.com/v1/audio/speech";
    public string apiKey;

    private void Awake()
    {
        if (Instance == null) Instance = this;
        else Destroy(gameObject);

        EnvLoader.LoadEnv();
                apiKey = Environment.GetEnvironmentVariable("OPENAI_API_KEY");
        if (!string.IsNullOrEmpty(apiKey))
        {
            apiKey = apiKey.Trim();
        }

        if (string.IsNullOrEmpty(apiKey))
        {
            Debug.LogError("Nenhuma API Key foi encontrada! Verifique suas variáveis de ambiente ou insira a chave no Inspector.");
            return;
        }
    }

    public async Task SpeakAsync(string text, string voice)
    {
        var tempFilePath = await GenerateSpeechFile(text, voice);

        if (!string.IsNullOrEmpty(tempFilePath))
        {
            await PlayAudioAsync(tempFilePath);
        }
    }

    private async Task<string> GenerateSpeechFile(string text, string voiceModel)
    {
        var model = "tts-1";
        string mp3Path = Path.Combine(Application.persistentDataPath, "ttsSpeech.mp3");

        var requestData = new TTSRequest(model, text, voiceModel);
        var jsonData = JsonUtility.ToJson(requestData);

        using (var request = new UnityWebRequest(openAIEndpoint, "POST"))
        {
            byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(jsonData);
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();

            request.SetRequestHeader("Content-Type", "application/json");
            request.SetRequestHeader("Authorization", $"Bearer {apiKey}");

            var operation = request.SendWebRequest();
            while (!operation.isDone)
            {
                await Task.Yield();
            }

            if (request.result == UnityWebRequest.Result.Success)
            {
                File.WriteAllBytes(mp3Path, request.downloadHandler.data);
                return mp3Path;
            }
            else
            {
                Debug.LogError($"TTS falhou: {request.error}\n{request.downloadHandler.text}");
                return null;
            }
        }
    }

    private async Task PlayAudioAsync(string filePath)
    {
        using (UnityWebRequest www = UnityWebRequestMultimedia.GetAudioClip("file://" + filePath, AudioType.MPEG))
        {
            var operation = www.SendWebRequest();
            while (!operation.isDone)
            {
                await Task.Yield();
            }

            if (www.result == UnityWebRequest.Result.Success)
            {
                AudioClip clip = DownloadHandlerAudioClip.GetContent(www);
                AudioSource audioSource = gameObject.AddComponent<AudioSource>();
                audioSource.clip = clip;
                audioSource.Play();

                while (audioSource.isPlaying)
                {
                    await Task.Yield();
                }

                Destroy(audioSource);
                Destroy(clip);
            }
            else
            {
                Debug.LogError($"Erro ao carregar áudio para reprodução: {www.error}");
            }
        }
    }

    [Serializable]
    public class TTSRequest
    {
        public string model;
        public string input;
        public string voice;

        public TTSRequest(string model, string input, string voice)
        {
            this.model = model;
            this.input = input;
            this.voice = voice;
        }
    }
}




