import os
from dotenv import load_dotenv
from fastapi import FastAPI, Request
import uvicorn

# Carrega as variáveis do arquivo .env
load_dotenv()

# Configura a API Key da OpenAI a partir do .env
os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

# Importa as classes do CrewAI
from crewai import Agent, Crew, Task

app = FastAPI()

# Criação de um agente simples com CrewAI
agent = Agent(
    name="AgenteCalculador",
    role="Um agente especializado em cálculos.",  # Agora como string
    backstory="Treinado para resolver problemas aritméticos básicos, com experiência em soma, subtração, multiplicação e divisão.",  # Agora como string
    goal="Responder perguntas aritméticas simples",
    llm="gpt-4o",
    memory=False  # Para este exemplo, não utilizamos memória
)

@app.post("/prompt")
async def process_prompt(request: Request):
    data = await request.json()
    prompt = data.get("prompt", "")
    AgentTask = Task(description = "Responda ao seguinte {prompt}",
                     agent = agent,
                     expected_output="Resposta ao prompt")
    
    try:
        finalCrew = Crew(agents=[agent], tasks=[AgentTask])
        # Utiliza o CrewAI para processar o prompt.
        # Supondo que o método 'kickoff' aceite o parâmetro 'prompt'
        # e retorne um dicionário com a chave "result" contendo a resposta.
        result = finalCrew.kickoff(inputs={"prompt" : prompt})
        answer = result.get("result", "Sem resposta")
    except Exception as e:
        answer = f"Ocorreu um erro: {e}"
    
    return {"response": answer}

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)






