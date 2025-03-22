using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.Networking;

public class Client : Agent
{
    private Rigidbody rb;
    public float speed = 2.0f;
    public bool canCollide = true;

    // The item we want
    private string requestedItem = "Camiseta branca";

    // Booleans to ensure we do things once
    private bool hasAskedGuide    = false;
    private bool onWayToStore     = false;
    private bool hasTalkedToStore = false;

    // Store reference
    private Store targetStore = null;

    protected override async void Start()
    {
        base.Start();
        rb = GetComponent<Rigidbody>();

        // 1) Call /startApplication to initialize server
        await CallStartApplication();

        // 2) (Optional) Move near the guide so we can trigger OnTriggerEnter in Guide
        GameObject guide = GameObject.FindGameObjectWithTag("Guide");
        if (guide != null && navMeshAgent != null)
        {
            navMeshAgent.isStopped = false;
            navMeshAgent.speed = speed;
            navMeshAgent.SetDestination(guide.transform.position);
        }
    }

    void Update()
    {
        float curSpeed = navMeshAgent.velocity.magnitude;
        animator.SetFloat("Speed", curSpeed);

        if (curSpeed > 0.1f)
        {
            Quaternion targetRotation = Quaternion.LookRotation(navMeshAgent.velocity.normalized);
            transform.rotation = Quaternion.Slerp(transform.rotation, targetRotation, Time.deltaTime * 10f);
        }

        // If we're on the way to the store, check if we've arrived
        if (onWayToStore && targetStore != null && !hasTalkedToStore)
        {
            float distance = Vector3.Distance(transform.position, targetStore.transform.position);
            if (distance < 1.5f)  // "Close enough" threshold
            {
                onWayToStore = false;
                hasTalkedToStore = true;
                // Start the store conversation automatically
                _ = StartConversation("Store");
            }
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

        if (isRequestInProgress) return; // Already making a request

        if (dialoguePartner == "Guide")
        {
            // Only do this once
            if (hasAskedGuide)
            {
                Debug.Log("[Client] Já falei com o Guide. Ignorando.");
                return;
            }
            hasAskedGuide = true;

            Debug.Log($"[Client] Asking Guide about item '{requestedItem}'");

            // 1) Ask the "guide" for the store number / position
            string prompt         = "Estou procurando o produto: " + requestedItem;
            string guideJson      = await SendPrompt(prompt, "guide", "client");
            string guideAnswer    = ExtractResponse(guideJson);

            Debug.Log("[Client] Guide responded => " + guideAnswer);

            // Let’s parse the store number from the text
            string storeNumber = ExtractFirstNumber(guideAnswer);
            Debug.Log("[Client] Store number extracted => " + storeNumber);

            // Move to that store if it exists in the scene
            targetStore = FindStore(storeNumber);
            if (targetStore != null)
            {
                Vector3 storePosition = targetStore.transform.position;
                navMeshAgent.isStopped = false;
                navMeshAgent.speed = speed;
                navMeshAgent.SetDestination(storePosition);
                onWayToStore = true;
            }
            else
            {
                Debug.LogWarning("Loja não encontrada no Unity scene para o ID: " + storeNumber);
            }
        }
        else if (dialoguePartner == "Store")
        {
            Debug.Log("[Client] Starting multi-turn conversation with the Store.");

<<<<<<< HEAD
            // 1) We do the turn-based loop
            await RunStoreConversationLoop();
=======
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
>>>>>>> 0149944923e8477417c7a2ff25f7a6a028ea750f

            // 2) After the loop finishes (buyer decided or we hit max turns),
            //    let's walk to the exit
            Exit targetExit = FindExit();
            if (targetExit != null)
            {
                Debug.Log("[Client] Conversation ended => going to exit");
                Vector3 exitPosition = targetExit.transform.position;
                navMeshAgent.isStopped = false;
                navMeshAgent.speed = speed;
                navMeshAgent.SetDestination(exitPosition);
            }
            else
            {
                Debug.Log("[Client] Nenhuma saída encontrada na cena.");
            }
        }

        canCollide = true;
    }

    /// <summary>
    /// Run a mini turn-based conversation: store -> buyer -> store -> buyer...
    /// Stop early if buyer says "vou levar" or "não vou levar".
    /// Or end if we exceed maxTurns.
    /// </summary>
    private async Task RunStoreConversationLoop()
    {
        int maxTurns = 6;

        // The buyer's last message (we start the store conversation with a greeting)
        string buyerMessage = $"Olá, quero comprar o produto {requestedItem}";
        string storeMessage = "";

        for (int turn = 0; turn < maxTurns; turn++)
        {
            // --- SELLER (STORE) TURN ---
            Debug.Log($"[STORE TURN] Sending buyer message => {buyerMessage}");
            string storeJson = await SendPrompt(buyerMessage, "store", "client");
            storeMessage = ExtractResponse(storeJson);
            Debug.Log($"[STORE TURN] Store responded => {storeMessage}");

            // --- BUYER TURN ---
            Debug.Log($"[BUYER TURN] Sending store message => {storeMessage}");
            string buyerJson = await SendPrompt(storeMessage, "client", "seller");
            buyerMessage = ExtractResponse(buyerJson);
            Debug.Log($"[BUYER TURN] Buyer responded => {buyerMessage}");

            // Check if buyer made a final decision
            if (BuyerHasDecided(buyerMessage))
            {
                Debug.Log($"[BUYER TURN] Buyer made a final decision => {buyerMessage}");
                return;
            }
        }

        Debug.Log($"[RunStoreConversationLoop] Max {maxTurns} turns reached. Ending conversation anyway.");
    }

    private bool BuyerHasDecided(string text)
    {
        // Lowercase, remove punctuation
        string check = text.ToLower().Replace(".", "").Replace("!", "").Replace("?", "");
        if (check.Contains("vou levar") || check.Contains("não vou levar") || check.Contains("nao vou levar"))
        {
            return true;
        }
        return false;
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
        if (exits.Length > 0)
        {
            return exits[0];
        }
        return null;
    }

    private string ExtractFirstNumber(string text)
    {
        foreach (char c in text)
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
