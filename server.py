import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# ----------------- LangChain + SQL Imports -----------------
import openai
from langchain_community.chat_models import ChatOpenAI
from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    PromptTemplate
)
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory

from sqlalchemy import create_engine, text
from langchain_experimental.sql import SQLDatabaseChain
from langchain_community.utilities import SQLDatabase

load_dotenv()

app = Flask(__name__)

#####################################################################
# 1) ENV Setup + LLM
#####################################################################
api_key = os.getenv("OPENAI_API_KEY")
model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-4")

# Base LLM for conversation
openai_llm = ChatOpenAI(
    model_name=model_name,
    openai_api_key=api_key,
    temperature=0.3
)

buyer_seller_llm = ChatOpenAI(
    model_name=model_name,
    openai_api_key=api_key,
    temperature=0
)

#####################################################################
# 2) Database Setup
#####################################################################
db_uri = "postgresql://myuser:mypassword@shopping.cib0gcgyigl5.us-east-1.rds.amazonaws.com:5432/shopping"
engine = create_engine(db_uri)
database = SQLDatabase(engine)

#####################################################################
# 3) SQL Chain for guide DB usage
#####################################################################
llm_for_sql = ChatOpenAI(
    model_name=model_name,
    openai_api_key=api_key,
    temperature=0.0
)

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
    llm=llm_for_sql,
    db=database,
    prompt=sql_prompt,
    verbose=True  # <- mostra o prompt, SQL e resultado no terminal
)


#####################################################################
# 4) Function to search DB, removing backticks and prefix
#####################################################################
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


#####################################################################
# 5) Additional LLM Chains (PromptGenerator, etc.) for Multi-Table
#####################################################################
# This chain helps produce a text query for `lojas` in Portuguese
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
    llm=llm_for_sql,
    prompt=prompt_generator_prompt,
    verbose=False
)

prompt_loja_prompt = PromptTemplate(
    input_variables=["store_number", "user_request"],
    template="""
Você é um especialista em mapear o pedido do comprador para uma consulta na tabela 'loja_{store_number}'.

A tabela 'loja_{store_number}' tem colunas: 
  - produto (texto)
  - tipo (texto)
  - qtd (inteiro)
  - preco (decimal)
  - tamanho (texto)
  - material (texto)
  - estampa (texto: 'Sim' ou 'Não')

O comprador quer: "{user_request}"

Por exemplo, uma Camiseta Verde ficaria assim na tabela da loja_100:
-produto = 'Camiseta'
-tipo = 'Verde'
-qtd = 10
-preco = 25.00
-tamanho = 'M'
-material = 'Algodão'
-estampa = 'Sim'


Gere UMA LINHA de texto (em português) no formato:

Na tabela 'loja_{store_number}', retorne produto, tipo, qtd, preco, tamanho, material, estampa
WHERE produto ILIKE '%...%' AND tipo ILIKE '%...%' AND qtd > 0;

Use a string do "user_request" no lugar de "...".  
Retorne SOMENTE a linha final, sem explicações adicionais.
"""
)
prompt_loja_chain = LLMChain(
    llm=llm_for_sql,
    prompt=prompt_loja_prompt,
    verbose=False
)

prompt_loja_fallback = PromptTemplate(
    input_variables=["store_number", "user_request", "min_price", "max_price"],
    template="""
Não foi encontrado o item exato "{user_request}" na tabela 'loja_{store_number}' ou está sem estoque.
Gere UMA LINHA de texto (em português), no formato:

Na tabela 'loja_{store_number}', retorne produto, tipo, qtd, preco, tamanho, material, estampa
WHERE qtd > 0 AND preco BETWEEN {min_price} AND {max_price}
ORDER BY preco ASC;

Retorne SOMENTE a linha final, sem explicações.
"""
)
prompt_loja_fallback_chain = LLMChain(
    llm=llm_for_sql,
    prompt=prompt_loja_fallback,
    verbose=False
)


