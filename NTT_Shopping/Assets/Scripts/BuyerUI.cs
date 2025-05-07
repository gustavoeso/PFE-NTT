using UnityEngine;
using UnityEngine.UI;
using System.Globalization;
using System.Collections.Generic;

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
        string rawProdutos = itemDesejadoInput.text;
        string rawPrecos = precoMaximoInput.text;

        string[] produtos = rawProdutos.Split(',');
        string[] precosStr = rawPrecos.Split(',');

        if (produtos.Length != precosStr.Length)
        {
            Debug.LogError("Número de produtos e preços não coincidem!");
            return;
        }

        List<string> requestedItems = new List<string>();
        List<float> maxPrices = new List<float>();

        for (int i = 0; i < produtos.Length; i++)
        {
            string produto = produtos[i].Trim();
            if (string.IsNullOrEmpty(produto))
            {
                Debug.LogWarning($"Produto vazio na posição {i}");
                continue;
            }

            if (!float.TryParse(precosStr[i].Trim(), NumberStyles.Any, CultureInfo.InvariantCulture, out float preco))
            {
                Debug.LogWarning($"Preço inválido para o produto '{produto}': '{precosStr[i]}'");
                continue;
            }

            requestedItems.Add(produto);
            maxPrices.Add(preco);
        }

        if (requestedItems.Count == 0)
        {
            Debug.LogWarning("Nenhum produto válido foi inserido.");
            return;
        }

        Client[] clients = Object.FindObjectsByType<Client>(FindObjectsSortMode.None);
        if (clients.Length != 1 || clients[0] == null)
        {
            Debug.LogError("Erro ao localizar instância única de Client.");
            return;
        }

        await clients[0].SetDesiredPurchase(requestedItems, maxPrices);
        clients[0].BeginMovement();

        Debug.Log($"(BuyerUI) Produtos=[{string.Join(", ", requestedItems)}], Preços Máximos=[{string.Join(", ", maxPrices)}]");
        inputPanel.SetActive(false);
    }

    
}
