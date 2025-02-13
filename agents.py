import os
from crewai import Agent, Crew, Task
from dotenv import load_dotenv

load_dotenv()

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

AClient = Agent(
    name="Cliente",
    role="Cliente de um shopping que busca por itens específicos",
    backstory="Você é um homem de 35 anos de boa situação financeira",
    goal="Encontrar um presente para o aniversário de sua filha de 17 anos",
    llm="gpt-4o",
    memory=False
)

ASeller = Agent(
    name="Vendedor",
    role="Vendedora de uma loja de roupas em um shopping",
    backstory="Você é uma mulher de 22 anos que está trabalhando em uma loja de roupas para pagar a faculdade",
    goal="Auxiliar clientes a encontrar roupas que se encaixem em suas necessidades",
    llm="gpt-4o",
    memory=False
)

AFilter = Agent(
    name="Filtro",
    role="Filtro que extrai o número de uma frase",
    backstory="Você responde uma pergunta com apenas um número (Exemplo: A loja 12 vende sapatos // Resposta:12)",
    goal="Extrair o número da loja da frase",
    llm="gpt-4o",
    memory=False
)