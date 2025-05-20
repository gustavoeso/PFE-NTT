using UnityEngine;
using System.Threading.Tasks;

public class Agent : MonoBehaviour
{
    public string agentType;
    public string agentDescription;

    public async void OnTriggerEntered(TriggerRelay.TriggerType triggerType, Collider other)
    {
        Client clientAgent = other.GetComponent<Client>();
        if (clientAgent == null) return;

        if (triggerType == TriggerRelay.TriggerType.Small)
        {
            await clientAgent.StartConversation(agentType);
        }
        else if (triggerType == TriggerRelay.TriggerType.Big)
        {
            await clientAgent.PossibleInterest(agentDescription, other.transform.position);
        }
        else
        {
            Debug.LogError("Tipo de trigger desconhecido.");
        }
    }
}

