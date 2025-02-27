from fastapi import FastAPI, Request
import uvicorn
import os
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationSummaryMemory
from langchain.chains import ConversationChain
from langchain.schema import SystemMessage

app = FastAPI()

model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
api_key = os.getenv("OPENAI_API_KEY", "your_openai_api_key")

llm = ChatOpenAI(
    model_name=model_name,
    openai_api_key=api_key,
    temperature=0.3
)

memoryClient = None
memoryGuide = None
AClient = None
AGuide = None
agentsDict = {}
CLIENT_PROMPT = "Você é um agente de IA no ecossistema de agentes. Sua função é procurar um produto específico dentro de um shopping, procurando informações sobre o mesmo através de dialogos."
GUIDE_PROMPT = "Você é um agente de IA no ecossistema de agentes. Sua função é auxiliar clientes a encontrarem a localização de um produto específico dentro de um shopping."
GUIDE_LOCATIONS = "A loja 1 vende roupas, a loja 2 vende eletrônicos, a loja 3 vende alimentos e a loja 4 vende livros"

@app.post("/startApplication")
async def start_application(request: Request):

    global llm, memory, agent
    agentsDict = {}

    # Geração do Client
    memoryClient = ConversationSummaryMemory(llm=llm)
    memoryClient.chat_memory.add_message(SystemMessage(content=CLIENT_PROMPT))
    AClient = ConversationChain(llm=llm, memory=memoryClient)
    agentsDict["client"] = AClient

    # Geração do Guide
    memoryGuide = ConversationSummaryMemory(llm=llm)
    memoryGuide.chat_memory.add_message(SystemMessage(content=GUIDE_PROMPT))
    memoryGuide.chat_memory.add_message(SystemMessage(content=GUIDE_LOCATIONS))
    AGuide = ConversationChain(llm=llm, memory=memoryGuide)
    agentsDict["guide"] = AGuide
    
    return {"status": "Aplicação iniciada, memória reiniciada e função do agente definida"}

@app.post("/agent")
async def process_prompt(request: Request):
    global agent
    data = await request.json()
    prompt = data.get("prompt", "")
    agentID = data.get("agent", "")
    agent = agentsDict[agentID]
    
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






