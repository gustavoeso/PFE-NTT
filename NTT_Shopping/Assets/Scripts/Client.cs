using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.Networking;

public class Client : Agent
{
    private string requestedItem = "Bicicleta";

    protected override async void Start()
    {
        base.Start();
        
        // Chama a API /startApplication no início da aplicação.
        await CallStartApplication();

        // Procura pelo objeto com tag "Guide" e define sua posição como destino inicial.
        GameObject guide = GameObject.FindGameObjectWithTag("Guide");
        if (guide != null)
        {
            Vector3 guidePosition = guide.transform.position;
            navMeshAgent.SetDestination(guidePosition);
        }
    }

    // Método auxiliar para chamar a API /startApplication.
    private async Task CallStartApplication()
    {
        string url = "http://localhost:8000/startApplication";
        using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
        {
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");

            var operation = request.SendWebRequest();
            while (!operation.isDone)
            {
                await Task.Yield();
            }

            if (request.result != UnityWebRequest.Result.Success)
            {
                Debug.LogError("Erro ao chamar /startApplication: " + request.error);
            }
            else
            {
                Debug.Log("API /startApplication chamada com sucesso: " + request.downloadHandler.text);
            }
        }
    }

    public override async Task StartConversation(string dialoguePartner)
    {
        await base.StartConversation(dialoguePartner);

        if (isRequestInProgress)
        {
            return;
        }

        if (dialoguePartner == "Guide")
        {
            string initialPrompt = "Formalize uma pergunta sobre onde encontrar o produto desejado : " + requestedItem;
            string clientResponse = await SendPrompt(initialPrompt, "client");
            string formattedResponse = ExtractResponse(clientResponse);
            Debug.Log("Pergunta do cliente: " + formattedResponse);

            // 2) Resposta enviada ao agente "seller"
            string sellerResponse = await SendPrompt(formattedResponse, "guide");
            formattedResponse = ExtractResponse(sellerResponse);
            Debug.Log("Resposta do vendedor: " + formattedResponse);

            // 3) Filtro: envia ao agente "filter" para identificar a loja correta
            string filteredStoreResponse = await SendPrompt(formattedResponse, "filter");
            formattedResponse = ExtractResponse(filteredStoreResponse);
            Debug.Log("Loja filtrada: " + formattedResponse);

            navMeshAgent.isStopped = false;
            Store targetStore = FindStore(formattedResponse);
            if (targetStore != null)
            {
                navMeshAgent.SetDestination(targetStore.transform.position);
            }
            else
            {
                Debug.LogError("Loja não encontrada para o ID: " + formattedResponse);
            }
        }
        else if (dialoguePartner == "Store")
        {
            // Em diálogo com a loja, utiliza o agente "clothes"
            string storeResponse = await SendPrompt(requestedItem, "clothes");
            string formattedResponse = ExtractResponse(storeResponse);
            Debug.Log("Resposta da Loja: " + formattedResponse);
        }
    }

    // Busca um objeto do tipo Store com o ID correspondente
    protected Store FindStore(string storeID)
    {
        Store[] stores = Object.FindObjectsByType<Store>(FindObjectsSortMode.None);
        foreach (Store store in stores)
        {
            if (store.StoreId == storeID)
            {
                return store;
            }
        }
        return null;
    }
}




