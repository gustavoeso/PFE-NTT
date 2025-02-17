from fastapi import FastAPI, Request
from crewai import Agent, Crew, Task
import uvicorn
from agents import AClient, ASeller, AFilter, AStore_Clothes

app = FastAPI()

@app.post("/request/client")
async def process_prompt(request: Request):
    data = await request.json()
    prompt = data.get("prompt", "")
    AgentTask = Task(description = "Pergunte para a vendedora da loja onde encontrar o seguinte produto : {prompt}",
                     agent = AClient,
                     expected_output="Uma pergunta para a vendedora da loja")
    
    try:
        finalCrew = Crew(agents=[AClient], tasks=[AgentTask])
        result = finalCrew.kickoff(inputs={"prompt" : prompt})
        answer = result.raw.strip()
    except Exception as e:
        answer = f"Ocorreu um erro: {e}"
    
    return {"response": answer}

@app.post("/request/seller")
async def process_prompt(request: Request):
    data = await request.json()
    prompt = data.get("prompt", "")
    AgentTask = Task(description = "O cliente diz o seguinte : {prompt}",
                     agent = ASeller,
                     expected_output="Responda a loja que melhor atende os desejos do cliente")
    
    try:
        finalCrew = Crew(agents=[ASeller], tasks=[AgentTask])
        result = finalCrew.kickoff(inputs={"prompt" : prompt})
        answer = result.raw.strip()
    except Exception as e:
        answer = f"Ocorreu um erro: {e}"
    
    return {"response": answer}

@app.post("/request/filter")
async def process_prompt(request: Request):
    data = await request.json()
    prompt = data.get("prompt", "")
    AgentTask = Task(description = "Qual o número da loja que a vendedora respondeu nessa pergunta : {prompt}",
                     agent = AFilter,
                     expected_output="Apenas um número de 1 a 4, caso não exista loja correspondente retorne 0")
    
    try:
        finalCrew = Crew(agents=[AFilter], tasks=[AgentTask])
        result = finalCrew.kickoff(inputs={"prompt" : prompt})
        answer = result.raw.strip()
    except Exception as e:
        answer = f"Ocorreu um erro: {e}"
    
    return {"response": answer}

@app.post("/request/clothes")
async def process_prompt(request: Request):
    data = await request.json()
    prompt = data.get("prompt", "")
    AgentTask = Task(description = "Um cliente irá chegar te pedindo o seguinte produto : {prompt}",
                     agent = AStore_Clothes,
                     expected_output="Retorne ao cliente se você possui o produto em estoque e recomende 3 produtos para tentar atende-lo, caso não possua o produto redirecione-o para outra loja conhecida ou expulse-o do shopping")
    
    try:
        finalCrew = Crew(agents=[AStore_Clothes], tasks=[AgentTask])
        result = finalCrew.kickoff(inputs={"prompt" : prompt})
        answer = result.raw.strip()
    except Exception as e:
        answer = f"Ocorreu um erro: {e}"
    
    return {"response": answer}

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)






