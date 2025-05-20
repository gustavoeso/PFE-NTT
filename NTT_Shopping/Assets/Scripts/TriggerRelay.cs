using UnityEngine;

public class TriggerRelay : MonoBehaviour
{
    public enum TriggerType { Small, Big }
    public TriggerType triggerType;
    private Agent parentAgent;

    private void Start()
    {
        parentAgent = GetComponentInParent<Agent>();
    }

    private void OnTriggerEnter(Collider other)
    {
        if (other.CompareTag("Client"))
        {
            parentAgent.OnTriggerEntered(triggerType, other);
        }
    }
}

