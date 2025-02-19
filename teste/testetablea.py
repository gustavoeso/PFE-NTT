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
from langchain.chains import LLMChain

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
# 3. Agents: PromptGenerator, Pesquisador, Comprador
##############################################################################

prompt_generator_prompt = PromptTemplate(
    input_variables=["user_request"],
    template="""
Você é um especialista em mapear pedidos do comprador para uma consulta na tabela 'lojas'.

A tabela 'lojas' tem colunas: id, tipo, numero.
 - 'tipo' pode ser 'Roupas', 'Jogos', 'Skate', etc.

O comprador quer: "{user_request}".

Gere, em português, um comando de consulta (NÃO em SQL, mas um texto em linguagem natural)
que será usado pelo pesquisador para encontrar a loja certa na tabela 'lojas'.

Explique brevemente qual 'tipo' corresponde ao que o comprador quer. 
Retorne APENAS o texto que o pesquisador usará, sem explicações adicionais.
""",
)
prompt_generator_chain = LLMChain(
    llm=llm,
    prompt=prompt_generator_prompt,
    verbose=True
)

prompt_generator_agent = Agent(
    role="Gerador de Prompt",
    goal="Dado o pedido do comprador, gerar o texto que será usado para consultar 'lojas'.",
    backstory="Este Agente gera a prompt de pesquisa para a tabela lojas, baseado no pedido do comprador.",
    tools=[],
    llm=llm
)

pesquisador = Agent(
    role="Pesquisador de Produtos",
    goal="Interpretar o prompt do PromptGenerator e consultar somente a loja relevante (sem iterar por todas).",
    backstory="Você sabe como usar o texto do PromptGenerator para fazer a query na tabela 'lojas'.",
    tools=[],
    llm=llm
)

comprador = Agent(
    role="Comprador",
    goal="Encontrar a melhor camisa branca e negociar diretamente o preço.",
    backstory="Você tem um casamento neste fim de semana e precisa de uma camisa branca elegante.",
    llm=llm,
    memory=memory
)

# A task that orchestrates the flow: "comprador -> prompt_generator -> pesquisador"
task = Task(
    description=(
        "O comprador pede algo, o PromptGenerator gera a instrução para o pesquisador, "
        "e então o pesquisador acha a loja na tabela 'lojas'."
    ),
    agent=pesquisador,  # The 'pesquisador' is the main agent that we'll run in code
    tools=[],
    memory=memory,
    expected_output="Dados da loja e possíveis produtos correspondentes."
)

crew = Crew(
    agents=[prompt_generator_agent, pesquisador, comprador],
    tasks=[task]
)

##############################################################################
# 4. Additional Prompt & Chain for Searching loja_{numero}
##############################################################################

# Main prompt for the "exact" product search in loja_{numero}
prompt_loja_prompt = PromptTemplate(
    input_variables=["store_number", "user_request"],
    template="""
Você é um especialista em mapear o pedido do comprador para uma consulta na tabela 'loja_{store_number}'.

A tabela 'loja_{store_number}' tem colunas: 
  - produto (texto)
  - qtd (inteiro)
  - preco (decimal)

O comprador quer: "{user_request}"

Gere UMA LINHA de texto (em português) que especifique o que consultar nessa tabela,
exatamente no formato:

Na tabela 'loja_{store_number}', retorne produto, qtd, preco onde produto ILIKE '%...%'.

Use a string do "user_request" no lugar de "...".  
Retorne SOMENTE a linha final, sem explicações adicionais.
""",
)
prompt_loja_chain = LLMChain(
    llm=llm,
    prompt=prompt_loja_prompt,
    verbose=True
)

# Fallback prompt if no exact matches were found:
# We'll ask the LLM to produce a "recommendation" query to find similar products or
# items in a similar category/price range.
prompt_loja_fallback = PromptTemplate(
    input_variables=["store_number", "user_request"],
    template="""
Não foi encontrado o item exato "{user_request}" na tabela 'loja_{store_number}'.
Gere UMA LINHA de texto (em português), no formato:

Na tabela 'loja_{store_number}', retorne produto, qtd, preco onde ...

para consultar produtos semelhantes ou alternativas que o comprador possa gostar.
Isto pode envolver usar ILIKE '%termo%' parcial, ou filtrar por similar categoria,
ou uma faixa de preço parecida. Retorne SOMENTE a linha final, sem explicações.
""",
)
prompt_loja_fallback_chain = LLMChain(
    llm=llm,
    prompt=prompt_loja_fallback,
    verbose=True
)

