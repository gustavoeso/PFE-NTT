using UnityEngine;
using UnityEngine.UI;
using System.Globalization;
using System.Collections.Generic;

using TMPro;
using System.Threading.Tasks; // Se estiver usando TextMesh Pro

public class BuyerUI : MonoBehaviour
{
    public GameObject BuyerUIObject;
    public TMP_InputField itemDesejadoInput;
    public TMP_InputField precoMaximoInput;
    public Button confirmarButton;
    public Client client;

    public void OnClickWrapper()
    {
        _ = OnConfirmButtonClicked(); // Ignora o Task, como o Unity espera void
    }

    public void Start()
    {
        BuyerUIObject.SetActive(false);
    }

    public void InitializeUI()
    {
        BuyerUIObject.SetActive(true);
    }

    public void CloseUI()
    {
        BuyerUIObject.SetActive(false);
    }

    public async Task OnConfirmButtonClicked()
    {
        string rawProdutos = itemDesejadoInput.text;
        string rawPrecos = precoMaximoInput.text;

        string[] produtos = rawProdutos.Split(',');
        string[] precosStr = rawPrecos.Split(',');

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

        if (requestedItems.Count != maxPrices.Count)
        {
            Debug.LogError("Número de produtos e preços não coincidem após validação!");
            return;
        }

        Client client = Object.FindFirstObjectByType<Client>();

        await client.SetDesiredPurchase(requestedItems, maxPrices);
        client.StartSimulation();

        Debug.Log($"(BuyerUI) Produtos=[{string.Join(", ", requestedItems)}], Preços Máximos=[{string.Join(", ", maxPrices)}]");
        
        CloseUI();
    }

    
}