#####################################################################
# 6) The big multi_table_search function
#####################################################################
def multi_table_search(buyer_request: str) -> str:
    """
    1) Generate a text query for 'lojas' using prompt_generator_chain
    2) Convert that text query -> SQL using search_database
    3) Find the store row
    4) Find the store's position in 'posicao'
    5) Query loja_{numero} for items
    6) Return a textual summary
    """
    # Step 1: Generate a prompt for 'lojas'
    prompt_for_lojas = prompt_generator_chain.run({"user_request": buyer_request})

    # Step 2: Actually query 'lojas'
    sql_store, rows_store = search_database(prompt_for_lojas)
    if not rows_store:
        return (
            "=== LOG: StepC -> NENHUMA loja encontrada.\n"
            f"PromptGenerator: {prompt_for_lojas}\n"
            f"SQL Gerado: {sql_store}\n"
            "Sem resultados."
        )

    # find first row with a valid integer in 'numero'
    store_row = None
    for r in rows_store:
        try:
            _ = int(r[2])  # parse
            store_row = r
            break
        except ValueError:
            continue

    if store_row is None:
        # no row had a valid numeric 'numero'
        return (
            "=== LOG: Nenhum 'numero' válido encontrado.\n"
            f"PromptGenerator: {prompt_for_lojas}\n"
            f"SQL Gerado: {sql_store}\n"
            f"Rows: {rows_store}\n"
            "Não foi possível continuar."
        )

    store_info = {
        "id": store_row[0],
        "tipo": store_row[1]
    }
    try:
        store_info["numero"] = int(store_row[2])
    except ValueError:
        return (
            f"=== LOG: Loja tem numero inválido.\n"
            f"Row: {store_row}"
        )

    # Step 3: get store coords from 'posicao' (optional)
    nl_query_pos = f"Na tabela 'posicao', retorne x,y,z onde numero = {store_info['numero']}."
    sql_pos, rows_pos = search_database(nl_query_pos)
    coords = []
    for r in rows_pos:
        try:
            coords.append({"x": float(r[0]), "y": float(r[1]), "z": float(r[2])})
        except (TypeError, ValueError):
            pass

    # Step 4: check in loja_{numero}
    store_number = store_info["numero"]

    # 4A) Primary attempt
    prompt_for_loja = prompt_loja_chain.run({
        "store_number": store_number,
        "user_request": buyer_request
    })
    sql_loja, rows_loja = search_database(prompt_for_loja)

    matching_items = []
    for r in rows_loja:
        try:
            matching_items.append({
                "produto": r[0],
                "tipo": r[1],
                "qtd": int(r[2]),
                "preco": float(r[3]),
                "tamanho": r[4],
                "material": r[5],
                "estampa": r[6]
            })
        except (IndexError, ValueError):
            continue

    exact_match_in_stock = matching_items
    recommended_items = []
    fallback_prompt = ""
    fallback_sql = ""

    # 4B) Fallback if no exact match
    if not exact_match_in_stock:
        reference_price = 250.0
        ignore_stock_query = f"""
        SELECT produto, tipo, qtd, preco, tamanho, material, estampa
        FROM loja_{store_number}
        WHERE produto ILIKE '%{buyer_request}%' AND tipo ILIKE '%{buyer_request}%'
        LIMIT 1
        """
        _, ignore_stock_rows = search_database(ignore_stock_query)
        if ignore_stock_rows:
            row0 = ignore_stock_rows[0]
            try:
                reference_price = float(row0[3])
            except (IndexError, ValueError):
                reference_price = 250.0

        min_price = reference_price * 0.8
        max_price = reference_price * 1.2

        fallback_prompt = prompt_loja_fallback_chain.run({
            "store_number": store_number,
            "user_request": buyer_request,
            "min_price": min_price,
            "max_price": max_price
        })
        fallback_sql, rows_loja_fallback = search_database(fallback_prompt)
        for r in rows_loja_fallback:
            try:
                recommended_items.append({
                    "produto": r[0],
                    "tipo": r[1],
                    "qtd": int(r[2]),
                    "preco": float(r[3]),
                    "tamanho": r[4],
                    "material": r[5],
                    "estampa": r[6]
                })
            except (IndexError, ValueError):
                continue

    final_items = exact_match_in_stock if exact_match_in_stock else recommended_items

    # Step 5) Summaries
    summary_lines = []
    summary_lines.append("=== RESULTADO DA PESQUISA MULTI-TABELA ===\n")
    summary_lines.append(f"Comprador quer: {buyer_request}\n")
    summary_lines.append("LOJA ESCOLHIDA:")
    summary_lines.append(f" - ID: {store_info['id']}, tipo: {store_info['tipo']}, numero: {store_info['numero']}")
    summary_lines.append(f" - SQL p/ 'lojas': {sql_store}")
    summary_lines.append("POSIÇÃO DA LOJA (x,y,z):")
    if coords:
        for c in coords:
            summary_lines.append(f"   x={c['x']}, y={c['y']}, z={c['z']}")
    else:
        summary_lines.append("   (não encontrado)\n")
    summary_lines.append(f"\nTABELA loja_{store_number} => SQL exato: {sql_loja}")
    if not exact_match_in_stock:
        summary_lines.append(f"(Sem match exato) => fallback prompt: {fallback_prompt}")
        summary_lines.append(f"=> fallback SQL: {fallback_sql}")

    if final_items:
        summary_lines.append("Itens Disponíveis:")
        for it in final_items:
            summary_lines.append(
                f"   - {it['produto']} ({it['tipo']}), "
                f"tamanho={it['tamanho']}, material={it['material']}, estampa={it['estampa']}, "
                f"qtd={it['qtd']}, R${it['preco']}"
            )
    else:
        summary_lines.append("(Nenhum item encontrado ou recomendado)")

    return "\n".join(summary_lines)


