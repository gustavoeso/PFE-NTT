import os
import time
import re
from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate
)
from langchain.memory import ConversationBufferMemory

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
TEMPERATURE = 0.3
MAX_TURNS = 20

MODELOS = {
    "gpt-4o": "gpt-4o",  # Usará OpenAI diretamente
    "gemini_2.0": "google/gemini-2.0-flash-001",
    "deepseek_v3": "deepseek/deepseek-chat-v3-0324",
    "claude_sonnet": "anthropic/claude-3.7-sonnet",
    "gemini_2.5": "google/gemini-2.5-flash-preview",
    "mistral_small_3": "mistralai/mistral-small-24b-instruct-2501"
}

def criar_chain(model_key, model_name, memory, prompt):
    if model_key == "gpt-4o":
        llm = ChatOpenAI(
            openai_api_key=OPENAI_API_KEY,
            model_name=model_name,
            temperature=TEMPERATURE
        )
    else:
        llm = ChatOpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
            model_name=model_name,
            temperature=TEMPERATURE
        )
    return LLMChain(
        llm=llm,
        prompt=prompt,
        memory=memory,
        verbose=False
    )

def criar_buyer_chain(model_key, model_name, memory):
    buyer_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template("""
            Você é o Buyer (comprador) em uma loja de roupas num shopping.
            Não se identifique como IA.

            Objetivo:
            - Você quer comprar uma camiseta branca ou não.
            - Você pode fazer até 3 perguntas.
            - Se decidir comprar, diga claramente algo como "vou levar essa", "vou levar", "decidi levar".
            - Se decidir não comprar, diga claramente algo como "não vou levar".
            - Evite respostas ambíguas.
            
            Histórico da conversa até agora:
            {history}
        """),
        HumanMessagePromptTemplate.from_template("""
            A última fala do Vendedor (Seller) foi:
            {seller_utterance}

            Agora responda como BUYER:
            1. Lembre-se que você só pode fazer até 3 perguntas.
            2. Se for decidir, diga algo claro como "vou levar" ou "não vou levar".
        """)
    ])
    return criar_chain(model_key, model_name, memory, buyer_prompt)

def criar_seller_chain(model_key, model_name, memory):
    seller_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template("""
            Você é o Seller (vendedor) em uma loja de roupas num shopping.
            Não se identifique como IA.

            Objetivo:
            - Vender roupas, responder perguntas do Buyer.
            - Não encerre a conversa por conta própria.

            Histórico da conversa até agora:
            {history}
        """),
        HumanMessagePromptTemplate.from_template("""
            A última fala do Comprador (Buyer) foi:
            {buyer_utterance}

            Agora responda como SELLER:
            1. Ofereça informações sobre as roupas, preços etc.
            2. Não se identifique como IA.
            3. Não encerre por conta própria.
        """)
    ])
    return criar_chain(model_key, model_name, memory, seller_prompt)

def should_stop_conversation(history_str: str) -> bool:
    """
    Verifica se o comprador tomou uma decisão clara de comprar ou não comprar.
    """
    patterns = [
        r"\b(vou levar|levarei|vou pegar)\b",
        r"\b(não vou levar|decidi não levar)\b",
        r"\b(levo essa|vou querer essa)\b",
        r"\b(só essa mesmo|essa está ótima vou levar)\b"
    ]

    for pattern in patterns:
        if re.search(pattern, history_str, flags=re.IGNORECASE):
            return True
    return False

def rodar_conversa_com_medicao(model_key, model_name):
    memory = ConversationBufferMemory(memory_key="history", return_messages=True)
    buyer_chain = criar_buyer_chain(model_key, model_name, memory)
    seller_chain = criar_seller_chain(model_key, model_name, memory)

    buyer_utterance = "Oi, estou procurando uma camiseta branca."
    memory.save_context({"input": "[BEGIN]"}, {"output": buyer_utterance})
    conversation_log = [("Buyer", buyer_utterance)]
    timing_log = []
    seller_utterance = ""

    turn = 2
    start_convo = time.time()

    while turn <= MAX_TURNS:
        start_turn = time.time()

        if turn % 2 == 0:
            seller_response = seller_chain.run({"buyer_utterance": buyer_utterance})
            memory.save_context({"input": buyer_utterance}, {"output": seller_response})
            conversation_log.append(("Seller", seller_response))
            seller_utterance = seller_response
        else:
            buyer_response = buyer_chain.run({"seller_utterance": seller_utterance})
            memory.save_context({"input": seller_utterance}, {"output": buyer_response})
            conversation_log.append(("Buyer", buyer_response))
            buyer_utterance = buyer_response

            # Checa se a conversa deve parar
            full_history = ""
            for m in memory.load_memory_variables({})["history"]:
                role = "Buyer" if m.type == "human" else "Seller"
                full_history += f"{role}: {m.content}\n"

            if should_stop_conversation(full_history):
                break

        end_turn = time.time()
        timing_log.append(end_turn - start_turn)
        turn += 1

    total_time = time.time() - start_convo

    os.makedirs("logs", exist_ok=True)
    with open(f"logs/{model_key}.txt", "w", encoding="utf-8") as f:
        f.write(f"Modelo: {model_key} ({model_name})\n")
        f.write(f"Temperatura: {TEMPERATURE}\n")
        f.write(f"Total de turns: {len(conversation_log)}\n")
        f.write(f"Tempo total da conversa: {total_time:.2f} segundos\n")
        f.write(f"Tempo médio por turn: {sum(timing_log)/len(timing_log):.2f} segundos\n\n")
        f.write("--- Conversa ---\n")
        for role, text in conversation_log:
            f.write(f"{role}: {text}\n")

    print(f"✅ Conversa com {model_key} salva em logs/{model_key}.txt")

def main():
    print("=== Iniciando testes com modelos ===\n")
    for nome_modelo, codigo_modelo in MODELOS.items():
        print(f"\n🔍 Rodando conversa com modelo: {nome_modelo} ({codigo_modelo})")
        rodar_conversa_com_medicao(nome_modelo, codigo_modelo)

    print("\n=== Fim dos testes. Verifique a pasta 'logs' para análise detalhada. ===")

if __name__ == "__main__":
    main()
