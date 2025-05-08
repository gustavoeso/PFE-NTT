using System.Collections;
using UnityEngine;

public class CarMovement : MonoBehaviour
{
    public Transform[] waypoints;
    public float speed = 5f;
    public float waitTime = 2f;

    public float rotationXOffset = -90f;
    public float rotationYOffset = 90f;

    private int currentWaypointIndex = 0;
    private bool isWaiting = false;

    void Update()
    {
        if (!isWaiting && waypoints.Length > 0)
        {
            MoveToWaypoint();
        }
    }

    void MoveToWaypoint()
    {
        Transform target = waypoints[currentWaypointIndex];
        Vector3 direction = (target.position - transform.position).normalized;
        transform.position += direction * speed * Time.deltaTime;

        if (direction != Vector3.zero)
        {
            Quaternion lookRotation = Quaternion.LookRotation(direction);
            transform.rotation = lookRotation * Quaternion.Euler(rotationXOffset, rotationYOffset, 0);
        }

        if (Vector3.Distance(transform.position, target.position) < 0.3f)
        {
            // Só espera se for um waypoint de índice par
            if (currentWaypointIndex % 2 == 0)
            {
                StartCoroutine(WaitAtWaypoint());
            }
            else
            {
                currentWaypointIndex = (currentWaypointIndex + 1) % waypoints.Length;
            }
        }
    }

    IEnumerator WaitAtWaypoint()
    {
        isWaiting = true;
        yield return new WaitForSeconds(waitTime);
        currentWaypointIndex = (currentWaypointIndex + 1) % waypoints.Length;
        isWaiting = false;
    }
}
