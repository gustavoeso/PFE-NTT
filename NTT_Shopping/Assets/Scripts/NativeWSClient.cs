using UnityEngine;
using NativeWebSocket;
using System.Text;
using System.Threading.Tasks;
using System.Collections.Generic;
using System;

public class NativeWSClient : MonoBehaviour
{
    private WebSocket websocket;
    [SerializeField] private string agentId = "cliente_123";
    public bool IsConnected { get; private set; } = false;

    private Dictionary<string, TaskCompletionSource<string>> pendingResponses = new();

    async void Start()
    {
        string url = $"ws://localhost:8000/ws/{agentId}";
        websocket = new WebSocket(url);

        websocket.OnOpen += () =>
        {
            Debug.Log("Conectado ao servidor WebSocket!");
            IsConnected = true;
        };

        websocket.OnError += (e) =>
        {
            Debug.LogError("Erro no WebSocket: " + e);
        };

        websocket.OnClose += (e) =>
        {
            Debug.Log("Conexão encerrada!");
            IsConnected = false;
        };

        websocket.OnMessage += (bytes) =>
        {
            string message = Encoding.UTF8.GetString(bytes);
            Debug.Log("[Servidor] >> " + message);

            // Extrair request_id se houver
            if (message.Contains("\"request_id\""))
            {
                var response = JsonUtility.FromJson<WSResponse>(message);
                if (pendingResponses.TryGetValue(response.request_id, out var tcs))
                {
                    tcs.SetResult(message);
                    pendingResponses.Remove(response.request_id);
                }
            }
        };

        await websocket.Connect();
    }

    void Update()
    {
#if !UNITY_WEBGL || UNITY_EDITOR
        websocket?.DispatchMessageQueue();
#endif
    }

    async void OnApplicationQuit()
    {
        await websocket.Close();
    }

    private async Task<string> SendTextWithAnswer(string action, string conteudoJson = "")
    {
        string requestId = Guid.NewGuid().ToString();
        string json = $"{{\"action\": \"{action}\", \"request_id\": \"{requestId}\"{(conteudoJson != "" ? ", " + conteudoJson : "")}}}";
        Debug.Log("Enviando para WS: " + json);

        var tcs = new TaskCompletionSource<string>();
        pendingResponses[requestId] = tcs;
        
        await websocket.SendText(json);

        var timeout = Task.Delay(40000);
        var completed = await Task.WhenAny(tcs.Task, timeout);
        if (completed == timeout)
        {
            pendingResponses.Remove(requestId);
            throw new TimeoutException($"[WS] Timeout aguardando resposta com request_id={requestId}");
        }

        return await tcs.Task;
    }

    // === MÉTODOS ADAPTADOS ===

    public async Task SendStartMessage()
    {
        string json = "{\"action\": \"start\"}";
        Debug.Log("Enviando mensagem de início: " + json);
        await websocket.SendText(json);
    }

    public async Task SetBuyerPreferences(List<string> desired_items, List<float> prices)
    {
        string json = $"{{\"action\": \"setBuyerPreferences\", \"desired_item\": {JsonUtility.ToJson(new Wrapper<string> { list = desired_items })}, \"max_price\": {JsonUtility.ToJson(new Wrapper<float> { list = prices })}}}";
        Debug.Log("Enviando preferências: " + json);
        await websocket.SendText(json);
    }

    [System.Serializable]
    private class Wrapper<T>
    {
        public List<T> list;
    }


    // ✅ Com resposta
    public async Task<string> SendMessageToStore(string prompt)
    {
        string json = $"\"prompt\": \"{prompt}\"";
        return await SendTextWithAnswer("store_request", json);
    }

    public async Task<string> SendMessageToBuyer(string prompt)
    {
        string json = $"\"prompt\": \"{prompt}\"";
        return await SendTextWithAnswer("buyer_message", json);
    }

    public async Task<string> SendMessageToGuide(string prompt)
    {
        string json = $"\"prompt\": \"{prompt}\"";
        return await SendTextWithAnswer("guide_request", json);
    }

    public async Task<string> RequestSummary(string prompt)
    {
        string json = $"\"conversa\": \"{prompt}\"";
        return await SendTextWithAnswer("get_summary", json);
    }

    [Serializable]
    private class WSResponse
    {
        public string request_id;
        public string message;
    }
}







