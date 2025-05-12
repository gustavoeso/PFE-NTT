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
  - id (integer)                    -- Unique store ID
  - tipo (varchar)                 -- Type of store (e.g., Roupas, Jogos, Tênis)
  - numero (numeric)              -- Store number, used to link to loja_{{numero}} tables

TABLE `loja_100`:                 -- Clothing store
  - id SERIAL PRIMARY KEY
  - produto VARCHAR(50)           -- Product name (e.g., Camiseta)
  - tipo VARCHAR(50)              -- Variation (e.g., Preta, Branca)
  - qtd INT                       -- Quantity in stock
  - preco DECIMAL(10,2)           -- Price
  - tamanho VARCHAR(10)           -- Size (e.g., P, M, G, 42)
  - material VARCHAR(50)          -- Material (e.g., Algodão)
  - estampa VARCHAR(3)            -- "Sim" or "Não" for printed design

TABLE `loja_200`:                 -- Video games store
  - id SERIAL PRIMARY KEY
  - produto VARCHAR(100)          -- Game title (e.g., FIFA 23)
  - tipo VARCHAR(50)              -- Genre (e.g., FPS, RPG)
  - qtd INT                       -- Quantity in stock
  - preco DECIMAL(10,2)           -- Price
  - console VARCHAR(50)           -- Console name (e.g., Xbox)

TABLE `loja_300`:                 -- Skate shop
  - id SERIAL PRIMARY KEY
  - produto VARCHAR(50)           -- Product name (e.g., Skate, Capacete)
  - marca VARCHAR(50)             -- Brand (e.g., Vans, Thrasher)
  - tipo VARCHAR(50)              -- Product type (e.g., Elétrico, Proteção)
  - cor VARCHAR(30)               -- Color (e.g., Preto, Azul)
  - qtd INT                       -- Quantity in stock
  - preco DECIMAL(10,2)           -- Price

TABLE `loja_400`:                 -- Shoe store
  - id SERIAL PRIMARY KEY
  - produto VARCHAR(50)           -- Product name (typically "Tênis")
  - marca VARCHAR(50)             -- Brand (e.g., Nike, Adidas, Jordan)
  - tipo VARCHAR(50)              -- Model (e.g., Air Max)
  - cor VARCHAR(30)               -- Color
  - qtd INT                       -- Quantity in stock
  - preco DECIMAL(10,2)           -- Price

TABLE `loja_500`:                 -- Fast food restaurant
  - id SERIAL PRIMARY KEY
  - produto VARCHAR(50)           -- Food item (e.g., Cheeseburger)
  - tipo VARCHAR(50)              -- Variation (e.g., Grande, 6 unidades)
  - qtd INT                       -- Quantity in stock
  - preco DECIMAL(10,2)           -- Price

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
 - 'tipo' pode ser 'Roupas', 'Jogos', 'Skate', 'Tênis', 'WcDonalds'.

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

def generate_sql_for_loja(buyer_request: str, store_number: int, store_tipo: str) -> str:
    store_schema = {
        "Roupas": ["produto", "tipo", "qtd", "preco", "tamanho", "material", "estampa"],
        "Jogos": ["produto", "tipo", "qtd", "preco", "console"],
        "Skate": ["produto", "marca", "tipo", "cor", "qtd", "preco"],
        "Tênis": ["produto", "marca", "tipo", "cor", "qtd", "preco"],
        "WcDonalds": ["produto", "tipo", "qtd", "preco"]
    }

    columns = store_schema.get(store_tipo, ["produto", "tipo", "qtd", "preco"])
    col_string = ", ".join(columns)

    base_query = f"SELECT {col_string} FROM loja_{store_number} WHERE qtd > 0"

    # Geração de filtros com base no pedido
    filter_clauses = []
    if "produto" in columns:
        filter_clauses.append(f"produto ILIKE '%{buyer_request}%'")
    if "tipo" in columns:
        filter_clauses.append(f"tipo ILIKE '%{buyer_request}%'")
    if "marca" in columns:
        filter_clauses.append(f"marca ILIKE '%{buyer_request}%'")

    if filter_clauses:
        filters = " OR ".join(filter_clauses)
        base_query += f" AND ({filters})"

    return base_query


