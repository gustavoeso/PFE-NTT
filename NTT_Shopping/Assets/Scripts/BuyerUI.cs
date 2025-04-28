using UnityEngine;
using UnityEngine.UI;
using System.Globalization;
using TMPro;
using System.Threading.Tasks; // Se estiver usando TextMesh Pro

public class BuyerUI : MonoBehaviour
{
    public TMP_InputField itemDesejadoInput;
    public TMP_InputField precoMaximoInput;
    public Button confirmarButton;
    public Client client;
    public GameObject inputPanel; 

    public void OnClickWrapper()
    {
        _ = OnConfirmButtonClicked(); // Ignora o Task, como o Unity espera void
    }

    public async Task OnConfirmButtonClicked()
    {
        
        // 1) Ler o texto dos campos
        string item = itemDesejadoInput.text;
        Client[] clients = Object.FindObjectsByType<Client>(FindObjectsSortMode.None);
        if (clients.Length == 0) {
            Debug.LogError("Client component not found in the scene.");
            return;
        }
        else if (clients.Length > 1) {
            Debug.LogError("Multiple Client components found in the scene. Please ensure only one is present.");
            return;
        }
        else if (clients[0] == null)
        {
            Debug.LogError("Client component not found on this GameObject.");
            return;
        }
        else {
            clients[0].requestedItem = item;
        }

        float precoMaximo;
        if (!float.TryParse(precoMaximoInput.text, NumberStyles.Any, CultureInfo.InvariantCulture, out precoMaximo))
        {
            precoMaximo = 0f;
        }

        // 2) Passar para o Client (ou fazer o que precisar)
        Debug.Log("(ClienteUI) Enviando dados para o Client...");
        await client.SetDesiredPurchase(item, precoMaximo);

        // 3) Sinalizar ao Client para iniciar a movimentação
        client.BeginMovement();
        
        Debug.Log($"(BuyerUI) Produto={item}, Preço Máximo={precoMaximo}");
        
        // 4) Limpar os campos de texto
        inputPanel.SetActive(false);
    }
    
}
