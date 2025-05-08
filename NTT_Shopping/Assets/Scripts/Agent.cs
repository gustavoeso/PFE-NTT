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

        // Extrai a resposta do JSON retornado pela API
    protected string ExtractResponse(string jsonResponse)
    {
        if (string.IsNullOrEmpty(jsonResponse))
        {
            return "Resposta vazia ou inválida";
        }

        try
        {
            AgentResponse data = JsonUtility.FromJson<AgentResponse>(jsonResponse);
            return data.answer ?? "Chave 'answer' não encontrada";
        }
        catch (System.Exception e)
        {
            Debug.LogError("Erro ao processar JSON: " + e.Message);
            return "Erro na formatação do JSON";
        }
    }

    protected bool ExtractFinalOffer(string jsonResponse)
    {
        if (string.IsNullOrEmpty(jsonResponse)) return false;

        try
        {
            AgentResponse data = JsonUtility.FromJson<AgentResponse>(jsonResponse);
            return data.final_offer;
        }
        catch
        {
            return false;
        }
    }


}

[System.Serializable]
public class AgentResponse
{
    public string answer;
    public bool final_offer;
}


// Updated PromptData to include agent_id
[System.Serializable]
public class PromptData
{
    public string prompt;
    public string speaker;
    public string agent_id; // new
}
