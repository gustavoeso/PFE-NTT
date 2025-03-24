using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.Networking;
using System.Text.RegularExpressions;

// A small helper class to map the JSON response from your Flask server.
// e.g. { "response": "some text" }
[System.Serializable]
public class ApiResponse
{
    public string response;
}

public class Client : Agent
{
    public bool canCollide = true;

    private Rigidbody rb;
    public float speed = 2.0f;
    private string requestedItem = "Camiseta branca";

    private bool hasAskedGuide    = false;
    private bool onWayToStore     = false;
    private bool hasTalkedToStore = false;
    private Store targetStore     = null;

    // Flag to prevent starting multiple "store" conversations at once
    private bool storeConversationInProgress = false;

    protected override async void Start()
    {
        base.Start();
        rb = GetComponent<Rigidbody>();
        await CallStartApplication();

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

        // Only check the distance and start conversation if:
        // - We are on the way to the store
        // - We haven't already talked to the store
        // - A store conversation is NOT already running
        if (onWayToStore && targetStore != null && !hasTalkedToStore && !storeConversationInProgress)
        {
            float distance = Vector3.Distance(transform.position, targetStore.transform.position);
            if (distance < 1.5f)
            {
                onWayToStore = false;
                hasTalkedToStore = true;
                // Call StartConversation("Store") exactly once
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
            while (!operation.isDone) await Task.Yield();

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
        // If about to start a Store conversation, ensure we don't do it twice
        if (dialoguePartner == "Store")
        {
            if (storeConversationInProgress) return;
            storeConversationInProgress = true;
        }

        // Call base (if your parent class does anything special)
        await base.StartConversation(dialoguePartner);

        if (isRequestInProgress) return;

        canCollide = false;

        if (dialoguePartner == "Guide")
        {
            if (hasAskedGuide) return;
            hasAskedGuide = true;

            string prompt = "Estou procurando o produto: " + requestedItem;

            Dialogue.Instance.InitializeDialogue("client", "guide");
            Dialogue.Instance.StartDialogue(prompt, true);
            await TTSManager.Instance.SpeakAsync(prompt, TTSManager.Instance.voiceClient);

            // Send prompt to your /request/guide endpoint
            string guideJson = await SendPrompt(prompt, "guide", "client");
            string guideAnswer = ExtractResponse(guideJson);

            Dialogue.Instance.StartDialogue(guideAnswer, false);
            await TTSManager.Instance.SpeakAsync(guideAnswer, TTSManager.Instance.voiceGuide);
            Dialogue.Instance.CloseDialogue();

            string storeNumber = ExtractFirstNumber(guideAnswer);
            Debug.Log("[Client] Número da loja extraído: " + storeNumber);

            targetStore = FindStore(storeNumber);
            if (targetStore != null)
            {
                Debug.Log("[Client] Loja encontrada na cena com ID: " + storeNumber);
                Vector3 storePosition = targetStore.transform.position;
                navMeshAgent.isStopped = false;
                navMeshAgent.speed = speed;
                navMeshAgent.SetDestination(storePosition);
                onWayToStore = true;
            }
            else
            {
                Debug.LogWarning("[Client] Loja NÃO encontrada na cena para o ID: " + storeNumber);
            }
        }
        else if (dialoguePartner == "Store")
        {
            Dialogue.Instance.InitializeDialogue("client", "seller");
            await RunStoreConversationLoop();
        }

        canCollide = true;

        // If that was the Store conversation, allow another in the future (if needed)
        if (dialoguePartner == "Store")
        {
            storeConversationInProgress = false;
        }
    }

    private async Task RunStoreConversationLoop()
    {
        int maxTurns = 6;

        // Buyer's initial line
        string buyerMessage = $"Olá, quero comprar o produto {requestedItem}";

        for (int turn = 0; turn < maxTurns; turn++)
        {
            // 1) Buyer speaks
            Dialogue.Instance.StartDialogue(buyerMessage, true);
            await TTSManager.Instance.SpeakAsync(buyerMessage, TTSManager.Instance.voiceClient);

            // 2) Check if the buyer decided
            if (BuyerHasDecided(buyerMessage))
            {
                Debug.Log($"[Buyer] Decisão final: {buyerMessage}");
                Dialogue.Instance.CloseDialogue();
                GoToExit();
                return;
            }

            // 3) Store responds
            string storeJson = await SendPrompt(buyerMessage, "store", "client");
            string storeMessage = ExtractResponse(storeJson);

            Dialogue.Instance.StartDialogue(storeMessage, false);
            await TTSManager.Instance.SpeakAsync(storeMessage, TTSManager.Instance.voiceGuide);

            // 4) Buyer responds to store
            string buyerJson = await SendPrompt(storeMessage, "client", "seller");
            buyerMessage = ExtractResponse(buyerJson);

            // 5) Check decision again
            if (BuyerHasDecided(buyerMessage))
            {
                Debug.Log($"[Buyer] Decisão final: {buyerMessage}");
                Dialogue.Instance.CloseDialogue();
                GoToExit();
                return;
            }
        }

        // If we reach max turns, end conversation anyway
        Debug.Log("[RunStoreConversationLoop] Conversa encerrada por limite de turnos.");
        Dialogue.Instance.CloseDialogue();
        GoToExit();
    }

    private void GoToExit()
    {
        Exit exitNow = FindExit();
        if (exitNow != null)
        {
            Vector3 exitPosition = exitNow.transform.position;
            navMeshAgent.isStopped = false;
            navMeshAgent.speed = speed;
            navMeshAgent.SetDestination(exitPosition);
        }
    }

    private bool BuyerHasDecided(string text)
    {
        // Lowercase and remove punctuation for easy matching
        string check = text.ToLower().Replace(".", "").Replace("!", "").Replace("?", "");
        return check.Contains("vou levar") || check.Contains("não vou levar") || check.Contains("nao vou levar");
    }

    protected Store FindStore(string storeID)
    {
        Store[] stores = Object.FindObjectsByType<Store>(FindObjectsSortMode.None);
        foreach (Store store in stores)
        {
            if (store.StoreId == storeID)
                return store;
        }
        return null;
    }

    protected Exit FindExit()
    {
        Exit[] exits = Object.FindObjectsByType<Exit>(FindObjectsSortMode.None);
        return exits.Length > 0 ? exits[0] : null;
    }

    private string ExtractFirstNumber(string text)
    {
        Match match = Regex.Match(text, @"\d+");
        return match.Success ? match.Value : "";
    }

    /// <summary>
    /// Extract the "response" field from the JSON that the Flask server returns.
    /// Since the server returns: { "response": "some text" },
    /// we can parse it with JsonUtility into our ApiResponse class.
    /// </summary>
    private string ExtractResponse(string json)
    {
        if (string.IsNullOrEmpty(json)) return "";
        ApiResponse respObject = JsonUtility.FromJson<ApiResponse>(json);
        if (respObject == null) return "";
        return respObject.response;
    }

    public void StopImmediately()
    {
        navMeshAgent.isStopped = true;
        navMeshAgent.velocity = Vector3.zero;
    }
}
