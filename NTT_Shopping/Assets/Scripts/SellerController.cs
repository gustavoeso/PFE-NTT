using UnityEngine;
using System.Threading.Tasks;

public class Seller : MonoBehaviour
{
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
        await clientAgent.StartConversation("Seller");
    }
}




