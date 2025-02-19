using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.AI;

public class Client : Agent
{
    private string requestedItem = "Bicicleta";
    protected GameObject targetStore;
    protected override void Start()
    {
        base.Start();

        GameObject seller = GameObject.FindGameObjectWithTag("Seller");

        if (seller != null)
        {
            Vector3 sellerPosition = seller.transform.position;
            navMeshAgent.SetDestination(sellerPosition);
        }
    }

    public async Task StartConversation(string dialoguePartner)
    {
        await base.StartConversation(dialoguePartner);

        if (isRequestInProgress)
        {
            return;
        }

        if (dialoguePartner == "Seller")
        {
            string ClientResponse = await SendPrompt(requestedItem, "client");
            string formattedResponse = ExtractResponse(ClientResponse);
            Debug.Log("Pergunta do cliente: " + formattedResponse);

            string SellerResponse = await SendPrompt(formattedResponse, "seller");
            formattedResponse = ExtractResponse(SellerResponse);
            Debug.Log("Resposta do vendedor: " + formattedResponse);

            string FilteredStore = await SendPrompt(formattedResponse, "filter");
            formattedResponse = ExtractResponse(FilteredStore);

            Debug.Log("Loja filtrada: " + formattedResponse);
            navMeshAgent.isStopped = false;
            Store targetStore = FindStore(formattedResponse);
            navMeshAgent.SetDestination(targetStore.transform.position);
        } 
        else if (dialoguePartner == "store")
        {
            string storeResponse = await SendPrompt(requestedItem, "clothes");
            string formattedResponse = ExtractResponse(storeResponse);
            Debug.Log("Resposta da Loja: " + formattedResponse);
        }
    }
    protected Store FindStore(string storeID)
    {
        Store[] stores = FindObjectsByType<Store>(FindObjectsSortMode.None);
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