def get_matching_items(buyer_request: str, store_number: int, agent_id: str):
    if "matching_items" in agent_cache[agent_id]:
        return agent_cache[agent_id]["matching_items"]

    store_tipo = agent_cache[agent_id].get("store_tipo", "")
    schema = {
        "Roupas": ["produto", "tipo", "qtd", "preco", "tamanho", "material", "estampa"],
        "Jogos": ["produto", "tipo", "qtd", "preco", "console"],
        "Skate": ["produto", "marca", "tipo", "cor", "qtd", "preco"],
        "Tênis": ["produto", "marca", "tipo", "cor", "qtd", "preco"],
        "WcDonalds": ["produto", "tipo", "qtd", "preco"]
    }
    columns = schema.get(store_tipo, ["produto", "tipo", "qtd", "preco"])
    col_string = ", ".join(columns)

    # 🔎 1. Buscar tudo que está no estoque da loja
    full_query = f"SELECT {col_string} FROM loja_{store_number} WHERE qtd > 0"
    _, all_rows = search_database(full_query)
    all_items = [{col: row[i] for i, col in enumerate(columns)} for row in all_rows]
    agent_cache[agent_id]["all_items_in_stock"] = all_items

    # 🔍 2. Tentar busca com filtro usando o pedido original
    loja_prompt = generate_sql_for_loja(buyer_request, store_number, store_tipo)
    _, rows = search_database(loja_prompt)

    matches = []
    for r in rows:
        item = {col: r[i] for i, col in enumerate(columns)}
        matches.append(item)

    if matches:
        agent_cache[agent_id]["matching_items"] = matches
        return matches

    # 💡 3. Fallback inteligente por similaridade textual com o estoque
    buyer_request_lower = buyer_request.lower()
    fallback_matches = []
    for item in all_items:
        for campo in ["produto", "tipo", "marca"]:
            if campo in item and buyer_request_lower in str(item[campo]).lower():
                fallback_matches.append(item)
                break

    if fallback_matches:
        agent_cache[agent_id]["matching_items"] = fallback_matches
        return fallback_matches

    # 🪙 4. Fallback final com base no preço
    reference_price = 250.0
    preco_query = f"SELECT preco FROM loja_{store_number} WHERE produto ILIKE '%{buyer_request}%' LIMIT 1"
    _, fallback_rows = search_database(preco_query)
    if fallback_rows:
        try:
            reference_price = float(fallback_rows[0][0])
        except:
            pass

    min_price = reference_price * 0.8
    max_price = reference_price * 1.2

    fallback_query = f"""
        SELECT {col_string}
        FROM loja_{store_number}
        WHERE qtd > 0 AND preco BETWEEN {min_price} AND {max_price}
        ORDER BY preco ASC
    """.strip()

    _, rows = search_database(fallback_query)
    for r in rows:
        item = {col: r[i] for i, col in enumerate(columns)}
        fallback_matches.append(item)

    agent_cache[agent_id]["matching_items"] = fallback_matches
    return fallback_matches


def multi_table_search(buyer_request: str, agent_id: str, store_number: int) -> str:
    lines = []
    try:
        store_id = agent_cache[agent_id].get("store_id")
        store_tipo = agent_cache[agent_id].get("store_tipo")

        lines.append(f"Loja encontrada: ID={store_id}, tipo={store_tipo}, numero={store_number}")

        # coords = get_store_coordinates(store_number, agent_id)
        # if coords:
        #     x, y, z = coords
        #     lines.append(f"Posição da loja: x={x}, y={y}, z={z}")
        # else:
        #     lines.append("Posição da loja não cadastrada")

        items = get_matching_items(buyer_request, store_number, agent_id)
        if items:
            lines.append("Itens Disponíveis:")
            for item in items:
                descricao = f" - {item['produto']} ({item['tipo']})"
                if 'tamanho' in item:
                    descricao += f", tamanho={item['tamanho']}"
                if 'material' in item:
                    descricao += f", material={item['material']}"
                if 'estampa' in item:
                    descricao += f", estampa={item['estampa']}"
                if 'marca' in item:
                    descricao += f", marca={item['marca']}"
                if 'cor' in item:
                    descricao += f", cor={item['cor']}"
                if 'console' in item:
                    descricao += f", console={item['console']}"
                descricao += f", qtd={item['qtd']}, R${item['preco']}"
                lines.append(descricao)

        else:
            lines.append("(Nenhum item encontrado ou recomendado)")

    except ValueError as e:
        lines.append(f"Erro: {str(e)}")

    return "\n".join(lines)
