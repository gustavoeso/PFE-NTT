import os
from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import (
    ChatPromptTemplate, 
    SystemMessagePromptTemplate, 
    HumanMessagePromptTemplate, 
    PromptTemplate
)
from langchain.memory import ConversationBufferMemory

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-4")

TEMPERATURES = [0.0, 0.1, 0.3, 0.7, 1.0]

def criar_buyer_chain(temp, memory):
    buyer_system_template = """
    Você é o Buyer (comprador) em uma loja de roupas num shopping.
    Não se identifique como IA.

    Objetivo:
    - Você quer comprar alguma peça de roupa ou não.
    - Se ainda não decidiu, você pode fazer perguntas (limite: 3 perguntas).
    - Ao atingir 3 perguntas, ou se o Seller já informou tudo que você queria saber, DECIDA.
    - Quando decidir, diga explicitamente algo contendo 'vou levar' ou 'não vou levar' (essas substrings).
    
    Contexto:
    - Você está procurando uma camiseta branca.
    - Se encontrar uma camiseta branca por até R$ 60,00, você tende a comprar.
    - Caso contrário, você pode ficar indeciso ou recusar.

    Histórico da conversa até agora:
    {history}
    """

    buyer_human_template = """
    A última fala do Vendedor (Seller) foi:
    {seller_utterance}

    Agora responda como BUYER:
    1. Lembre-se de que você só pode fazer até 3 perguntas.
    2. Se já fez 3 perguntas ou se está satisfeito, use a frase 'vou levar' ou 'não vou levar' em sua resposta final.
    3. Não se identifique como IA.
    """

    buyer_prompt = ChatPromptTemplate(
        input_variables=["history", "seller_utterance"],
        messages=[
            SystemMessagePromptTemplate.from_template(buyer_system_template),
            HumanMessagePromptTemplate.from_template(buyer_human_template),
        ]
    )

    return LLMChain(
        llm=ChatOpenAI(
            openai_api_key=api_key, 
            model_name=model_name, 
            temperature=temp
        ),
        prompt=buyer_prompt,
        memory=memory,
        verbose=False
    )

def criar_seller_chain(memory):
    seller_system_template = """
    Você é o Seller (vendedor) em uma loja de roupas num shopping.
    Não se identifique como IA.

    Objetivo:
    - Vender roupas, mas não encerrar a conversa. 
    - Responda perguntas do Buyer.
    - Se o Buyer disser algo contendo 'vou levar' ou 'não vou levar', é ele que está decidindo.

    Histórico da conversa até agora:
    {history}
    """

    seller_human_template = """
    A última fala do Comprador (Buyer) foi:
    {buyer_utterance}

    Agora responda como SELLER:
    1. Ofereça informações sobre as roupas, preços etc.
    2. Não se identifique como IA.
    3. Não encerre por conta própria.
    """

    seller_prompt = ChatPromptTemplate(
        input_variables=["history", "buyer_utterance"],
        messages=[
            SystemMessagePromptTemplate.from_template(seller_system_template),
            HumanMessagePromptTemplate.from_template(seller_human_template),
        ]
    )

    return LLMChain(
        llm=ChatOpenAI(
            openai_api_key=api_key, 
            model_name=model_name, 
            temperature=0.3
        ),
        prompt=seller_prompt,
        memory=memory,
        verbose=False
    )

def criar_controller_chain():
    controller_prompt_template = """
    Você é um agente controlador que analisa o histórico da conversa (Buyer e Seller)
    e decide se deve ENCERRAR ou CONTINUAR.

    REGRAS:
    - Responda "STOP" SOMENTE se o Buyer disser algo que contenha a substring "vou levar" ou "não vou levar".
    - Caso contrário => CONTINUE.
    - Não use nada além de STOP ou CONTINUE (sem aspas).

    Leia o histórico abaixo e retorne somente STOP ou CONTINUE:

    {history}
    """

    controller_prompt = PromptTemplate(
        input_variables=["history"], 
        template=controller_prompt_template
    )

    return LLMChain(
        llm=ChatOpenAI(
            openai_api_key=api_key, 
            model_name=model_name, 
            temperature=0.0
        ),
        prompt=controller_prompt,
        verbose=False
    )

def rodar_conversa(temperatura):
    """Executa a conversa com a temperature dada e imprime o log, mas NÃO faz classificação automática."""
    memory = ConversationBufferMemory(memory_key="history", return_messages=True)

    buyer_chain = criar_buyer_chain(temperatura, memory)
    seller_chain = criar_seller_chain(memory)
    controller_chain = criar_controller_chain()

    # Armazenamos falas localmente para imprimir
    conversation_log = []

    buyer_utterance = "Oi, estou procurando uma camiseta branca."
    # Armazena na memória
    memory.save_context({"input": "[BEGIN]"}, {"output": buyer_utterance})
    conversation_log.append(("Buyer", buyer_utterance))

    seller_utterance = ""
    turn = 2
    max_turns = 10

    while turn <= max_turns:
        # Montar histórico p/ controller
        mem_vars = memory.load_memory_variables({})
        history_str = ""
        for m in mem_vars["history"]:
            role = "Buyer" if m.type == "human" else "Seller"
            history_str += f"{role}: {m.content}\n"

        decision = controller_chain.run({"history": history_str})
        if "STOP" in decision.upper():
            break

        if turn % 2 == 0:
            # Seller
            seller_response = seller_chain.run({"buyer_utterance": buyer_utterance})
            conversation_log.append(("Seller", seller_response))
            # Salva no memory
            memory.save_context({"input": buyer_utterance}, {"output": seller_response})
            seller_utterance = seller_response
        else:
            # Buyer
            buyer_response = buyer_chain.run({"seller_utterance": seller_utterance})
            conversation_log.append(("Buyer", buyer_response))
            # Salva no memory
            memory.save_context({"input": seller_utterance}, {"output": buyer_response})
            buyer_utterance = buyer_response

        turn += 1

    # Imprime a conversa
    print(f"\n--- Conversa final (T={temperatura}) ---")
    for role, text in conversation_log:
        print(f"{role}: {text}")

def main():
    print("=== Iniciando teste para análise manual ===\n")
    for temp in TEMPERATURES:
        print(f"\n========================\nTestando temperatura {temp}\n========================")
        rodar_conversa(temp)

    print("\n=== Fim dos testes! Agora copie a conversa acima e analise manualmente. ===")

if __name__ == "__main__":
    main()
