using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.AI;

public class Store : Agent
{
    public string StoreId;
    private void OnTriggerEnter(Collider other)
    {
        if (other.CompareTag("Client"))
        {
            Agent clientAgent = other.GetComponent<Agent>();
            if (clientAgent != null)
            {
                StartConversationStoreAsync(clientAgent);
            }
        }
    }

    private async void StartConversationStoreAsync(Agent clientAgent)
    {
        await StartConversationStore(clientAgent);
    }
}
