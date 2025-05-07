using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.Networking;
using System.Text.RegularExpressions;
using System.Collections;   // Necessário para IEnumerator
using System.Collections.Generic; // Se precisar de listas
using System.Text;          // Necessário para Encoding

public class Client : Agent
{
    public bool canCollide = true;

    private Rigidbody rb;
    public float speed = 2.0f;

    public string requestedItem = "";  // Com o codigo novo, n precisa mais disso, mas vou deixar
    public List<string> requestedItems = new List<string>();
    public List<float> maxPrices = new List<float>();
    private int currentItemIndex = 0;
    private TaskCompletionSource<bool> storeConversationFinishedTCS;


    private bool hasAskedGuide = false;
    private bool onWayToStore = false;
    private bool hasTalkedToStore = false;
    private bool storeConversationInProgress = false;
    private bool isLeavingStore = false;
    private bool finalOffer = false;
    private Store targetStore = null;
    public bool startMovement = false;
    private NativeWSClient websocketClient;

    protected override async void Start()
    {
        base.Start();
        rb = GetComponent<Rigidbody>();
        rb.isKinematic = true;

        websocketClient = FindFirstObjectByType<NativeWSClient>();

        // Espera até o websocket estar conectado
        while (!websocketClient.IsConnected)
        {
            await Task.Delay(100); // espera 100ms
        }

        await CallStartApplication();
    }

    void Update()
    {
        if (!startMovement)
        {
            // Se não pode se mover, garantir que navMeshAgent.isStopped = true;
            navMeshAgent.isStopped = true;
            return;
        }

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
        await websocketClient.SendStartMessage();
        return;
    }

    public override async Task StartConversation(string dialoguePartner)
    {
        await StartConversation(dialoguePartner, requestedItems[currentItemIndex]);
    }
    public async Task StartConversation(string dialoguePartner, string itemName = "")
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

            string prompt = "Estou procurando o produto: " + itemName;

            Dialogue.Instance.InitializeDialogue("client", "guide");
            await Dialogue.Instance.StartDialogue(prompt, true);
            await TTSManager.Instance.SpeakAsync(prompt, TTSManager.Instance.voiceClient);

            // (1) Envia via WebSocket com ação "guide_request"
            string guideJson = await websocketClient.SendMessageToGuide(prompt);
            Debug.Log("[Client] JSON recebido do guia: " + guideJson);

            // (2) Extrai a resposta
            AgentResponse response = JsonUtility.FromJson<AgentResponse>(guideJson);
            string guideAnswer = response.answer;
            Debug.Log("[Client] guideAnswer=" + guideAnswer);

            await Dialogue.Instance.StartDialogue(guideAnswer, false);
            await TTSManager.Instance.SpeakAsync(guideAnswer, TTSManager.Instance.voiceGuide);
            Dialogue.Instance.CloseDialogue();

            // (3) Extração de número da loja e movimentação
            string storeNumber = ExtractStoreNumber(guideAnswer);
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
            storeConversationFinishedTCS = new TaskCompletionSource<bool>();
            await RunStoreConversationLoop();
            await storeConversationFinishedTCS.Task;
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

        string currentItem = requestedItems[currentItemIndex];
        string buyerMessage = $"Olá, quero comprar o produto {currentItem}";

        for (int turn = 0; turn < maxTurns; turn++)
        {
            Debug.Log($"[Client] Turno {turn + 1} de {maxTurns}");

            await Dialogue.Instance.StartDialogue(buyerMessage, true);
            await TTSManager.Instance.SpeakAsync(buyerMessage, TTSManager.Instance.voiceClient);

            // Buyer -> store
            string storeJson = await websocketClient.SendMessageToStore(buyerMessage);
            string storeMessage = ExtractResponse(storeJson);
            Debug.Log($"[Store -> Buyer] {storeMessage}");

            await Dialogue.Instance.StartDialogue(storeMessage, false);
            await TTSManager.Instance.SpeakAsync(storeMessage, TTSManager.Instance.voiceGuide);

            // Then store -> buyer
            string buyerJson = await websocketClient.SendMessageToBuyer(storeMessage);
            buyerMessage = ExtractResponse(buyerJson);
            finalOffer = ExtractFinalOffer(buyerJson);

            if (finalOffer)
            {
                Debug.Log($"[Buyer] Decisão detectada: {buyerMessage}");

                string resumoJson = await websocketClient.RequestSummary(storeMessage);
                string resumo = ExtractResponse(resumoJson);

                bool confirmada = await PurchaseDecisionUI.Instance.GetUserDecisionAsync(resumo);

                if (confirmada)
                {
                    Debug.Log("[Humano] Confirmou a decisão.");
                    await Dialogue.Instance.StartDialogue("Vou Levar o Produto. Muito Obrigado!", true);
                    await TTSManager.Instance.SpeakAsync("Vou Levar o Produto. Muito Obrigado!", TTSManager.Instance.voiceClient);
                }
                else
                {
                    Debug.Log("[Humano] Recusou a decisão.");
                    await Dialogue.Instance.StartDialogue("Não vou levar o produto. Muito Obrigado!", true);
                    await TTSManager.Instance.SpeakAsync("Não vou levar o produto. Muito Obrigado!", TTSManager.Instance.voiceClient);
                }

                Dialogue.Instance.CloseDialogue();
                storeConversationFinishedTCS?.SetResult(true);
                return;
            }
        }

