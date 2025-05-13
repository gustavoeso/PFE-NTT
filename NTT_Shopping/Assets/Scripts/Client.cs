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

    public string requestedItem = "Produto X"; 
    public List<string> requestedItems = new List<string>();
    public List<float> maxPrices = new List<float>();
    private int currentItemIndex = 0;
    private TaskCompletionSource<bool> storeConversationFinishedTCS;


    private bool hasAskedGuide = false;
    private bool storeConversationInProgress = false;
    private bool finalOffer = false;
    private Store targetStore = null;
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
        float curSpeed = navMeshAgent.velocity.magnitude;
        animator.SetFloat("Speed", curSpeed);

        if (curSpeed > 0.1f)
        {
            Quaternion targetRotation = Quaternion.LookRotation(navMeshAgent.velocity.normalized);
            transform.rotation = Quaternion.Slerp(transform.rotation, targetRotation, Time.deltaTime * 10f);
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
            Debug.Log("Test Guide");
            Dialogue.Instance.InitializeDialogue("client", "guide");
            await Dialogue.Instance.StartDialogue(prompt, true);
            await TTSManager.Instance.SpeakAsync(prompt, TTSManager.Instance.voiceClient);

            string guideJson = await websocketClient.SendMessageToGuide(prompt);

            // (2) Extrai a resposta
            AgentResponse response = JsonUtility.FromJson<AgentResponse>(guideJson);
            string guideAnswer = response.answer;

            await Dialogue.Instance.StartDialogue(guideAnswer, false);
            await TTSManager.Instance.SpeakAsync(guideAnswer, TTSManager.Instance.voiceGuide);
            Dialogue.Instance.CloseDialogue();

            // (3) Extração de número da loja e movimentação
            string storeNumber = ExtractStoreNumber(guideAnswer);

            targetStore = FindStore(storeNumber);
            if (targetStore != null)
            {
                Vector3 storePosition = new Vector3(
                    targetStore.transform.position.x,
                    transform.position.y,
                    targetStore.transform.position.z
                );

                NavMeshHit hit;
                if (NavMesh.SamplePosition(storePosition, out hit, 2.0f, NavMesh.AllAreas))
                {
                    navMeshAgent.isStopped = false;
                    navMeshAgent.speed = speed;
                    navMeshAgent.SetDestination(hit.position);
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
            if (requestedItems[currentItemIndex + 1] != null)
            {
                Debug.Log("Going to next item");
                currentItemIndex++;
                requestedItem = requestedItems[currentItemIndex];
                GameObject guide = GameObject.FindGameObjectWithTag("Guide");
                if (guide != null && navMeshAgent != null)
                {
                    navMeshAgent.isStopped = false;
                    navMeshAgent.speed = speed;
                    navMeshAgent.SetDestination(guide.transform.position);
                    storeConversationInProgress = false;
                    canCollide = false;
                    hasAskedGuide = false;
                }
            }
            else
            {
                GoToExit();
            }
            storeConversationInProgress = false;
        }

        canCollide = true;
    }

    private async Task RunStoreConversationLoop()
    {
        int maxTurns = 6;

        string currentItem = requestedItems[currentItemIndex];
        string buyerMessage = $"Olá, quero comprar o produto {currentItem}";

        for (int turn = 0; turn < maxTurns; turn++)
        {
            Debug.Log($"[Client] Turno {turn + 1} de {maxTurns}");

            await Dialogue.Instance.StartDialogue(buyerMessage, true);
            await TTSManager.Instance.SpeakAsync(buyerMessage, TTSManager.Instance.voiceClient);

            // Buyer -> store
            Debug.Log($"[Buyer -> Store] {buyerMessage}");
            string storeJson = await websocketClient.SendMessageToStore(buyerMessage);
            Debug.Log($"[Client] JSON recebido da loja: {storeJson}");
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
                string resumoJson = await websocketClient.RequestSummary(storeMessage);
                string resumo = ExtractResponse(resumoJson);

                bool confirmada = await PurchaseDecisionUI.Instance.GetUserDecisionAsync(resumo);

                if (confirmada)
                {
                    await Dialogue.Instance.StartDialogue("Vou Levar o Produto. Muito Obrigado!", true);
                    await TTSManager.Instance.SpeakAsync("Vou Levar o Produto. Muito Obrigado!", TTSManager.Instance.voiceClient);
                }
                else
                {
                    await Dialogue.Instance.StartDialogue("Não vou levar o produto. Muito Obrigado!", true);
                    await TTSManager.Instance.SpeakAsync("Não vou levar o produto. Muito Obrigado!", TTSManager.Instance.voiceClient);
                }

                Dialogue.Instance.CloseDialogue();
                storeConversationFinishedTCS?.SetResult(true);
                return;
            }
        }
        string forcedDecision = "Estou a muito tempo aqui, perdi o interesse. Obrigado!";
        await Dialogue.Instance.StartDialogue(forcedDecision, true);
        await TTSManager.Instance.SpeakAsync(forcedDecision, TTSManager.Instance.voiceClient);

        Dialogue.Instance.CloseDialogue();
        storeConversationFinishedTCS?.SetResult(true);
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

    public void BeginMovement()
    {
        Debug.Log("[Client] BeginMovement chamado");
        navMeshAgent.isStopped = false;
        GameObject guide = GameObject.FindGameObjectWithTag("Guide");
        if (guide != null && navMeshAgent != null)
        {
            navMeshAgent.SetDestination(guide.transform.position);
        }
        requestedItem = requestedItems[currentItemIndex];
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
