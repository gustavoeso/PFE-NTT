using UnityEngine;
using NativeWebSocket;
using System.Text;
using System.Threading.Tasks;

public class NativeWSClient : MonoBehaviour
{
    private WebSocket websocket;

    [SerializeField] private string agentId = "cliente_123";

    async void Start()
    {
        string url = $"ws://localhost:8000/ws/{agentId}";
        websocket = new WebSocket(url);

        websocket.OnOpen += () =>
        {
            Debug.Log("Conectado ao servidor WebSocket!");
            SendStartMessage();
        };

        websocket.OnError += (e) =>
        {
            Debug.LogError("Erro no WebSocket: " + e);
        };

        websocket.OnClose += (e) =>
        {
            Debug.Log("Conexão encerrada!");
        };

        websocket.OnMessage += (bytes) =>
        {
            string message = Encoding.UTF8.GetString(bytes);
            Debug.Log($"[Servidor]: {message}");
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

    public async void SendStartMessage()
    {
        string json = "{\"action\": \"start\"}";
        await websocket.SendText(json);
    }

    public async void EnviarMensagemParaLoja(string prompt)
    {
        var json = $"{{\"action\": \"buyer_message\", \"prompt\": \"{prompt}\"}}";
        await websocket.SendText(json);
    }

    public async void SolicitarResumo()
    {
        var json = $"{{\"action\": \"get_summary\"}}";
        await websocket.SendText(json);
    }
}






