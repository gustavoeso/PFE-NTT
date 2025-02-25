import os
from crewai import Agent, Crew, Task
from dotenv import load_dotenv

load_dotenv()

os.environ["OPENAI_API_KEY"] = os.getenv("OPENAI_API_KEY")

AClient = Agent(
    name="Cliente",
    role="Comprador de itens",
    backstory="Será requisitado a você que encontre um produto específico dentro de um shopping",
    goal="Encontrar um presente para o aniversário de sua filha de 17 anos",
    llm="gpt-4o",
    memory=False
)

ASeller = Agent(
    name="Vendedor",
    role="Vendedora de uma loja de roupas em um shopping",
    backstory="A loja 1 é responsável por vender itens tecnologicos, a loja 2 roupas, a loja 3 vende diversos tipos de alimento e a loja 4 vende livros",
    goal="Auxiliar clientes a encontrar roupas que se encaixem em suas necessidades, você sempre deve dirigir o cliente a uma das lojas do shopping, sendo da loja 1 a 4",
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

AStore_Clothes = Agent(
    role="Vendedor de Loja de Roupas",
    goal="Vender as melhores roupas, caso não consiga atender o cliente redirecione-o para outra loja",
    backstory=(
        "Você conhece bem o estoque. Procure oferecer 3 opções, discuta preços e tente concretizar a venda."
        "A loja 1 é responsável por vender itens tecnologicos, a loja 2 roupas, a loja 3 vende diversos tipos de alimento e a loja 4 vende livros"
        "Em seu estoque você possui camisetas lisas de diversas cores, calças jeans e sapatos sociais"
    ),
    memory=False,
    verbose=False,
    allow_delegation=False,
    llm=os.getenv("OPENAI_MODEL_NAME") or "gpt-3.5-turbo"
)