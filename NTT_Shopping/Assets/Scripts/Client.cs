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
    public string requestedItem = "";
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
                    await TTSManager.Instance.SpeakAsync("Não Vou Levar o Produto. Muito Obrigado!", TTSManager.Instance.voiceGuide);
                    Dialogue.Instance.CloseDialogue();
                    GoToExit();
                }
                else
                {
                    Debug.Log("[Humano] Recusou a decisão.");
                    await Dialogue.Instance.StartDialogue("Não vou levar o produto. Muito Obrigado!", true);
                    await TTSManager.Instance.SpeakAsync("Não Vou Levar o Produto. Muito Obrigado!", TTSManager.Instance.voiceGuide);
                    Dialogue.Instance.CloseDialogue();
                    GoToExit();
                }

                return;
            }
        }

        Debug.LogWarning("[Client] Conversa atingiu o limite de turnos sem decisão. Forçando decisão...");

        string forcedDecision = "Estou a muito tempo aqui, perdi o interesse. Obrigado!";
        await Dialogue.Instance.StartDialogue(forcedDecision, true);
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

    public async Task SetDesiredPurchase(string desiredItem, float maxPrice){
        await websocketClient.SetBuyerPreferences(desiredItem, maxPrice.ToString());
    }

    public void BeginMovement(){
        // Agora sim, definimos que pode começar a andar
        startMovement = true;
        
        // Se quiser imediatamente mandar o comprador falar com o Guia:
        GameObject guide = GameObject.FindGameObjectWithTag("Guide");
        if (guide != null && navMeshAgent != null)
        {
            navMeshAgent.isStopped = false;
            navMeshAgent.speed = speed;
            navMeshAgent.stoppingDistance = 1.2f;
            navMeshAgent.SetDestination(guide.transform.position);
        }

        Debug.Log("[Client] Movimentação iniciada (BeginMovement)");
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
