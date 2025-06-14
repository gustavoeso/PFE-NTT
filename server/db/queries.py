from langchain_community.utilities import SQLDatabase
from langchain_experimental.sql import SQLDatabaseChain
from langchain.prompts import PromptTemplate
from sqlalchemy import text
from server.db.engine import engine
from server.config import OPENAI_API_KEY, OPENAI_MODEL_NAME
from langchain_openai import ChatOpenAI
from server.utils.memory import agent_cache, productIndex, stores
from server.llm.prompts import prompt_loja_prompt, prompt_loja_fallback_chain
from langchain.chains import LLMChain
import unicodedata
import time
import json

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
  - id SERIAL PRIMARY KEY         -- Product ID
  - produto VARCHAR(50)           -- Product name (e.g., Camiseta)
  - tipo VARCHAR(50)              -- Variation (e.g., Preta, Branca)
  - qtd INT                       -- Quantity in stock
  - preco DECIMAL(10,2)           -- Price
  - tamanho VARCHAR(10)           -- Size (e.g., P, M, G, 42)
  - material VARCHAR(50)          -- Material (e.g., Algodão)
  - estampa VARCHAR(3)            -- "Sim" or "Não" for printed design

TABLE `loja_200`:                 -- Video games store
  - id SERIAL PRIMARY KEY         -- Product ID
  - produto VARCHAR(100)          -- Game title (e.g., FIFA 23)
  - tipo VARCHAR(50)              -- Genre (e.g., FPS, RPG)
  - qtd INT                       -- Quantity in stock
  - preco DECIMAL(10,2)           -- Price
  - console VARCHAR(50)           -- Console name (e.g., Xbox)

TABLE `loja_300`:                 -- Skate shop
  - id SERIAL PRIMARY KEY         -- Product ID
  - produto VARCHAR(50)           -- Product name (e.g., Skate, Capacete)
  - marca VARCHAR(50)             -- Brand (e.g., Vans, Thrasher)
  - tipo VARCHAR(50)              -- Product type (e.g., Elétrico, Proteção)
  - cor VARCHAR(30)               -- Color (e.g., Preto, Azul)
  - qtd INT                       -- Quantity in stock
  - preco DECIMAL(10,2)           -- Price

TABLE `loja_400`:                 -- Shoe store
  - id SERIAL PRIMARY KEY         -- Product ID
  - produto VARCHAR(50)           -- Product name (typically "Tênis")
  - marca VARCHAR(50)             -- Brand (e.g., Nike, Adidas, Jordan)
  - tipo VARCHAR(50)              -- Model (e.g., Air Max)
  - cor VARCHAR(30)               -- Color
  - qtd INT                       -- Quantity in stock
  - preco DECIMAL(10,2)           -- Price

TABLE `loja_500`:                 -- Fast food restaurant
  - id SERIAL PRIMARY KEY         -- Product ID
  - produto VARCHAR(50)           -- Food item (e.g., Cheeseburger)
  - tipo VARCHAR(50)              -- Variation (e.g., Grande, 6 unidades)
  - qtd INT                       -- Quantity in stock
  - preco DECIMAL(10,2)           -- Price

TABLE `loja_600`:                 -- Bookstore 
  - id (serial)                   -- Product ID
  - produto (text)                -- Book title
  - autor (text)                  -- Author of the book
  - genero (text)                 -- Genre of the book
  - preco (numeric)               -- Price in BRL
  - idioma (text)                 -- Language
  - qtd (int)                     -- Quantity in stock

TABLE `loja_700`:                 -- Electronics store
  - id (serial)                   -- Product ID
  - produto (text)                -- Product category (e.g., Smartphone, Monitor)
  - tipo (text)                   -- Specific model (e.g., Galaxy S24, iPhone 15)
  - marca (text)                  -- Brand name
  - preco (numeric)               -- Price in BRL
  - garantia (text)               -- Warranty duration
  - qtd (int)                     -- Quantity in stock
  

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

def medir_tempo(func):
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        resultado = func(*args, **kwargs)
        elapsed_time = time.perf_counter() - start_time
        print(f"[{func.__name__}] Tempo de execução: {elapsed_time:.3f} segundos")
        return resultado
    return wrapper

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

def remove_acentos(texto):
    return ''.join(
        c for c in unicodedata.normalize('NFKD', texto)
        if not unicodedata.combining(c)
    )

def find_all_stores():
    """
    Find all stores in the database and return them as a list of tuples.
    Each tuple contains (id, tipo, numero).
    """
    query = "SELECT tipo, numero, id FROM lojas"
    try:
        with engine.connect() as conn:
            result_proxy = conn.execute(text(query))
            rows = result_proxy.fetchall()
            for row in rows:
                store_tipo = remove_acentos(row[0])
                store_num = row[1]
                store_id = row[2]
                stores[store_tipo] = [store_num, store_id]
            print("stores:", stores)
            return
    except Exception as e:
        print(f"[find_all_stores] Error: {e}")
        return
    
