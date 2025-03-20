using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.Networking;

public class Client : Agent
{
    private string requestedItem = "Jogo de Tabuleiro Monopoly";
    private Rigidbody rb;
    private Vector3 moveDirection;
    public float speed = 2.0f;
    public bool canCollide = true;

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
        Debug.Log("Iniciando conversa com: " + dialoguePartner);
        canCollide = false;

        if (isRequestInProgress)
        {
            return;
        }

        if (dialoguePartner == "Guide")
        {   
            string initialPrompt = "Inicie o diálogo com um guia do shopping buscando pelo seguinte produto " + requestedItem;
            string clientResponse = await SendPrompt(initialPrompt, "guide", "client");
            string formattedResponse = ExtractResponse(clientResponse);
            Dialogue.Instance.InitializeDialogue("client", "guide");
            Dialogue.Instance.StartDialogue(formattedResponse, true);
            Debug.Log("Pergunta do cliente: " + formattedResponse);
            await TTSManager.Instance.SpeakAsync(formattedResponse, TTSManager.Instance.voiceClient);

            string sellerResponse = await SendPrompt(formattedResponse, "guide", "guide");
            formattedResponse = ExtractResponse(sellerResponse);
            Dialogue.Instance.StartDialogue(formattedResponse, false);
            Debug.Log("Resposta do vendedor: " + formattedResponse);
            await TTSManager.Instance.SpeakAsync(formattedResponse, TTSManager.Instance.voiceGuide);
            Dialogue.Instance.CloseDialogue();

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
        if (dialoguePartner == "Store")
        {
            string initialPrompt = "{Você ja chegou na loja especificada, agora dirija uma pergunta para iniciar o dialogo com o atendente pedindo pelo produto} " + requestedItem;
            string clientResponse = await SendPrompt(initialPrompt, "store", "client");
            string formattedResponse = ExtractResponse(clientResponse);
            Dialogue.Instance.InitializeDialogue("client", "seller");
            Dialogue.Instance.StartDialogue(formattedResponse, true);
            Debug.Log("Pergunta do cliente: " + formattedResponse);
            await TTSManager.Instance.SpeakAsync(formattedResponse, TTSManager.Instance.voiceClient);

            string sellerResponse = await SendPrompt(formattedResponse, "store", "store");
            formattedResponse = ExtractResponse(sellerResponse);
            Dialogue.Instance.StartDialogue(formattedResponse, false);
            Debug.Log("Resposta do vendedor: " + formattedResponse);
            await TTSManager.Instance.SpeakAsync(formattedResponse, TTSManager.Instance.voiceGuide);

            clientResponse = await SendPrompt("Pergunte ao usúario se ele deve ou não aceitar a oferta", "client", "client");
            formattedResponse = ExtractResponse(clientResponse);
            bool userDecision = await PurchaseDecisionUI.Instance.GetUserDecisionAsync(formattedResponse);

            if (userDecision)
            {
                clientResponse = await SendPrompt("Aceite a oferta do vendedor e se despeça", "store", "client");
                formattedResponse = ExtractResponse(clientResponse);
            }
            else
            {
                clientResponse = await SendPrompt("Negue a oferta do vendedor e se despeça", "store", "client");
                formattedResponse = ExtractResponse(clientResponse);
            }
            Dialogue.Instance.StartDialogue(formattedResponse, true);
            await TTSManager.Instance.SpeakAsync(formattedResponse, TTSManager.Instance.voiceClient);
            Dialogue.Instance.CloseDialogue();

            Exit targetExit = FindExit();
            Vector3 exitPosition = targetExit.transform.position;

            navMeshAgent.isStopped = false;
            navMeshAgent.speed = speed;
            navMeshAgent.SetDestination(exitPosition);

            if (navMeshAgent.remainingDistance <= navMeshAgent.stoppingDistance + 0.1f)
            {
                StopImmediately();
            }
        }

        canCollide = true;
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

    protected Exit FindExit()
    {
        Exit[] exits = Object.FindObjectsByType<Exit>(FindObjectsSortMode.None);
        foreach (Exit exit in exits)
        {
            return exit;
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




