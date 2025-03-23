using UnityEngine;


public class Guide : MonoBehaviour
{
    private bool hasTalked = false;  // Only allow one conversation with the client

    private async void OnTriggerEnter(Collider other)
    {
        if (other.CompareTag("Client"))
        {
            if (hasTalked)
            {
                Debug.Log("[Guide] Já conversei com este Client. Ignorando.");
                return;
            }
            hasTalked = true;

            Client clientAgent = other.GetComponent<Client>();
            if (clientAgent != null)
            {
                Debug.Log("[Guide] Starting conversation with client...");
                await clientAgent.StartConversation("Guide");
            }
        }
    }
}
