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
