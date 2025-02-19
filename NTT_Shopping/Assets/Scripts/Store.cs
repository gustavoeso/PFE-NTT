using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.AI;

public class Store : MonoBehaviour
{
    public string StoreId;
    private void OnTriggerEnter(Collider other)
    {
        if (other.CompareTag("Client"))
        {
            Client clientAgent = other.GetComponent<Client>();
            if (clientAgent != null)
            {
                StartConversationAsync(clientAgent);
            }
        }
    }

    private async void StartConversationAsync(Client clientAgent)
    {
        await clientAgent.StartConversation("Store");
    }
}
