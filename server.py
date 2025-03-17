from fastapi import FastAPI, Request
from langchain_community.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from dotenv import load_dotenv
import uvicorn
import os

load_dotenv()

app = FastAPI()

model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
api_key = os.getenv("OPENAI_API_KEY")

agentsDict = {}
memoryDict = {}

llm = ChatOpenAI(model_name=model_name, api_key=api_key, temperature=0)

client_system_template = """
Você é o Buyer (comprador) em uma loja de roupas em um shopping.
Não se identifique como IA.

Objetivo:
- Você quer comprar um item específico, que será fornecido em um prompt inicial.
- Você deve entrar em diálogos com outros agentes para encontrar o item desejado.
- Os diálogos devem ser naturais e coerentes.
- Os diálogos poderão ser tanto com um guia do shopping quanto com um vendedor da loja.
- Quando decidir, diga explicitamente \"Vou levar\" ou \"Não vou levar\".

Histórico da conversa até agora:
{history}
"""

client_human_template = """
A última resposta recebida foi:
{last_response}

Agora responda como cliente:
1. Se ainda não encontrou o item desejado, pergunte ao guia onde encontrar.
2. Se já encontrou o item desejado, diga \"Vou levar\" ou \"Não vou levar\".
3. Se tiver dúvidas em relação ao item, pergunte ao vendedor.
"""

guide_system_template = """
Você é o Guia do Shopping, educado e prestativo, responsável por ajudar clientes a encontrar lojas específicas.
Não se identifique como IA.

As lojas disponíveis são:
1. Loja de Roupas
2. Loja de Eletrônicos
3. Loja de Brinquedos
4. Loja de Alimentos

Histórico da conversa até agora:
{history}
"""

guide_human_template = """
A última resposta recebida foi:
{last_response}

Agora responda como guia:
- Sempre indique uma das quatro lojas mencionadas acima, escolhendo a mais apropriada para o item solicitado pelo cliente.
- Você DEVE mencionar explicitamente o número da loja escolhida junto com o nome da loja na sua resposta.
- Mencione sempre apenas uma loja.
- Em sua resposta deve haver sempre apenas um único número, representando a loja escolhida.
- Não mencione lojas que não estejam na lista.

Exemplo correto: "Você pode encontrar esse item na Loja 1, a Loja de Roupas."
"""

store_system_template = """
Você é o vendedor de uma loja que deve auxiliar o comprador a encontrar o produto desejado em sua loja, dentro de um estoque inventado.
Não se identifique como IA.

Histórico da conversa até agora:
{history}
"""

store_human_template = """
A última resposta recebida foi:
{last_response}

Agora responda como vendedor:
- Qual produto da loja melhor atende os requisitos do cliente.
- Ofereça apenas um produto, deixando para decisão do cliente se ele irá ou não querer.
"""

@app.post("/startApplication")
async def start_application():
    agentsDict.clear()
    memoryDict.clear()

    client_memory = ConversationBufferMemory(memory_key="history", return_messages=True)
    client_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(client_system_template),
        HumanMessagePromptTemplate.from_template(client_human_template)
    ])
    agentsDict["client"] = LLMChain(llm=llm, prompt=client_prompt, memory=client_memory)
    memoryDict["client"] = client_memory

    guide_memory = ConversationBufferMemory(memory_key="history", return_messages=True)
    guide_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(guide_system_template),
        HumanMessagePromptTemplate.from_template(guide_human_template)
    ])
    guide_chain = LLMChain(llm=llm, prompt=guide_prompt, memory=guide_memory)

    agentsDict["guide"] = guide_chain
    memoryDict["guide"] = guide_memory

    store_memory = ConversationBufferMemory(memory_key="history", return_messages=True)
    store_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(store_system_template),
        HumanMessagePromptTemplate.from_template(store_human_template)
    ])
    store_chain = LLMChain(llm=llm, prompt=store_prompt, memory=store_memory)

    agentsDict["store"] = store_chain
    memoryDict["store"] = store_memory

    return {"status": "Aplicação iniciada corretamente."}

@app.post("/request/{agent_id}")
async def process_prompt(agent_id: str, request: Request):
    data = await request.json()
    prompt = data.get("prompt", "")
    speaker = data.get("speaker", "")

    if agent_id not in agentsDict:
        return {"response": f"Agente '{agent_id}' não encontrado."}

    if speaker == "client":
        answer = agentsDict["client"].run(last_response=prompt)
    else:
        answer = agentsDict[agent_id].run(last_response=prompt)

    memoryDict["client"].save_context({"input": prompt}, {"output": answer})
    if agent_id != "client":
        memoryDict[agent_id].save_context({"input": prompt}, {"output": answer})

    return {"response": answer}

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)






