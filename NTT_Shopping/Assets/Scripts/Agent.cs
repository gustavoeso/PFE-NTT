using UnityEngine;
using UnityEngine.Networking;
using System.Text;
using System.Threading.Tasks;

public class Agent : MonoBehaviour
{
    protected UnityEngine.AI.NavMeshAgent navMeshAgent;
    protected bool isRequestInProgress = false;
    protected Animator animator;

    // (1) A random agent_id for each Agent (or each Client).
    protected string myAgentId;

    protected virtual void Start()
    {
        // Generate a random or unique ID for this agent.
        // Example: a short substring of a full GUID
        myAgentId = System.Guid.NewGuid().ToString().Substring(0, 8);
        Debug.Log($"[Agent] Generated agent_id={myAgentId}");

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
    protected async Task<string> SendPrompt(string prompt, string endpointName, string speaker)
    {
        isRequestInProgress = true;

        // Remove extra quotes for safety
        prompt = prompt.Replace("\"", "");

        // (2) Include agent_id in the request body
        PromptData data = new PromptData
        {
            prompt   = prompt,
            speaker  = speaker,
            agent_id = myAgentId // Use our newly generated ID
        };

        string jsonData = JsonUtility.ToJson(data);
        byte[] bodyRaw  = Encoding.UTF8.GetBytes(jsonData);

        // We'll build a URL using endpointName: "guide", "store", or "client"
        string url = "http://localhost:8000/request/" + endpointName;

        using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
        {
            request.uploadHandler   = new UploadHandlerRaw(bodyRaw);
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

// Updated PromptData to include agent_id
[System.Serializable]
public class PromptData
{
    public string prompt;
    public string speaker;
    public string agent_id; // new
}
