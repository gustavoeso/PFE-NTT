using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.AI;

public class Store : MonoBehaviour
{
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
}
