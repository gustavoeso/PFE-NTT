using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.Networking;

public class Client : Agent
{
    private string requestedItem = "Bicicleta";
    private Rigidbody rb;
    private Vector3 moveDirection;
    public float speed = 2.0f;

    protected override async void Start()
    {
        base.Start();
        rb = GetComponent<Rigidbody>();
        
        await CallStartApplication();

        GameObject guide = GameObject.FindGameObjectWithTag("Guide");
        if (guide != null)
        {
            Vector3 guidePosition = guide.transform.position;
            navMeshAgent.SetDestination(guidePosition);
        }
    }

    void Update()
    {
        float speed = navMeshAgent.velocity.magnitude;
        animator.SetFloat("Speed", speed);

        if (navMeshAgent.velocity.magnitude > 0.1f)
        {
            Quaternion targetRotation = Quaternion.LookRotation(navMeshAgent.velocity.normalized);
            transform.rotation = Quaternion.Slerp(transform.rotation, targetRotation, Time.deltaTime * 10f);
        }

    }

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
            string initialPrompt = "Inicie o diálogo com um guia do shopping buscando pelo seguinte produto " + requestedItem;
            string clientResponse = await SendPrompt(initialPrompt, "client", "client");
            string formattedResponse = ExtractResponse(clientResponse);
            Debug.Log("Pergunta do cliente: " + formattedResponse);

            string sellerResponse = await SendPrompt(formattedResponse, "guide", "client");
            formattedResponse = ExtractResponse(sellerResponse);
            Debug.Log("Resposta do vendedor: " + formattedResponse);

            string storeNumber = ExtractFirstNumber(formattedResponse);
            Debug.Log("Número da loja extraído: " + storeNumber);

            Store targetStore = FindStore(storeNumber);
            if (targetStore != null)
            {
                Vector3 storePosition = targetStore.transform.position;

                // **Garante que o agente não está parado antes de definir o destino**
                navMeshAgent.isStopped = false;
                navMeshAgent.speed = speed;
                navMeshAgent.SetDestination(storePosition);

                // **Adiciona uma pequena margem para evitar bloqueios**
                if (navMeshAgent.remainingDistance <= navMeshAgent.stoppingDistance + 0.1f)
                {
                    StopImmediately();
                }
            }
            else
            {
                Debug.LogError("Loja não encontrada para o ID: " + formattedResponse);
            }
        }
    }

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

    private string ExtractFirstNumber(string response)
    {
        foreach (char c in response)
        {
            if (char.IsDigit(c))
            {
                return c.ToString();
            }
        }
        return "";
    }

    public void StopImmediately()
    {
        navMeshAgent.isStopped = true;
        navMeshAgent.velocity = Vector3.zero;
    }
}




