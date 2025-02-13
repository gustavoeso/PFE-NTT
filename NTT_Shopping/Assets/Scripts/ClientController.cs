using UnityEngine;
using UnityEngine.AI;

public class Client : Agent
{
    public string store; // Nome/ID da loja que o cliente deve visitar
    private GameObject targetStore; // Referência à loja de destino
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

    protected override void Update()
    {
        base.Update();

        if (state == "searchingStore" && targetStore != null)
        {
            // Verifica se chegou ao destino
            if (!navMeshAgent.pathPending && navMeshAgent.remainingDistance <= navMeshAgent.stoppingDistance)
            {
                navMeshAgent.isStopped = true; // Para o movimento ao chegar na loja
                state = "arrived"; // Atualiza o estado
                Debug.Log("Cliente chegou à loja: " + store);
            }
        }
    }

    // 🔹 Procura pela loja correta baseado na variável `store`
    private GameObject FindClosestStore()
    {
        GameObject[] stores = GameObject.FindGameObjectsWithTag("Store");

        foreach (GameObject storeObject in stores)
        {
            Store storeComponent = storeObject.GetComponent<Store>(); // Supondo que há um script Store
            if (storeComponent != null && storeComponent.ID == store)
            {
                return storeObject; // Retorna a loja correta
            }
        }

        return null; // Retorna nulo se não encontrar nenhuma loja com o ID correspondente
    }
}



