using UnityEngine;
using UnityEngine.AI;

public class Client : Agent
{
    protected override void Start()
    {
        // Chama o Start() da classe pai Agent
        base.Start();

        GameObject seller = GameObject.FindGameObjectWithTag("Seller");

        if (seller != null)
        {
            Vector3 sellerPosition = seller.transform.position;
            navMeshAgent.SetDestination(sellerPosition);
        }
    }
}



