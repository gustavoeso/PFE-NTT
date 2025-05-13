using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.Networking;
using System.Text.RegularExpressions;
using System.Collections;
using System.Collections.Generic; // Se precisar de listas
using System.Text;

public class Client : MonoBehaviour
{

    // Core
    private Rigidbody rb;
    private NativeWSClient websocketClient;
    protected UnityEngine.AI.NavMeshAgent navMeshAgent;
    protected Animator animator;
    protected string myAgentId;
    protected BuyerUI buyerUI;

    // Config Vars
    public float speed = 2.0f;
    public int maxStoreTurns = 3;

    // Global Vars
    public List<string> requestedItems = new List<string>();
    public List<float> maxPrices = new List<float>();
    private int currentItemIndex = 0;
    private GameObject target = null;
    string targetType = null;
    string tempString;

    // Flags
    private bool conversationInProgress = false;
    private bool finalOffer = false;
    protected bool isRequestInProgress = false;


    protected async void Start()
    {
        myAgentId = System.Guid.NewGuid().ToString().Substring(0, 8);

        animator = GetComponent<Animator>();
        navMeshAgent = GetComponent<UnityEngine.AI.NavMeshAgent>();
        rb = GetComponent<Rigidbody>();
        websocketClient = FindFirstObjectByType<NativeWSClient>();
        buyerUI = FindFirstObjectByType<BuyerUI>();

        while (!websocketClient.IsConnected)
        {
            await Task.Delay(100);
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

        buyerUI.InitializeUI();

        return;
    }

    public void StartSimulation()
    {
        findGuide();
        targetType = "Guide";
        BeginMovement();
        return;
    }

    public async Task StartConversation(string dialoguePartner)
    {
        Debug.Log("Starting Conversation with: " + dialoguePartner);

        if (conversationInProgress || targetType != dialoguePartner) return;
        conversationInProgress = true;

        StopMovement();
        
        if (dialoguePartner == "Guide")
        {
            tempString = "Estou procurando o produto: " + requestedItems[currentItemIndex];
            Dialogue.Instance.InitializeDialogue("client", "guide");
            await Dialogue.Instance.StartDialogue(tempString, true);
            await TTSManager.Instance.SpeakAsync(tempString, TTSManager.Instance.voiceClient);
            tempString = await websocketClient.SendMessageToGuide(tempString);

            AgentResponse response = JsonUtility.FromJson<AgentResponse>(tempString);
            tempString = response.answer;
            await Dialogue.Instance.StartDialogue(tempString, false);
            await TTSManager.Instance.SpeakAsync(tempString, TTSManager.Instance.voiceGuide);
            Dialogue.Instance.CloseDialogue();

            FindStore(ExtractStoreNumber(tempString));
            targetType = "Store";
            BeginMovement();
        }

        else if (dialoguePartner == "Store")
        {
            await RunStoreConversationLoop();

            currentItemIndex++;
            if (currentItemIndex < requestedItems.Count)
            {
                targetType = "Guide";
                findGuide();
                BeginMovement();
            }
            else
            {
                GoToExit();
            }
        }

        conversationInProgress = false;
        Debug.Log("Conversation Ended");
    }

    private async Task RunStoreConversationLoop()
    {
        Dialogue.Instance.InitializeDialogue("client", "seller");
        tempString = $"Olá, quero comprar o produto {requestedItems[currentItemIndex]}";

        for (int turn = 0; turn < maxStoreTurns; turn++)
        {
            Debug.Log($"[Client] Turno {turn + 1} de {maxStoreTurns}");

            Debug.Log($"[Buyer -> Store] {tempString}");
            await Dialogue.Instance.StartDialogue(tempString, true);
            await TTSManager.Instance.SpeakAsync(tempString, TTSManager.Instance.voiceClient);

            tempString = await websocketClient.SendMessageToStore(tempString);
            tempString = ExtractResponse(tempString);

            Debug.Log($"[Store -> Buyer] {tempString}");
            await Dialogue.Instance.StartDialogue(tempString, false);
            await TTSManager.Instance.SpeakAsync(tempString, TTSManager.Instance.voiceGuide);

            tempString = await websocketClient.SendMessageToBuyer(tempString);
            tempString = ExtractResponse(tempString);

            finalOffer = ExtractFinalOffer(tempString);

            if (finalOffer)
            {
                tempString = await websocketClient.RequestSummary(tempString);
                tempString = ExtractResponse(tempString);

                bool purchaseConfirmation = await PurchaseDecisionUI.Instance.GetUserDecisionAsync(tempString);

                if (purchaseConfirmation)
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
                return;
            }
        }

        tempString = "Estou a muito tempo aqui, perdi o interesse. Obrigado!";
        await Dialogue.Instance.StartDialogue(tempString, true);
        await TTSManager.Instance.SpeakAsync(tempString, TTSManager.Instance.voiceClient);

        Dialogue.Instance.CloseDialogue();
    }

    private void GoToExit()
    {
        FindExit();
        BeginMovement();
    }

    private void findGuide()
    {
        GameObject guide = GameObject.FindGameObjectWithTag("Guide");
        target = guide;
    }

    public void BeginMovement()
    {   
        Debug.Log("Begin Movement to Target: " + target.name);
        navMeshAgent.isStopped = false;
        navMeshAgent.SetDestination(target.transform.position);
    }

    public void StopMovement()
    {
        navMeshAgent.isStopped = true;
        navMeshAgent.velocity = Vector3.zero;
    }

    protected void FindStore(string storeID)
    {   
        Store[] stores = Object.FindObjectsByType<Store>(FindObjectsSortMode.None);
        foreach (Store store in stores)
        {
            if (store.StoreId == storeID)
            {
                target = store.gameObject;
                return;
            }
        }
        GoToExit();
        Debug.LogError("Loja não encontrada com o ID: " + storeID);
    }

    protected void FindExit()
    {
        target = FindFirstObjectByType<Exit>().gameObject;
        return;
    }

    private string ExtractStoreNumber(string text)
    {   
        Debug.Log("Extracting Store Number From: " + text);
        var match = Regex.Match(text, @"n[uú]mero\s*=\s*(\d+)");
        if (match.Success)
        {
            return match.Groups[1].Value;
        }

        return Regex.Replace(text, @"[^\d]", "");
    }

    public async Task SetDesiredPurchase(List<string> desiredItems, List<float> prices)
    {

        requestedItems = desiredItems;
        maxPrices = prices;

        await websocketClient.SetBuyerPreferences(desiredItems, prices);
    }

    protected string ExtractResponse(string jsonResponse)
    {
        if (string.IsNullOrEmpty(jsonResponse))
        {
            return "Resposta vazia ou inválida";
        }

        try
        {
            AgentResponse data = JsonUtility.FromJson<AgentResponse>(jsonResponse);
            return data.answer ?? "Chave 'answer' não encontrada";
        }
        catch (System.Exception e)
        {
            Debug.LogError("Erro ao processar JSON: " + e.Message);
            return "Erro na formatação do JSON";
        }
    }

    protected bool ExtractFinalOffer(string jsonResponse)
    {
        if (string.IsNullOrEmpty(jsonResponse)) return false;

        try
        {
            AgentResponse data = JsonUtility.FromJson<AgentResponse>(jsonResponse);
            return data.final_offer;
        }
        catch
        {
            return false;
        }
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
