import os
from dotenv import load_dotenv

from crewai import Agent, Task, Crew
import openai

# LangChain + SQL
from langchain.memory import ConversationSummaryMemory
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from langchain_experimental.sql import SQLDatabaseChain
from langchain.prompts.prompt import PromptTemplate

from sqlalchemy import create_engine, text

##############################################################################
# 1. Environment Setup & LLM
##############################################################################

load_dotenv()

db_uri = 'postgresql://myuser:mypassword@localhost:5432/shopping'
api_key = os.getenv("OPENAI_API_KEY")
model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-4-turbo")

llm = ChatOpenAI(
    model_name=model_name,
    openai_api_key=api_key,
    temperature=0.3
)

memory = ConversationSummaryMemory(llm=llm)

##############################################################################
# 2. Database Setup (SQLAlchemy + LangChain)
##############################################################################

engine = create_engine(db_uri)
database = SQLDatabase(engine)

CUSTOM_SQL_PROMPT = """
You are an expert SQL developer. Given the user question, output a valid SQL query ONLY in the format:

SQLQuery: SELECT ...

No triple backticks or extra text. No explanations. Just the query.

User Question: {input}
SQLQuery:
"""

prompt = PromptTemplate(
    input_variables=["input"],
    template=CUSTOM_SQL_PROMPT,
)

sql_chain = SQLDatabaseChain.from_llm(
    llm=llm,
    db=database,
    prompt=prompt,
    verbose=True
)

def search_database(nl_query: str):
    """
    (1) Send a natural-language prompt to the chain -> get an SQL string.
    (2) Execute that SQL with SQLAlchemy -> return rows (as tuples).
    (3) Return (sql_text, rows).
    """
    chain_output = sql_chain.invoke({"query": nl_query})
    sql_text = chain_output.get("result", "")
    if not sql_text:
        return ("", [])

    with engine.connect() as conn:
        result_proxy = conn.execute(text(sql_text))
        rows = result_proxy.fetchall()
    
    return (sql_text, rows)

##############################################################################
# 3. Agents & Task
##############################################################################

# The "comprador" is effectively the user. They have a single goal: buy a camisa branca.
comprador = Agent(
    role="Comprador",
    goal="Encontrar a melhor camisa branca e negociar diretamente o preço.",
    backstory="Você tem um casamento neste fim de semana e precisa de uma camisa branca elegante.",
    llm=llm,
    memory=memory
)

# The "pesquisador" is the one who interacts with the DB. 
pesquisador = Agent(
    role="Pesquisador de Produtos",
    goal="Interpretar o desejo do comprador e consultar somente a loja relevante (sem iterar por todas).",
    backstory="Você conhece as categorias das lojas e sabe mapear 'camisa branca' para 'Roupas' => store 100.",
    tools=[],
    llm=llm
)

# A task instructing the "pesquisador" to find the store, get coordinates, and check availability.
task = Task(
    description=(
        "Interpretar a requisição do comprador ('camisa branca'), "
        "descobrir qual loja (apenas a adequada) em 'lojas', "
        "pegar suas coordenadas em 'posicao', e consultar a tabela loja_{numero} "
        "sobre a camisa branca. Não percorrer todas as lojas, apenas a correspondente."
    ),
    agent=pesquisador,
    tools=[],
    memory=memory,
    expected_output="Dados da loja que vende 'camisa branca' e sua localização."
)

crew = Crew(
    agents=[pesquisador, comprador],
    tasks=[task]
)

##############################################################################
# 4. Conversation / Logic Flow
##############################################################################

# The buyer's request:
buyer_request = "Preciso de uma camisa branca elegante."

# Step A: Pesquisador interprets which store from 'lojas' matches "camisa branca"
#   We'll rely on the LLM to guess that "camisa branca" => "Roupas" => store #100
#   so we do just one query to find that store.

nl_query_store = f"Na tabela 'lojas', qual a loja (id, tipo, numero) que combina com '{buyer_request}'? " \
                 "A loja deve ser aquela que tenha tipo 'Roupas' pois 'camisa branca' é uma roupa. " \
                 "Retorne somente a linha correspondente."

sql_store, rows_store = search_database(nl_query_store)
print("\nSQL used to interpret store:\n", sql_store)
print("Store rows:\n", rows_store)

if not rows_store:
    print("Nenhuma loja encontrada para 'camisa branca'.")
    exit(0)

# Convert the single row to a dict
store_row = rows_store[0]  # e.g. (1, 'Roupas', Decimal('100'))
store_info = {
    "id": store_row[0],
    "tipo": store_row[1],
    "numero": int(store_row[2])
}
print("\nStore chosen by Pesquisador:\n", store_info)

# Step B: Get the store's coordinates from `posicao`
nl_query_pos = (
    f"Na tabela 'posicao', retorne x,y,z onde numero = {store_info['numero']}."
)
sql_pos, rows_pos = search_database(nl_query_pos)
coords = []
for r in rows_pos:
    coords.append({
        "x": float(r[0]),
        "y": float(r[1]),
        "z": float(r[2])
    })
print("\nCoordinates for store:", coords)

# Step C: Check the store's table `loja_{numero}` for "camisa branca"
nl_query_loja = (
    f"Na tabela 'loja_{store_info['numero']}', retorne produto, qtd, preco "
    f"onde produto ILIKE '%camisa branca%'."
)
sql_loja, rows_loja = search_database(nl_query_loja)
matching_items = []
for r in rows_loja:
    matching_items.append({
        "produto": r[0],
        "qtd": r[1],
        "preco": float(r[2])
    })

print("\nMatching items in loja_{numero}:\n", matching_items)

# Final summary
print("\n=== FINAL SUMMARY ===")
if matching_items:
    print(f"Store #{store_info['numero']} (tipo='{store_info['tipo']}') sells:")
    for it in matching_items:
        print(f"  - {it['produto']} (qtd={it['qtd']}, preco={it['preco']})")
    print("Coordinates:", coords)
else:
    print(f"No 'camisa branca' found in loja_{store_info['numero']}.")

##############################################################################
# 5. (Optional) Save conversation or results
##############################################################################
with open("conversa.txt", "w", encoding="utf-8") as file:
    file.write("=== Buyer Request ===\n")
    file.write(buyer_request + "\n\n")

    file.write("=== Store Chosen ===\n")
    file.write(sql_store + "\n")
    file.write(str(rows_store) + "\n\n")

    file.write("=== Coordinates ===\n")
    file.write(sql_pos + "\n")
    file.write(str(coords) + "\n\n")

    file.write("=== Loja Table Query ===\n")
    file.write(sql_loja + "\n")
    file.write(str(matching_items) + "\n\n")
