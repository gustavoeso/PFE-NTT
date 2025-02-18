import os
from crewai import Agent, Task, Crew
from crewai_tools import PGSearchTool

# Set up your PostgreSQL database URI
db_uri = 'postgresql://myuser:mypassword@localhost:5432/shopping'

# Initialize the PGSearchTools, each pointing to a different table
pg_search_tool_lojas = PGSearchTool(
    db_uri=db_uri,
    table_name='lojas'
)

pg_search_tool_pos = PGSearchTool(
    db_uri=db_uri,
    table_name='posicao'
)

# ----- 1) Define the first agent for the "lojas" table -----
agent_lojas = Agent(
    role='Agente de Busca no Banco de Dados (Lojas)',
    goal='Encontrar o número da loja com tipo = Roupas',
    backstory='Especializado em encontrar números de loja com base no tipo fornecido.',
    tools=[pg_search_tool_lojas],
    verbose=True
)

# ----- 2) Define the second agent for the "posicao" table -----
agent_pos = Agent(
    role='Agente de Busca no Banco de Dados (Posições)',
    goal='Encontrar as coordenadas (x, y, z) com base no número da loja',
    backstory='Especializado em buscar as coordenadas de uma loja a partir do número.',
    tools=[pg_search_tool_pos],
    verbose=True
)

# ----- Define the two tasks -----
# Task 1: Find the store number for the "Roupas" shop
task_lojas = Task(
    description="""
    Você tem acesso à tabela "lojas", que possui colunas "tipo" e "numero".
    
    **Objetivo**: 
    1. Pesquise na tabela "lojas" para encontrar o "numero" da loja em que "tipo" = 'Roupas'.
    2. Retorne somente esse número (por exemplo, "42").
    """,
    agent=agent_lojas,
    # CrewAI requires expected_output, so we provide a placeholder:
    expected_output="42"  # or any placeholder
)

# Task 2: Given that store number, find the coordinates from the "posicao" table
task_pos = Task(
    description="""
    Você receberá como entrada um valor de "numero" de loja.
    Use esse número para buscar na tabela "posicao" (colunas "x", "y", "z" correspondentes a esse numero).
    
    **Objetivo**:
    1. Retornar as coordenadas no formato "x, y, z" (por exemplo, "10, 20, 1").
    """,
    agent=agent_pos,
    # Again, required placeholder:
    expected_output="10, 20, 1"  # or any placeholder
)

# ----- Create the Crew with both agents and both tasks -----
crew = Crew(
    agents=[agent_lojas, agent_pos],
    tasks=[task_lojas, task_pos],
    verbose=True
)

# ----- Run the tasks in sequence -----
if __name__ == '__main__':
    # 1. Execute the first task to find the store number
    store_number = crew.run_task(task_lojas)
    
    # 2. Update the description of the second task with the store_number
    task_pos.description = f"""
    O número da loja é {store_number}.
    Use esse número para buscar na tabela "posicao" e retorne as coordenadas no formato "x, y, z".
    """
    
    # 3. Execute the second task to fetch the coordinates
    coordinates = crew.run_task(task_pos)
    
    # Print the final result
    print("Coordenadas encontradas:", coordinates)
