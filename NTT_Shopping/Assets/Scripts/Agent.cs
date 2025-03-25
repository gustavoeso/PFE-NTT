using UnityEngine;
using UnityEngine.Networking;
using System.Text;
using System.Threading.Tasks;

public class Agent : MonoBehaviour
{
    protected UnityEngine.AI.NavMeshAgent navMeshAgent;
    protected bool isRequestInProgress = false;
    protected Animator animator;

    protected virtual void Start()
    {
        animator = GetComponent<Animator>();
        navMeshAgent = GetComponent<UnityEngine.AI.NavMeshAgent>();
    }

    // Método base para iniciar uma conversa (pode ser sobrescrito)
    public virtual Task StartConversation(string dialoguePartner)
    {
        if (navMeshAgent != null)
        {   
            navMeshAgent.velocity  = Vector3.zero;
            navMeshAgent.isStopped = true;
        }
        return Task.CompletedTask;
    }

    // Envia um prompt para um agente específico na API
    protected async Task<string> SendPrompt(string prompt, string agentId, string speaker)
    {
        isRequestInProgress = true;
        
        // Remoção de aspas para evitar problemas e serialização correta do prompt.
        prompt = prompt.Replace("\"", "");
        
        // Criação do objeto e serialização para JSON.
        PromptData data = new PromptData { prompt = prompt, speaker = speaker };
        string jsonData = JsonUtility.ToJson(data);
        
        // Conversão do JSON para bytes.
        byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonData);
        
        string url = "http://localhost:8000/request/" + agentId;
        
        using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
        {
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
        
            var operation = request.SendWebRequest();
            while (!operation.isDone)
            {
                await Task.Yield();
            }
        
            isRequestInProgress = false;
        
            if (request.result == UnityWebRequest.Result.Success)
            {
                return request.downloadHandler.text;
            }
            else
            {
                Debug.LogError("Erro: " + request.error);
                return null;
            }
        }
    }

    // Extrai a resposta do JSON retornado pela API
    protected string ExtractResponse(string jsonResponse)
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

[System.Serializable]
public class PromptData {
    public string prompt;
    public string speaker;
}