##############################################################################
# 5. Flow Implementation
##############################################################################

# Step A: Buyer request
buyer_request = "Preciso comprar o jogo de vídeo game Baldurs Door."

print(f"\n[Comprador diz]: '{buyer_request}'")

# Step B: PromptGenerator Agent -> creates the NATURAL LANGUAGE prompt for 'lojas'
prompt_for_lojas = prompt_generator_chain.run({"user_request": buyer_request})
print(f"\n[PromptGenerator output for 'lojas' query]:\n{prompt_for_lojas}")

# Step C: Pesquisador uses that generated text to do the actual search in 'lojas'
sql_store, rows_store = search_database(prompt_for_lojas)
print("\n[SQL Generated by LLM / Pesquisador]:\n", sql_store)
print("[Rows from DB]:\n", rows_store)

if not rows_store:
    print("Nenhuma loja encontrada para esse pedido do comprador.")
    exit(0)

store_row = rows_store[0]
store_info = {
    "id": store_row[0],
    "tipo": store_row[1],
    "numero": int(store_row[2])
}
print("\n[Loja escolhida]:", store_info)

# Step D: Get store coordinates from `posicao`
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
print("[Coordenadas]:", coords)

##############################################################################
# Step E: Check in `loja_{numero}` using the main prompt, fallback if needed
##############################################################################

item_request = buyer_request  # or parse the user's actual item from buyer_request if desired

# (1) Primary attempt to find EXACT match
prompt_for_loja = prompt_loja_chain.run({
    "store_number": store_info["numero"],
    "user_request": item_request
})
print(f"\n[PromptLoja output for 'loja_{store_info['numero']}' query]:\n{prompt_for_loja}")

sql_loja, rows_loja = search_database(prompt_for_loja)
print("\n[SQL Generated by LLM for loja_{store_info['numero']}]:\n", sql_loja)
print("[Rows from DB]:\n", rows_loja)

matching_items = []
for r in rows_loja:
    matching_items.append({
        "produto": r[0],
        "qtd": r[1],
        "preco": float(r[2])
    })

# (2) If no exact matches, fallback to "similar product" query
if not matching_items:
    print("\nNenhum item exato encontrado. Tentando recomendações semelhantes...\n")
    prompt_for_fallback = prompt_loja_fallback_chain.run({
        "store_number": store_info["numero"],
        "user_request": item_request
    })
    print("[PromptLoja fallback output]:", prompt_for_fallback)

    sql_loja_fallback, rows_loja_fallback = search_database(prompt_for_fallback)
    print("\n[SQL Generated by LLM for fallback]:\n", sql_loja_fallback)
    print("[Rows from DB]:\n", rows_loja_fallback)

    recommended_items = []
    for r in rows_loja_fallback:
        recommended_items.append({
            "produto": r[0],
            "qtd": r[1],
            "preco": float(r[2])
        })

    # Overwrite or combine?
    matching_items = recommended_items

##############################################################################
# 6. Final Summary
##############################################################################

print("\n=== FINAL SUMMARY ===")
if matching_items:
    print(f"Loja #{store_info['numero']} (tipo='{store_info['tipo']}') tem:")
    for it in matching_items:
        print(f" - {it['produto']} (qtd={it['qtd']}, preco={it['preco']})")
    print("Coordenadas da loja:", coords)
else:
    print(f"Nenhum resultado encontrado ou recomendado para '{item_request}'.")

##############################################################################
# 7. (Optional) Save conversation/results to file
##############################################################################

with open("conversa.txt", "w", encoding="utf-8") as file:
    file.write("--- Buyer request ---\n")
    file.write(buyer_request + "\n\n")

    file.write("--- PromptGenerator output ---\n")
    file.write(prompt_for_lojas + "\n\n")

    file.write("--- Pesquisador store query (SQL) ---\n")
    file.write(sql_store + "\n\n")
    file.write(str(rows_store) + "\n\n")

    file.write("--- Coordinates ---\n")
    file.write(sql_pos + "\n")
    file.write(str(coords) + "\n\n")

    file.write("--- Loja exact match query ---\n")
    file.write(prompt_for_loja + "\n")
    file.write(sql_loja + "\n")
    file.write(str(rows_loja) + "\n\n")

    if not rows_loja:
        file.write("--- Loja fallback query ---\n")
        file.write(prompt_for_fallback + "\n")
        file.write(sql_loja_fallback + "\n")
        file.write(str(recommended_items) + "\n\n")
