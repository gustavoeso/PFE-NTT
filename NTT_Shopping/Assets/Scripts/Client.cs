using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.Networking;
using System.Text.RegularExpressions;

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

    private bool hasAskedGuide = false;
    private bool onWayToStore = false;
    private bool hasTalkedToStore = false;
    private bool storeConversationInProgress = false;
    private bool isLeavingStore = false;

    private Store targetStore = null;

    protected override async void Start()
    {
        base.Start();
        rb = GetComponent<Rigidbody>();
        rb.isKinematic = true;

        await CallStartApplication();

        GameObject guide = GameObject.FindGameObjectWithTag("Guide");
        if (guide != null && navMeshAgent != null)
        {
            navMeshAgent.isStopped = false;
            navMeshAgent.speed = speed;
            navMeshAgent.stoppingDistance = 1.2f;
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

        if (onWayToStore && targetStore != null && !hasTalkedToStore && !storeConversationInProgress && !isLeavingStore)
        {
            float distance = Vector3.Distance(transform.position, targetStore.transform.position);
            Debug.Log($"[Client] Distância atual até a loja: {distance:F2}");
            Debug.DrawLine(transform.position, targetStore.transform.position, Color.green);

            if (distance < 1.5f)
            {
                Debug.Log("[Client] Chegou perto da loja, iniciando conversa...");
                onWayToStore = false;
                hasTalkedToStore = true;
                navMeshAgent.ResetPath();
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
        if (dialoguePartner == "Store")
        {
            if (storeConversationInProgress) return;
            storeConversationInProgress = true;
        }

        // Permite a conversa com a loja mesmo que outra requisição esteja em andamento
        if (dialoguePartner != "Store" && isRequestInProgress) return;

        await base.StartConversation(dialoguePartner);

        canCollide = false;

        if (dialoguePartner == "Guide")
        {
            if (hasAskedGuide) return;
            hasAskedGuide = true;

            string prompt = "Estou procurando o produto: " + requestedItem;

            Dialogue.Instance.InitializeDialogue("client", "guide");
            Dialogue.Instance.StartDialogue(prompt, true);
            await TTSManager.Instance.SpeakAsync(prompt, TTSManager.Instance.voiceClient);

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
                Vector3 storePosition = new Vector3(
                    targetStore.transform.position.x,
                    transform.position.y,
                    targetStore.transform.position.z
                );

                NavMeshHit hit;
                if (NavMesh.SamplePosition(storePosition, out hit, 2.0f, NavMesh.AllAreas))
                {
                    Debug.Log($"[Client] Caminho válido para a loja! Indo para: {hit.position}");
                    navMeshAgent.isStopped = false;
                    navMeshAgent.speed = speed;
                    navMeshAgent.SetDestination(hit.position);
                    onWayToStore = true;

                    bool pathValid = navMeshAgent.CalculatePath(hit.position, new NavMeshPath());
                    Debug.Log($"[Client] Caminho gerado com sucesso? {pathValid}");
                }
                else
                {
                    Debug.LogWarning("[Client] Não foi possível encontrar uma posição válida na NavMesh próxima à loja.");
                }
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

        if (dialoguePartner == "Store")
        {
            storeConversationInProgress = false;
        }
    }

    private async Task RunStoreConversationLoop()
    {
        Debug.Log("[Client] Iniciando conversa com a loja (RunStoreConversationLoop)");
        int maxTurns = 6;
        string buyerMessage = $"Olá, quero comprar o produto {requestedItem}";

        for (int turn = 0; turn < maxTurns; turn++)
        {
            Debug.Log($"[Client] Turno {turn + 1} de {maxTurns}");

            Dialogue.Instance.StartDialogue(buyerMessage, true);
            await TTSManager.Instance.SpeakAsync(buyerMessage, TTSManager.Instance.voiceClient);

            if (BuyerHasDecided(buyerMessage))
            {
                Debug.Log($"[Buyer] Decisão final (antes da loja responder): {buyerMessage}");
                Dialogue.Instance.CloseDialogue();
                GoToExit();
                return;
            }

            string storeJson = await SendPrompt(buyerMessage, "store", "client");
            string storeMessage = ExtractResponse(storeJson);
            Debug.Log($"[Store -> Buyer] {storeMessage}");

            Dialogue.Instance.StartDialogue(storeMessage, false);
            await TTSManager.Instance.SpeakAsync(storeMessage, TTSManager.Instance.voiceGuide);

            string buyerJson = await SendPrompt(storeMessage, "client", "seller");
            buyerMessage = ExtractResponse(buyerJson);
            Debug.Log($"[Buyer -> Store] {buyerMessage}");

            if (BuyerHasDecided(buyerMessage))
            {
                Debug.Log($"[Buyer] Decisão final (após resposta da loja): {buyerMessage}");
                Dialogue.Instance.CloseDialogue();
                GoToExit();
                return;
            }
        }

        Debug.LogWarning("[Client] Conversa atingiu o limite de turnos sem decisão. Forçando decisão...");

        string forcedDecision = "Vou levar";
        Dialogue.Instance.StartDialogue(forcedDecision, true);
        await TTSManager.Instance.SpeakAsync(forcedDecision, TTSManager.Instance.voiceClient);

        Dialogue.Instance.CloseDialogue();
        GoToExit();
    }

    private void GoToExit()
    {
        isLeavingStore = true;
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
