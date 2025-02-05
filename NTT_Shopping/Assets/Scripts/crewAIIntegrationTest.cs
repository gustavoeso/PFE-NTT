using UnityEngine;
using UnityEngine.Networking;
using System.Collections;
using System.Text;

public class CrewAIIntegrationTest : MonoBehaviour
{
    void Start()
    {
        // Envie o prompt para o servidor assim que o jogo iniciar
        StartCoroutine(SendPrompt("quanto é 2 + 2?"));
    }

    IEnumerator SendPrompt(string prompt)
    {
        // Cria o JSON com o prompt
        string jsonData = "{\"prompt\": \"" + prompt + "\"}";
        byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonData);

        // Cria uma requisição POST para o endpoint do servidor
        UnityWebRequest request = new UnityWebRequest("http://localhost:8000/prompt", "POST");
        request.uploadHandler = new UploadHandlerRaw(bodyRaw);
        request.downloadHandler = new DownloadHandlerBuffer();
        request.SetRequestHeader("Content-Type", "application/json");

        // Envia a requisição e aguarda a resposta
        yield return request.SendWebRequest();

        if (request.result == UnityWebRequest.Result.Success)
        {
            Debug.Log("Resposta do servidor: " + request.downloadHandler.text);
        }
        else
        {
            Debug.Log("Erro: " + request.error);
        }
    }
}


