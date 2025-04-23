from langchain_community.utilities import SQLDatabase
from langchain_experimental.sql import SQLDatabaseChain
from langchain.prompts import PromptTemplate
from sqlalchemy import text
from server.db.engine import engine
from server.config import OPENAI_API_KEY, OPENAI_MODEL_NAME
from langchain_openai import ChatOpenAI
from server.utils.memory import agent_cache
from server.llm.prompts import prompt_loja_prompt, prompt_loja_fallback_chain
from langchain.chains import LLMChain

# Setup

database = SQLDatabase(engine)
llm = ChatOpenAI(model_name=OPENAI_MODEL_NAME, openai_api_key=OPENAI_API_KEY, temperature=0.0)

# Novo prompt limpo (sem explicações, sem markdown)
CUSTOM_SQL_PROMPT = """
You are an expert SQL developer. The database schema is as follows:

TABLE `lojas`:
  - id (integer)
  - tipo (varchar)
  - numero (numeric)

TABLE `posicao`:
  - numero (integer)
  - x (integer)
  - y (integer)
  - z (integer)


TABLE `loja_100`:
    id SERIAL PRIMARY KEY,
    produto VARCHAR(50),
    tipo VARCHAR(50),
    qtd INT,
    preco DECIMAL(10,2),
    tamanho VARCHAR(10),
    material VARCHAR(50),
    estampa VARCHAR(3) CHECK (estampa IN ('Sim', 'Não'))

TABLE `loja_105`:
    id SERIAL PRIMARY KEY,
    produto VARCHAR(100), --> name of the game
    tipo VARCHAR(50),     --> category of the game
    qtd INT,              --> quantity in stock
    preco DECIMAL(10,2),  --> price
    console VARCHAR(50)   --> console name

No other `loja_{{n}}` tables exist.

IMPORTANT:
 - Do NOT reference columns that do not exist.
 - The table 'lojas' only has columns: id, tipo, numero
 - If the user mentions color, do not filter by color in 'lojas' – that belongs in `loja_{{numero}}`.
 - Only use existing columns.

Given the user question, output a valid SQL query ONLY in the format:

SQLQuery: SELECT ...

No triple backticks or extra text. No explanations. Just the query.

User Question: {input}
SQLQuery:
"""

sql_prompt = PromptTemplate(
    input_variables=["input"],
    template=CUSTOM_SQL_PROMPT,
)

sql_chain = SQLDatabaseChain.from_llm(
    llm=llm,
    db=database,
    prompt=sql_prompt,
    verbose=True  # shows prompt, SQL, and results in terminal
)

def search_database(nl_query: str):
    """
    Use the sql_chain to turn natural language into SQL, then execute it.
    Returns (sql_text, rows).

    Also sanitizes the output to remove triple backticks or "SQLQuery:".
    """
    try:
        chain_output = sql_chain.invoke({"query": nl_query})
    except Exception as e:
        print(f"[search_database] Error generating SQL: {e}")
        return ("", [])

    print(f"[search_database] Chain output: {chain_output}")

    raw_result = chain_output.get("result", "")
    if not raw_result:
        return ("", [])

    sanitized = raw_result.replace("```", "").replace("SQLQuery:", "").strip()
    sql_text = sanitized

    print(f"[search_database] SQL Gerado:\n{sql_text}")

    rows = []
    try:
        with engine.connect() as conn:
            result_proxy = conn.execute(text(sql_text))
            rows = result_proxy.fetchall()

            print(f"[search_database] Resultado da query:")
            for i, row in enumerate(rows):
                print(f"  Linha {i + 1}: {row}")

    except Exception as e:
        print(f"[search_database] Erro ao executar a query SQL: {e}")

    return (sql_text, rows)

prompt_generator_prompt = PromptTemplate(
    input_variables=["user_request"],
    template="""
Você é um especialista em mapear pedidos do comprador para uma consulta na tabela 'lojas'.

A tabela 'lojas' tem colunas: id, tipo, numero.
 - 'tipo' pode ser 'Roupas', 'Jogos', 'Skate', etc.

O comprador quer: "{user_request}".

Gere, em português, um comando de consulta (NÃO em SQL, mas um texto em linguagem natural)
que será usado pelo pesquisador para encontrar a loja certa na tabela 'lojas'.

Por exemplo, se o comprador quer uma camiseta verde, o comando pode ser:
"Na tabela 'lojas', retorne id, tipo, numero WHERE tipo = 'Roupas'"

Explique brevemente qual 'tipo' corresponde ao que o comprador quer. 
Retorne APENAS o texto que o pesquisador usará, sem explicações adicionais.
"""
)

prompt_generator_chain = LLMChain(
    llm=llm,
    prompt=prompt_generator_prompt,
    verbose=False
)

