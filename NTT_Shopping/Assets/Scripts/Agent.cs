using UnityEngine;
using UnityEngine.Networking;
using System.Text;
using System.Threading.Tasks;

public class Agent : MonoBehaviour
{
    protected UnityEngine.AI.NavMeshAgent navMeshAgent;
    protected string state = "idle"; // Estado inicial
    private bool isRequestInProgress = false; // Flag para evitar múltiplos requests

    protected virtual void Start()
    {
        navMeshAgent = GetComponent<UnityEngine.AI.NavMeshAgent>();
    }

    // 🔹 Torna a função assíncrona para permitir o uso de `await`
    public async Task StartConversation(Agent other)
    {
        if (navMeshAgent != null)
        {
            navMeshAgent.isStopped = true; // Para o movimento
        }

        if (other.navMeshAgent != null)
        {
            other.navMeshAgent.isStopped = true; // Para o outro agente também
        }

        state = "dialogue";
        other.state = "dialogue";

        // Inicia o primeiro request, se nenhum estiver em progresso
        if (!isRequestInProgress)
        {
            string response = await SendPrompt("Sapato", "client");
            Debug.Log("Resposta do servidor: " + response);
        }
    }

    // 🔹 Método agora é assíncrono e retorna uma `Task<string>`
    private async Task<string> SendPrompt(string prompt, string agent)
    {
        isRequestInProgress = true; // Marca que há um request em andamento

        string jsonData = "{\"prompt\": \"" + prompt + "\"}";
        byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonData);

        // Cria uma requisição POST para o endpoint do servidor
        string path = "http://localhost:8000/request/" + agent;
        Debug.Log(path);

        using (UnityWebRequest request = new UnityWebRequest(path, "POST"))
        {
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");

            // 🔹 Usa `await` para aguardar a resposta do servidor
            var operation = request.SendWebRequest();

            while (!operation.isDone)
            {
                await Task.Yield(); // Aguarda até que a requisição termine sem travar a Unity
            }

            isRequestInProgress = false; // Marca que o request foi concluído

            if (request.result == UnityWebRequest.Result.Success)
            {
                return request.downloadHandler.text; // Retorna a resposta do servidor
            }
            else
            {
                Debug.LogError("Erro: " + request.error);
                return null;
            }
        }
    }
}