#####################################################################
# 7) BuyerChain & SellerChain
#####################################################################
buyer_memory = ConversationBufferMemory(
    memory_key="history",
    return_messages=True
)

########################################
# BuyerChain
########################################
buyer_system_template = """
Você é o Buyer (comprador) em uma loja no shopping.
Não se identifique como IA.

Objetivo:
- Você quer comprar alguma coisa ou não.
- Você pode fazer NO MÁXIMO 3 perguntas sobre preço, quantidade, material, tamanho ou estampa.
- Depois de 3 perguntas, OBRIGATORIAMENTE deve decidir:
  - Se for comprar: escreva EXATAMENTE "Vou levar"
  - Se não for comprar: escreva EXATAMENTE "Não vou levar"
- Você deve querer apenas aquilo que foi designado a você comprar e nada mais, não faça perguntas sobre outros produtos.

Histórico da conversa até agora:
{history}
"""

buyer_human_template = """
A última fala do Vendedor (Seller) foi:
{seller_utterance}

Agora responda como BUYER:
1. Se ainda não atingiu 3 perguntas e não decidiu, faça sua pergunta ou observação.
2. Se já fez 3 perguntas, OBRIGATORIAMENTE diga "Vou levar" ou "Não vou levar".
3. Não se identifique como IA.
"""

buyer_system_msg = SystemMessagePromptTemplate.from_template(buyer_system_template)
buyer_human_msg = HumanMessagePromptTemplate.from_template(buyer_human_template)

buyer_prompt = ChatPromptTemplate(
    input_variables=["history", "seller_utterance"],
    messages=[buyer_system_msg, buyer_human_msg]
)

buyer_chain = LLMChain(
    llm=buyer_seller_llm,
    prompt=buyer_prompt,
    memory=buyer_memory,
    verbose=False
)

########################################
# SellerChain
########################################
seller_system_template = """
Você é o Seller (vendedor) em uma loja no shopping.
Não se identifique como IA.

Objetivo:
- Vender produtos (ou responder perguntas) usando dados reais do estoque.
- Responda perguntas do Buyer sobre produto, preço, quantidade, material, tamanho ou estampa.
- Caso tenha estampa, informe que é o logo da Nike.
- Política de troca e devolução: 30 dias.
- Garantia de 1 ano.
- Aceita cartões de crédito e débito, dinheiro e PIX.
- Não encerre a conversa você mesmo.
- Não sugira outros produtos.

Estoque disponível (buscado com multi-table logic):
{stock_info}

Histórico da conversa até agora:
{history}
"""

seller_human_template = """
A última fala do Comprador (Buyer) foi:
{buyer_utterance}

Agora responda como SELLER:
1. Se possível, use as informações de 'Estoque' acima para dar detalhes reais.
2. Não se identifique como IA.
3. Não encerre a conversa. Aguarde o Buyer decidir com "Vou levar" ou "Não vou levar".
"""

