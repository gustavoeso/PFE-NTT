using UnityEngine;

public class Store : MonoBehaviour
{
    public string StoreId; // Exemplo: "100", "105", etc.

    private async void OnTriggerEnter(Collider other)
    {
        if (other.CompareTag("Client"))
        {
            Client clientAgent = other.GetComponent<Client>();
            if (clientAgent != null)
            {
                await clientAgent.StartConversation("Store");
            }
        }
    }
}
