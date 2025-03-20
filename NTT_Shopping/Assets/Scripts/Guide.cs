using UnityEngine;
using System.Threading.Tasks;

public class Guide : MonoBehaviour
{
    private async void OnTriggerEnter(Collider other)
    {
        if (other.CompareTag("Client"))
        {
            Client clientAgent = other.GetComponent<Client>();
            if (clientAgent != null)
            {   
                if (clientAgent.canCollide){
                    await clientAgent.StartConversation("Guide");
                }
            }
        }
    }
}