seller_system_msg = SystemMessagePromptTemplate.from_template(seller_system_template)
seller_human_msg = HumanMessagePromptTemplate.from_template(seller_human_template)

seller_prompt = ChatPromptTemplate(
    input_variables=["history", "buyer_utterance", "stock_info"],
    messages=[seller_system_msg, seller_human_msg]
)

seller_chain = LLMChain(
    llm=buyer_seller_llm,
    prompt=seller_prompt,
    verbose=False
)


#####################################################################
# 8) Flask Endpoints
#####################################################################

@app.route('/startApplication', methods=['POST'])
def start_application():
    """
    Called once at the start of the Unity Client to 'initialize' if needed.
    """
    buyer_memory.clear()
    return jsonify({"response": "Application started! Buyer memory cleared."})


@app.route('/request/guide', methods=['POST'])
def guide_request():
    """
    Endpoint for the "guide" logic:
    The Unity 'Client' might say: "Estou procurando o produto X"
    This endpoint finds the store in 'lojas' and the store position in 'posicao'.
    
    We now use prompt_generator_chain + search_database 
    to let the LLM figure out the 'tipo' or relevant columns in 'lojas'.
    """
    data = request.get_json()
    print(data)
    buyer_request = data.get("prompt", "")

    # 1) Use prompt_generator_chain to produce a "lojas" query in PT-BR
    prompt_for_lojas = prompt_generator_chain.run({"user_request": buyer_request})
    # 2) Pass that to search_database
    sql_store, rows_store = search_database(prompt_for_lojas)
    if not rows_store:
        return jsonify({"response": "Nenhuma loja encontrada para esse item."})

    # pick first row with a valid store_num
    store_id, store_tipo, store_num = None, None, None
    for row in rows_store:
        # row is (id, tipo, numero)
        try:
            temp_num = int(row[2])
            store_id = row[0]
            store_tipo = row[1]
            store_num = temp_num
            break
        except:
            continue

    if store_num is None:
        return jsonify({"response": "Nenhuma loja com número válido encontrada."})

    # get the position (posicao table)
    sql_pos, rows_pos = search_database(
        f"Na tabela 'posicao', retorne x,y,z onde numero = {store_num}."
    )
    if not rows_pos:
        return jsonify({
            "response": f"Loja {store_num} encontrada (tipo={store_tipo}), mas posição não cadastrada."
        })

    x, y, z = rows_pos[0]
    text_response = (
        f"Loja encontrada: tipo '{store_tipo}' número {store_num}. "
        f"Localização: x={x}, y={y}, z={z}."
    )
    return jsonify({"response": text_response})


@app.route('/request/store', methods=['POST'])
def store_request():
    """
    Endpoint for the "store/seller" logic:
    The user (client) says something like "Quero comprar Camiseta branca"
    We'll do the multi_table_search to see what's in stock, then pass that info
    to the seller chain for a final response.
    """
    data = request.get_json()
    prompt = data.get("prompt", "")
    # speaker = data.get("speaker", "")  # Typically 'client' – unused here

    # 1) multi_table_search to get inventory details
    stock_info = multi_table_search(prompt)

    # 2) feed that into the seller chain
    seller_response = seller_chain.run(
        buyer_utterance=prompt,
        stock_info=stock_info,
        history=buyer_memory.load_memory_variables({})["history"]
    )

    # Save the seller's response in buyer memory, so next Buyer turn can refer to it
    buyer_memory.save_context({"input": ""}, {"output": seller_response})

    return jsonify({"response": seller_response})


@app.route('/request/client', methods=['POST'])
def client_request():
    """
    Endpoint for the "client/buyer" logic:
    If your Unity code wants to have the Buyer respond to the last Seller message,
    call this with the JSON: { "prompt": "...", "speaker": "seller" } for example.
    """
    data = request.get_json()
    prompt = data.get("prompt", "")

    # We'll treat the prompt as "seller_utterance" (the last message from the store).
    buyer_reply = buyer_chain.run(seller_utterance=prompt)
    return jsonify({"response": buyer_reply})


if __name__ == '__main__':
    # In production, use a proper WSGI server. For dev, debug=True is OK.
    app.run(host='0.0.0.0', port=8000, debug=True)