        Debug.LogWarning("[Client] Conversa atingiu o limite de turnos sem decisão. Forçando decisão...");

        string forcedDecision = "Estou a muito tempo aqui, perdi o interesse. Obrigado!";
        await Dialogue.Instance.StartDialogue(forcedDecision, true);
        await TTSManager.Instance.SpeakAsync(forcedDecision, TTSManager.Instance.voiceClient);

        Dialogue.Instance.CloseDialogue();
        storeConversationFinishedTCS?.SetResult(true);
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

    // (3) Extract store number from text like "número=100"
    private string ExtractStoreNumber(string text)
    {
        // Match e.g. "número=100" or "numero=105"
        var match = Regex.Match(text, @"n[uú]mero\s*=\s*(\d+)");
        if (match.Success)
        {
            return match.Groups[1].Value; // e.g. "100"
        }

        // If not matched, fallback to digits only (but might cause confusion if multiple numbers).
        return Regex.Replace(text, @"[^\d]", "");
    }

    public void StopImmediately()
    {
        navMeshAgent.isStopped = true;
        navMeshAgent.velocity = Vector3.zero;
    }

    // Acho que essa função aqui ficou inutil
    public async Task SetDesiredPurchase(List<string> desiredItems, List<float> prices)
    {
        if (desiredItems.Count != prices.Count)
        {
            Debug.LogError("Quantidade de itens e preços não bate!");
            return;
        }

        requestedItems = desiredItems;
        maxPrices = prices;

        await websocketClient.SetBuyerPreferences(requestedItems, maxPrices);
    }

    private async Task ExecutePurchaseSequence()
    {
        Debug.Log("[Client] Iniciando sequência de compras...");
        for (int i = 0; i < requestedItems.Count; i++)
        {
            Debug.Log($"[Client] Rodada {i}: item={requestedItems[i]}");

            string item = requestedItems[i];
            float price = (i < maxPrices.Count) ? maxPrices[i] : 0f;

            Debug.Log($"[Client] Iniciando compra do item {i+1}/{requestedItems.Count}: '{item}' (R${price})");

            await websocketClient.SetBuyerPreferences(new List<string> { item }, new List<float> { price });

            currentItemIndex = i;

            hasAskedGuide = false;
            hasTalkedToStore = false;
            storeConversationInProgress = false;
            isLeavingStore = false;
            targetStore = null;

            // Falar com o Guia e obter loja
            GameObject guide = GameObject.FindGameObjectWithTag("Guide");
            if (guide != null && navMeshAgent != null)
            {
                Debug.Log("[Client] Indo até o Guia");
                navMeshAgent.SetDestination(guide.transform.position);
                await WaitUntilCloseTo(guide.transform.position);
                await StartConversation("Guide", item);
            }
            else
            {
                Debug.LogError("Guia com tag 'Guide' não encontrado na cena.");
            }

            // Esperar chegar na loja
            if (targetStore != null)
            {
                navMeshAgent.SetDestination(targetStore.transform.position);
                await WaitUntilCloseTo(targetStore.transform.position);
                await StartConversation("Store");
            }

            // Esperar um pouco antes do próximo
            await Task.Delay(1000);
        }

        Debug.Log("[Client] Compras finalizadas. Indo para a saída.");
        GoToExit();
    }

    private async Task WaitUntilCloseTo(Vector3 destination, float threshold = 1.5f)
    {
        int timeout = 0;

        while (Vector3.Distance(transform.position, destination) > threshold)
        {
            Debug.Log($"[Client] Esperando aproximação... Atual={transform.position}, Destino={destination}");

            if (timeout++ > 100) // ~20 segundos
            {
                Debug.LogWarning("[Client] Timeout ao tentar se aproximar!");
                break;
            }

            await Task.Delay(200);
        }

        navMeshAgent.ResetPath();
    }

    public void BeginMovement()
    {
        Debug.Log("[Client] BeginMovement chamado");
        startMovement = true;
        _ = ExecutePurchaseSequence();
    }


    [System.Serializable]
    public class PreferencesData
    {
        public string agent_id;
        public string desired_item;
        public float max_price;
    }

    [System.Serializable]
    public class AgentResponse
    {
        public string request_id;
        public string answer;
        public bool final_offer;
    }

}
