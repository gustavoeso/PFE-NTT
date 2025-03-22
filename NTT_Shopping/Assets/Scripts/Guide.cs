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
<<<<<<< HEAD
            {
                Debug.Log("[Guide] Starting conversation with client...");
                await clientAgent.StartConversation("Guide");
=======
            {   
                if (clientAgent.canCollide){
                    await clientAgent.StartConversation("Guide");
                }
>>>>>>> 0149944923e8477417c7a2ff25f7a6a028ea750f
            }
        }
    }
}
