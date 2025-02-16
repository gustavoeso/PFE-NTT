using UnityEngine;
using UnityEngine.AI;

public class Client : Agent
{
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
            navMeshAgent.isStopped = false; // Continua o movimento
            navMeshAgent.SetDestination(targetStore.transform.position);
            if (!navMeshAgent.pathPending && navMeshAgent.remainingDistance <= navMeshAgent.stoppingDistance)
            {
                navMeshAgent.isStopped = true; // Para o movimento ao chegar na loja
                state = "arrived"; // Atualiza o estado
                Debug.Log("Cliente chegou à loja: " + targetStore.GetComponent<Store>().storeID);
            }
        }
    }

}