@medir_tempo
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

@medir_tempo
def get_store_tipo(buyer_request: str) -> str:
    """
    1. Check if 'store_number' is cached for this agent_id.
    2. If not cached, run prompt_generator_chain + search_database to find the store.
    3. Cache the store_number, store_id, store_tipo.
    4. Return the store_number.
    """
    
    prompt_for_lojas = prompt_generator_chain.run({"user_request": buyer_request})
    _, rows_store = search_database(prompt_for_lojas)

    if not rows_store:
        raise ValueError(f"Nenhuma loja encontrada para: '{buyer_request}'.")

    store_row = None
    for r in rows_store:
        try:
            store_row = r
            break
        except ValueError:
            continue

    if not store_row:
        raise ValueError("Nenhum 'numero' válido encontrado na tabela 'lojas'.")

    _, store_tipo, _ = store_row

    return remove_acentos(store_tipo)

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

# Prompt para decompor pedido em campos da loja
atributo_parser_prompt = PromptTemplate(
    input_variables=["pedido", "campos"],
    template="""
Você é um assistente inteligente que separa um pedido de compra em campos da tabela.

Pedido: "{pedido}"

Campos da tabela disponíveis: {campos}

Responda com um JSON mapeando os campos relevantes. Ignore os campos que não aparecem no pedido.
Exemplo: 
Entrada: "camiseta branca algodão"
Saída: {{"produto": "camiseta", "tipo": "branca", "material": "algodão"}}

Agora responda com o JSON para o pedido:
"""
)

atributo_parser_chain = LLMChain(llm=llm, prompt=atributo_parser_prompt)

@medir_tempo
def generate_sql_for_loja(buyer_request: str, store_number: int, store_tipo: str) -> str:
    store_schema = {
        "Roupas": ["produto", "tipo", "qtd", "preco", "tamanho", "material", "estampa"],
        "Jogos": ["produto", "tipo", "qtd", "preco", "console"],
        "Skate": ["produto", "marca", "tipo", "cor", "qtd", "preco"],
        "Tênis": ["produto", "marca", "tipo", "cor", "qtd", "preco"],
        "WcDonalds": ["produto", "tipo", "qtd", "preco"],
        "Livros": ["produto", "autor", "genero", "preco", "idioma", "qtd"],
        "Eletronicos": ["produto", "tipo", "marca", "preco", "garantia", "qtd"]
    }

    columns = store_schema.get(store_tipo, ["produto", "tipo", "qtd", "preco"])
    col_string = ", ".join(columns)
    base_query = f"SELECT {col_string} FROM loja_{store_number} WHERE qtd > 0"

    # 🧠 Tentar decompor o pedido nos campos certos usando LLM
    atributos = atributo_parser_chain.run({
        "pedido": buyer_request,
        "campos": ", ".join(columns)
    })

    try:
        atributos_dict = json.loads(atributos)
    except Exception as e:
        print(f"[generate_sql_for_loja] Falha ao converter JSON: {e}\nEntrada: {atributos}")
        atributos_dict = {}

    filter_clauses = []
    for campo, valor in atributos_dict.items():
        if campo in columns:
            filter_clauses.append(f"{campo} ILIKE '%{valor}%'")

    if filter_clauses:
        filters = " AND ".join(filter_clauses)
        base_query += f" AND ({filters})"

    return base_query

@medir_tempo
def get_matching_items(buyer_request: str, store_description: str, agent_id: str):
    if "matching_items" in agent_cache[agent_id]:
        if store_description in agent_cache[agent_id]["matching_items"]:
            return agent_cache[agent_id]["matching_items"][store_description]
    else:
        agent_cache[agent_id]["matching_items"] = {}

    store_tipo = store_description
    schema = {
        "Roupas": ["produto", "tipo", "qtd", "preco", "tamanho", "material", "estampa"],
        "Jogos": ["produto", "tipo", "qtd", "preco", "console"],
        "Skate": ["produto", "marca", "tipo", "cor", "qtd", "preco"],
        "Tênis": ["produto", "marca", "tipo", "cor", "qtd", "preco"],
        "WcDonalds": ["produto", "tipo", "qtd", "preco"]
    }
    store_number = stores[store_tipo][0]
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
        agent_cache[agent_id]["matching_items"][store_description] = matches
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
        agent_cache[agent_id]["matching_items"][store_description] = fallback_matches
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

    agent_cache[agent_id]["matching_items"][store_description] = fallback_matches
    return fallback_matches

@medir_tempo
def multi_table_search(buyer_request: str, agent_id: str, store_description: str) -> str:
    lines = []
    try:
        store_number = stores[store_description][0]
        store_id = stores[store_description][1]

        lines.append(f"Loja encontrada: ID={store_id}, tipo={store_description}, numero={store_number}")

        items = get_matching_items(buyer_request, store_description, agent_id)
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
