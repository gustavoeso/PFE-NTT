from langchain_community.utilities import SQLDatabase
from langchain_experimental.sql import SQLDatabaseChain
from langchain.prompts import PromptTemplate
from sqlalchemy import text
from server.db.engine import sync_engine
from server.config import OPENAI_API_KEY, OPENAI_MODEL_NAME
from langchain_openai import ChatOpenAI
from langchain_core.runnables import Runnable
from server.utils.memory import agent_cache
from server.llm.prompts import prompt_generator_prompt, prompt_loja_prompt, prompt_loja_fallback_chain

# Setup

database = SQLDatabase(sync_engine)
llm = ChatOpenAI(model_name=OPENAI_MODEL_NAME, openai_api_key=OPENAI_API_KEY, temperature=0.0)

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
  - produto (varchar)
  - tipo (varchar)
  - qtd (int)
  - preco (decimal)
  - tamanho (varchar)
  - material (varchar)
  - estampa (varchar)

TABLE `loja_105`:
  - produto (varchar)
  - tipo (varchar)
  - qtd (int)
  - preco (decimal)
  - console (varchar)

User Question: {input}
SQLQuery:
"""

sql_prompt = PromptTemplate(input_variables=["input"], template=CUSTOM_SQL_PROMPT)
sql_chain = SQLDatabaseChain.from_llm(llm=llm, db=database, prompt=sql_prompt, verbose=True)

def search_database(nl_query: str):
    try:
        chain_output = sql_chain.invoke({"query": nl_query})
    except Exception as e:
        print(f"[search_database] Error generating SQL: {e}")
        return ("", [])

    raw_result = chain_output.get("result", "")
    if not raw_result:
        return ("", [])

    sql_text = raw_result.replace("SQLQuery:", "").replace("```", "").strip()
    print(f"[search_database] SQL Gerado:\n{sql_text}")

    rows = []
    try:
        with sync_engine.connect() as conn:
            result_proxy = conn.execute(text(sql_text))
            rows = result_proxy.fetchall()
    except Exception as e:
        print(f"[search_database] Erro ao executar a query SQL: {e}")

    return (sql_text, rows)

def get_store_number(buyer_request: str, agent_id: str) -> int:
    if "store_number" in agent_cache[agent_id]:
        return agent_cache[agent_id]["store_number"]

    prompt_for_lojas = prompt_generator_prompt | llm
    loja_query = prompt_for_lojas.invoke({"user_request": buyer_request})
    sql_store, rows_store = search_database(loja_query)

    if not rows_store:
        raise ValueError(f"Nenhuma loja encontrada para: '{buyer_request}'")

    for r in rows_store:
        try:
            store_id, store_tipo, store_num = r
            store_num = int(store_num)
            break
        except:
            continue
    else:
        raise ValueError("Nenhum número de loja válido encontrado.")

    agent_cache[agent_id].update({
        "store_number": store_num,
        "store_id": store_id,
        "store_tipo": store_tipo
    })

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
