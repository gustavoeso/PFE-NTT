using UnityEngine;
using TMPro;
using System.Collections;
using System.Collections.Generic;
using System.Threading.Tasks;


public class Dialogue : MonoBehaviour
{
    public static Dialogue Instance;

    [Header("Referência ao texto de diálogo")]
    public TextMeshProUGUI textDisplay;
    public TextMeshProUGUI leftName;
    public TextMeshProUGUI rightName;
    public float typingSpeed = 0.05f;

    [Header("Posições para personagens 3D")]
    public Transform leftCharacterSlot;
    public Transform rightCharacterSlot;

    [Header("Mapeamento de Personagens (ID -> Prefab)")]
    public CharacterMapping[] characterMappings;
    private Dictionary<string, GameObject> characterMap;
    private GameObject leftCharacterInstance;
    private GameObject rightCharacterInstance;


    private TaskCompletionSource<bool> dialogueFinishedTCS;

    private void Awake()
    {
        if (Instance == null)
            Instance = this;
        else
            Destroy(gameObject);

        characterMap = new Dictionary<string, GameObject>();
        foreach (CharacterMapping mapping in characterMappings)
        {
            if (!characterMap.ContainsKey(mapping.characterID))
                characterMap.Add(mapping.characterID, mapping.characterPrefab);
            else
                Debug.LogWarning($"ID duplicado: {mapping.characterID}");
        }

        gameObject.SetActive(false);
    }

    public void InitializeDialogue(string leftCharID, string rightCharID)
    {
        if (leftCharacterInstance != null)
            Destroy(leftCharacterInstance);
        if (rightCharacterInstance != null)
            Destroy(rightCharacterInstance);

        if (!string.IsNullOrEmpty(leftCharID) && characterMap.ContainsKey(leftCharID))
            leftCharacterInstance = Instantiate(characterMap[leftCharID], leftCharacterSlot);

        if (!string.IsNullOrEmpty(rightCharID) && characterMap.ContainsKey(rightCharID))
            rightCharacterInstance = Instantiate(characterMap[rightCharID], rightCharacterSlot);

        rightName.text = rightCharID;
        leftName.text = leftCharID;

        gameObject.SetActive(true);
    }

    public Task StartDialogue(string sentence, bool isLeftCharacterTalking)
    {
        textDisplay.text = "";
        textDisplay.pageToDisplay = 1;

        UpdateCharacterVisual(isLeftCharacterTalking);

        dialogueFinishedTCS = new TaskCompletionSource<bool>();
        StartCoroutine(TypeLine(sentence));
        return dialogueFinishedTCS.Task;
    }


    private void UpdateCharacterVisual(bool isLeftCharacterTalking)
    {
        Color activeColor = Color.white;
        Color inactiveColor = Color.gray;

        void UpdateCharacter(GameObject character, bool isActive)
        {
            if (character == null)
                return;
            
            var renderer = character.GetComponentInChildren<Renderer>();
            if (renderer != null)
            {
                if (renderer.material.HasProperty("_Saturation"))
                {
                    renderer.material.SetFloat("_Saturation", isActive ? 1f : 0f);
                }
                else
                {
                    renderer.material.color = isActive ? activeColor : inactiveColor;
                }
            }
        }

        UpdateCharacter(leftCharacterInstance, isLeftCharacterTalking);
        UpdateCharacter(rightCharacterInstance, !isLeftCharacterTalking);

        if (isLeftCharacterTalking)
        {
            leftName.color = activeColor;
            rightName.color = new Color(inactiveColor.r, inactiveColor.g, inactiveColor.b, 0.5f);
            rightName.fontStyle = TMPro.FontStyles.Normal;
            leftName.fontStyle = TMPro.FontStyles.Bold;
        }
        else
        {
            rightName.color = activeColor;
            leftName.color = new Color(inactiveColor.r, inactiveColor.g, inactiveColor.b, 0.5f);
            rightName.fontStyle = TMPro.FontStyles.Bold;
            leftName.fontStyle = TMPro.FontStyles.Normal;
        }
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

        dialogueFinishedTCS?.TrySetResult(true);
    }


    public void CloseDialogue()
    {
        if (leftCharacterInstance != null)
            Destroy(leftCharacterInstance);
        if (rightCharacterInstance != null)
            Destroy(rightCharacterInstance);

        gameObject.SetActive(false);
    }
}




