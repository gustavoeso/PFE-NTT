using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.UI;
using TMPro;
using System.Collections;

public class PurchaseDecisionUI : MonoBehaviour
{
    public static PurchaseDecisionUI Instance { get; private set; }
    public GameObject decisionPanel;
    public TextMeshProUGUI textDisplay;
    public Button yesButton;
    public Button noButton;
    public float typingSpeed = 0.05f;

    private TaskCompletionSource<bool> decisionTcs;

    private void Awake()
    {
        if (Instance == null)
        {
            Instance = this;
        }
        else
        {
            Destroy(gameObject);
        }

        decisionPanel.SetActive(false);
    }

    public Task<bool> GetUserDecisionAsync(string message)
    {
        decisionTcs = new TaskCompletionSource<bool>();
        decisionPanel.SetActive(true);
        StartDialogue(message);
        yesButton.onClick.AddListener(OnYesClicked);
        noButton.onClick.AddListener(OnNoClicked);

        return decisionTcs.Task;
    }

    private void OnYesClicked()
    {
        decisionTcs.TrySetResult(true);
        Cleanup();
    }

    private void OnNoClicked()
    {
        decisionTcs.TrySetResult(false);
        Cleanup();
    }

    private void Cleanup()
    {
        yesButton.onClick.RemoveListener(OnYesClicked);
        noButton.onClick.RemoveListener(OnNoClicked);
        decisionPanel.SetActive(false);
    }

    public void StartDialogue(string sentence)
    {
        textDisplay.text = "";
        textDisplay.pageToDisplay = 1;

        StartCoroutine(TypeLine(sentence));
    }

    private IEnumerator TypeLine(string sentence)
    {
        foreach (char letter in sentence.ToCharArray())
        {
            textDisplay.text += letter;
            textDisplay.ForceMeshUpdate();

            if (textDisplay.textInfo.pageCount > textDisplay.pageToDisplay)
            {
                textDisplay.pageToDisplay = textDisplay.textInfo.pageCount;
            }

            yield return new WaitForSeconds(typingSpeed);
        }
    }
}


