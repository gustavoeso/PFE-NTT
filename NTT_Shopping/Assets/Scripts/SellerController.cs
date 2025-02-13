using UnityEngine;
using System.Threading.Tasks;

public class Seller : Agent
{
    private void OnTriggerEnter(Collider other)
    {
        if (other.CompareTag("Client"))
        {
            Agent clientAgent = other.GetComponent<Agent>();
            if (clientAgent != null)
            {
                // Chama o método assíncrono sem bloquear o jogo
                StartConversationAsync(clientAgent);
            }
        }
    }

    // 🔹 Método auxiliar para rodar o StartConversation de forma assíncrona
    private async void StartConversationAsync(Agent clientAgent)
    {
        await StartConversation(clientAgent);
    }
}




