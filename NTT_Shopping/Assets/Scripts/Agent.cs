using UnityEngine;
using UnityEngine.Networking;
using System.Text;
using System.Threading.Tasks;
using System.Collections.Generic;

public class Agent : MonoBehaviour
{
    protected UnityEngine.AI.NavMeshAgent navMeshAgent;
    protected string state = "idle"; // Estado inicial
    private bool isRequestInProgress = false; // Flag para evitar múltiplos requests
    public string store; // Nome/ID da loja que o cliente deve visitar

    protected virtual void Update()
    {
    }
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
            string ClientResponse = await SendPrompt("Bola de Futebol", "client");
            await Task.Delay(3000);
            string formattedResponse = ExtractResponse(ClientResponse);
            Debug.Log("Pergunta do cliente: " + formattedResponse);

            string SellerResponse = await SendPrompt(formattedResponse, "seller");
            await Task.Delay(3000);
            formattedResponse = ExtractResponse(SellerResponse);
            Debug.Log("Resposta do vendedor: " + formattedResponse);

            string FilteredStore = await SendPrompt(formattedResponse, "filter");
            await Task.Delay(3000);
            formattedResponse = ExtractResponse(FilteredStore);
            Debug.Log("Loja filtrada: " + formattedResponse);
            other.state = "searchingStore";
            other.store = formattedResponse;
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

    // 🔹 Método para extrair apenas o valor da chave "response" do JSON recebido
    private string ExtractResponse(string jsonResponse)
    {
        if (string.IsNullOrEmpty(jsonResponse))
        {
            return "Resposta vazia ou inválida";
        }

        try
        {
            ResponseData data = JsonUtility.FromJson<ResponseData>(jsonResponse);
            return data.response ?? "Chave 'response' não encontrada";
        }
        catch (System.Exception e)
        {
            Debug.LogError("Erro ao processar JSON: " + e.Message);
            return "Erro na formatação do JSON";
        }
    }
}

[System.Serializable]
public class ResponseData
{
    public string response;
}



