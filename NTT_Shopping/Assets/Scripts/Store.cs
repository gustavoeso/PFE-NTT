using UnityEngine;

public class Store : MonoBehaviour
{
<<<<<<< HEAD
    public string StoreId; // e.g. "100", "105", etc.

    // We let the Client handle the conversation in code. 
    // So no OnTriggerEnter needed here.
=======
    public string StoreId;
    private async void OnTriggerEnter(Collider other)
    {
        if (other.CompareTag("Client"))
        {
            Client clientAgent = other.GetComponent<Client>();
            if (clientAgent != null)
            {
                if (clientAgent.canCollide){
                    await clientAgent.StartConversation("Store");
                }
            }
        }
    }
>>>>>>> 0149944923e8477417c7a2ff25f7a6a028ea750f
}
