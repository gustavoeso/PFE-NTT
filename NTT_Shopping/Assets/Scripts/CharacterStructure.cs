using System;
using UnityEngine;

// Classe auxiliar para expor no Inspector.
[Serializable]
public class CharacterMapping
{
    public string characterID;       // Ex.: "Guerreiro", "Mago", "Arqueiro"
    public GameObject characterPrefab;
}
