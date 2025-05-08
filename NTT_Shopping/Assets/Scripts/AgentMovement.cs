using System.Collections;
using UnityEngine;

public class RandomNPCWalker : MonoBehaviour
{
    public Transform[] waypoints;
    public float speed = 2f;
    public float minWaitTime = 1f;
    public float maxWaitTime = 3f;
    [Range(0f, 1f)] public float chanceToReturnHome = 0.2f;

    private Vector3 initialPosition;
    private Quaternion initialRotation;
    private bool isWaiting = false;
    private Transform target;
    private bool isReturningHome = false;

    void Start()
    {
        initialPosition = transform.position;
        initialRotation = transform.rotation;
        ChooseNextDestination();
    }

    void Update()
    {
        if (isWaiting || target == null) return;

        Vector3 direction = (target.position - transform.position).normalized;
        transform.position += direction * speed * Time.deltaTime;

        if (direction != Vector3.zero)
        {
            Quaternion lookRotation = Quaternion.LookRotation(direction);
            transform.rotation = Quaternion.Lerp(transform.rotation, lookRotation, Time.deltaTime * 5f);
        }

        if (Vector3.Distance(transform.position, target.position) < 0.3f)
        {
            StartCoroutine(WaitThenMove());
        }
    }

    IEnumerator WaitThenMove()
    {
        isWaiting = true;
        float waitTime = Random.Range(minWaitTime, maxWaitTime);
        yield return new WaitForSeconds(waitTime);

        if (!isReturningHome && Random.value < chanceToReturnHome)
        {
            target = null;
            isReturningHome = true;
            target = CreateTemporaryTarget(initialPosition);
        }
        else
        {
            ChooseNextDestination();
        }

        isWaiting = false;
    }

    void ChooseNextDestination()
    {
        if (waypoints.Length == 0) return;
        int index = Random.Range(0, waypoints.Length);
        target = waypoints[index];
    }

    // Cria um objeto temporário no ponto inicial para servir de destino
    Transform CreateTemporaryTarget(Vector3 position)
    {
        GameObject temp = new GameObject("ReturnHomeTarget");
        temp.transform.position = position;
        StartCoroutine(DestroyAndReset(temp));
        return temp.transform;
    }

    // Destroi o target temporário e aplica rotação original
    IEnumerator DestroyAndReset(GameObject tempTarget)
    {
        // Espera até o NPC chegar lá
        while (Vector3.Distance(transform.position, tempTarget.transform.position) > 0.3f)
        {
            yield return null;
        }

        transform.rotation = initialRotation;
        Destroy(tempTarget);
        isReturningHome = false;
        yield return new WaitForSeconds(Random.Range(minWaitTime, maxWaitTime));
        ChooseNextDestination();
    }
}