def get_store_number(buyer_request: str, agent_id: str) -> int:
    """
    1. Check if 'store_number' is cached for this agent_id.
    2. If not cached, run prompt_generator_chain + search_database to find the store.
    3. Cache the store_number, store_id, store_tipo.
    4. Return the store_number.
    """
    # If we already have a store_number, return it
    if "store_number" in agent_cache[agent_id]:
        return agent_cache[agent_id]["store_number"]
    
    # Otherwise, generate a query for 'lojas' using the LLM
    prompt_for_lojas = prompt_generator_chain.run({"user_request": buyer_request})
    sql_store, rows_store = search_database(prompt_for_lojas)

    if not rows_store:
        raise ValueError(f"Nenhuma loja encontrada para: '{buyer_request}'.")

    store_row = None
    for r in rows_store:
        # row is (id, tipo, numero)
        try:
            temp_num = int(r[2])
            store_row = r
            break
        except ValueError:
            continue

    if not store_row:
        raise ValueError("Nenhum 'numero' válido encontrado na tabela 'lojas'.")

    store_id, store_tipo, store_num = store_row
    agent_cache[agent_id]["store_number"] = store_num
    agent_cache[agent_id]["store_id"] = store_id
    agent_cache[agent_id]["store_tipo"] = store_tipo

    return store_num

def get_store_coordinates(store_number: int, agent_id: str):
    if "store_position" in agent_cache[agent_id]:
        return agent_cache[agent_id]["store_position"]

    query = f"Na tabela 'posicao', retorne x,y,z onde numero = {store_number}."
    _, rows = search_database(query)
    if not rows:
        agent_cache[agent_id]["store_position"] = None
        return None

    x, y, z = rows[0]
    coords = (x, y, z)
    agent_cache[agent_id]["store_position"] = coords
    return coords

def get_matching_items(buyer_request: str, store_number: int, agent_id: str):
    if "matching_items" in agent_cache[agent_id]:
        return agent_cache[agent_id]["matching_items"]

    prompt_query = prompt_loja_prompt | llm
    loja_prompt = prompt_query.invoke({"store_number": store_number, "user_request": buyer_request})
    _, rows = search_database(loja_prompt)

    matches = []
    for r in rows:
        try:
            matches.append({
                "produto": r[0], "tipo": r[1], "qtd": int(r[2]),
                "preco": float(r[3]), "tamanho": r[4], "material": r[5], "estampa": r[6]
            })
        except:
            pass

    if matches:
        agent_cache[agent_id]["matching_items"] = matches
        return matches

    # fallback caso nada encontrado
    reference_price = 250.0
    query = f"SELECT preco FROM loja_{store_number} WHERE produto ILIKE '%{buyer_request}%' LIMIT 1"
    _, fallback_rows = search_database(query)
    if fallback_rows:
        try:
            reference_price = float(fallback_rows[0][0])
        except:
            pass

    min_price = reference_price * 0.8
    max_price = reference_price * 1.2

    fallback_result = prompt_loja_fallback_chain | llm
    fallback_prompt = fallback_result.invoke({
        "store_number": store_number,
        "user_request": buyer_request,
        "min_price": min_price,
        "max_price": max_price
    })

    _, rows = search_database(fallback_prompt)
    fallback_matches = []
    for r in rows:
        try:
            fallback_matches.append({
                "produto": r[0], "tipo": r[1], "qtd": int(r[2]),
                "preco": float(r[3]), "tamanho": r[4], "material": r[5], "estampa": r[6]
            })
        except:
            pass

    agent_cache[agent_id]["matching_items"] = fallback_matches
    return fallback_matches

def multi_table_search(buyer_request: str, agent_id: str) -> str:
    lines = []
    try:
        store_number = get_store_number(buyer_request, agent_id)
        store_id = agent_cache[agent_id].get("store_id")
        store_tipo = agent_cache[agent_id].get("store_tipo")

        lines.append(f"Loja encontrada: ID={store_id}, tipo={store_tipo}, numero={store_number}")

        coords = get_store_coordinates(store_number, agent_id)
        if coords:
            x, y, z = coords
            lines.append(f"Posição da loja: x={x}, y={y}, z={z}")
        else:
            lines.append("Posição da loja não cadastrada")

        items = get_matching_items(buyer_request, store_number, agent_id)
        if items:
            lines.append("Itens Disponíveis:")
            for item in items:
                lines.append(
                    f" - {item['produto']} ({item['tipo']}), tamanho={item['tamanho']}, material={item['material']}, estampa={item['estampa']}, qtd={item['qtd']}, R${item['preco']}"
                )
        else:
            lines.append("(Nenhum item encontrado ou recomendado)")

    except ValueError as e:
        lines.append(f"Erro: {str(e)}")

    return "\n".join(lines)
