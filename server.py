from fastapi import FastAPI, Request
import uvicorn
import os
from langchain_community.chat_models import ChatOpenAI
from langchain.memory import ConversationSummaryMemory
from langchain.chains import ConversationChain
from langchain.schema import SystemMessage
from dotenv import load_dotenv

app = FastAPI()

load_dotenv()

model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
api_key = os.getenv("OPENAI_API_KEY", "your_openai_api_key")

llm = ChatOpenAI(
    model_name=model_name,
    openai_api_key=api_key,
    temperature=0.3
)

# Dicionário global para armazenar os agentes
agentsDict = {}

# Prompts constantes para cada agente
CLIENT_PROMPT = ("Você é um agente de IA no ecossistema de agentes."
                 "Sua função é encontrar um produto específico dentro de um shopping"
                 "Você só deve retornar em suas respostas frases que componham os dialogos de um cliente")

GUIDE_PROMPT = ("Você é um agente de IA no ecossistema de agentes. "
                "Sua função é auxiliar clientes a encontrarem a localização de um produto "
                "específico dentro de um shopping.")
GUIDE_LOCATIONS = "A loja 1 vende roupas, a loja 2 vende eletrônicos, a loja 3 vende alimentos e a loja 4 vende livros"

FILTER_PROMPT = ("Você é um agente de IA responsável por filtrar e identificar a loja mais apropriada "
                 "para um produto específico, com base nas informações disponíveis sobre o shopping.")

CLOTHES_PROMPT = ("Você é um agente de IA que representa uma loja de roupas. "
                  "Sua função é auxiliar clientes a encontrarem produtos de vestuário dentro de um shopping.")

@app.post("/startApplication")
async def start_application():
    global agentsDict
    agentsDict = {}

    # Criação do agente Client
    memoryClient = ConversationSummaryMemory(llm=llm)
    memoryClient.chat_memory.add_message(SystemMessage(content=CLIENT_PROMPT))
    AClient = ConversationChain(llm=llm, memory=memoryClient)
    agentsDict["client"] = AClient

    # Criação do agente Guide (com localização das lojas)
    memoryGuide = ConversationSummaryMemory(llm=llm)
    memoryGuide.chat_memory.add_message(SystemMessage(content=GUIDE_PROMPT))
    memoryGuide.chat_memory.add_message(SystemMessage(content=GUIDE_LOCATIONS))
    AGuide = ConversationChain(llm=llm, memory=memoryGuide)
    agentsDict["guide"] = AGuide

    # Criação do agente Filter
    memoryFilter = ConversationSummaryMemory(llm=llm)
    memoryFilter.chat_memory.add_message(SystemMessage(content=FILTER_PROMPT))
    AFilter = ConversationChain(llm=llm, memory=memoryFilter)
    agentsDict["filter"] = AFilter

    # Criação do agente Clothes
    memoryClothes = ConversationSummaryMemory(llm=llm)
    memoryClothes.chat_memory.add_message(SystemMessage(content=CLOTHES_PROMPT))
    AClothes = ConversationChain(llm=llm, memory=memoryClothes)
    agentsDict["clothes"] = AClothes

    return {"status": "Aplicação iniciada, memórias reiniciadas e funções dos agentes definidas"}

@app.post("/request/{agent_id}")
async def process_prompt(agent_id: str, request: Request):
    global agentsDict
    data = await request.json()
    prompt = data.get("prompt", "")
    
    agent = agentsDict.get(agent_id)
    if agent is None:
         return {"response": f"Agente '{agent_id}' não encontrado."}
    
    try:
         answer = agent.run(prompt)
    except Exception as e:
         answer = f"Ocorreu um erro: {e}"
    
    return {"response": answer}

@app.post("/extractNumber")
async def extract_number(request: Request):
    data = await request.json()
    text = data.get("text", "")
    number = "".join(filter(str.isdigit, text))
    return {"number": number}

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)






