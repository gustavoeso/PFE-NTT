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


# Define the agent with the PGSearchTool
search_agent = Agent(
    role='Agente de pesquisa de banco de dados.',
    goal='Encontrar o número da loja requisitada em uma tabela PostgreSQL.',
    backstory='Um agente de IA especialista em encontrar número de lojas em uma tabela.',
    tools=[pg_search_tool_lojas],
    verbose=True
)

# Define the task for the agent
search_task = Task(
    description='Encontre o número da loja desejada.',
    expected_output='100.',
    agent=search_agent
)

# Create the crew with the agent and task
crew = Crew(
    agents=[search_agent],
    tasks=[search_task],
    verbose=True
)

# Execute the task
if __name__ == '__main__':
    result = crew.kickoff()
    print(result)