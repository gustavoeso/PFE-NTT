import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from collections import defaultdict

# ----------------- LangChain + SQL Imports -----------------
import openai
from langchain_community.chat_models import ChatOpenAI
from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    PromptTemplate
)
from langchain_core.output_parsers import PydanticOutputParser
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory

from sqlalchemy import create_engine, text
from langchain_experimental.sql import SQLDatabaseChain
from langchain_community.utilities import SQLDatabase
from pydantic import BaseModel

load_dotenv()

app = Flask(__name__)

#####################################################################
# 1) ENV Setup + LLM
#####################################################################
api_key = os.getenv("OPENAI_API_KEY")
model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-4o")

# Base LLM for conversation
openai_llm = ChatOpenAI(
    model_name=model_name,
    openai_api_key=api_key,
    temperature=0.3
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
    produto VARCHAR(100),
    tipo VARCHAR(50),
    qtd INT,
    preco DECIMAL(10,2),
    console VARCHAR(50)

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
    verbose=True  # shows prompt, SQL, and results in terminal
)


#####################################################################
# 4) Function to search DB
#####################################################################
def search_database(nl_query: str):
    """
    Use the sql_chain to turn natural language into SQL, then execute it.
    Returns (sql_text, rows).
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
# Gera texto de query para a tabela 'lojas'
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

Por exemplo, uma Camiseta Verde ficaria assim:
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
# 6) Server-Side Cache
#####################################################################
agent_cache = defaultdict(dict)

#####################################################################
# 6.1) Helper Functions to Retrieve Data with Caching
#####################################################################

def get_store_number(buyer_request: str, agent_id: str) -> int:
    # Se já temos store_number, retorna
    if "store_number" in agent_cache[agent_id]:
        return agent_cache[agent_id]["store_number"]

    prompt_for_lojas = prompt_generator_chain.run({"user_request": buyer_request})
    sql_store, rows_store = search_database(prompt_for_lojas)

    if not rows_store:
        raise ValueError(f"Nenhuma loja encontrada para: '{buyer_request}'.")

    store_row = None
    for r in rows_store:
        # (id, tipo, numero)
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

    nl_query_pos = f"Na tabela 'posicao', retorne x,y,z onde numero = {store_number}."
    sql_pos, rows_pos = search_database(nl_query_pos)
    if not rows_pos:
        agent_cache[agent_id]["store_position"] = None
        return None

    x, y, z = rows_pos[0]
    coords = (x, y, z)
    agent_cache[agent_id]["store_position"] = coords
    return coords

def get_matching_items(buyer_request: str, store_number: int, agent_id: str):
    if "matching_items" in agent_cache[agent_id]:
        return agent_cache[agent_id]["matching_items"]

    # Tenta match exato
    prompt_for_loja = prompt_loja_chain.run({
        "store_number": store_number,
        "user_request": buyer_request
    })
    sql_loja, rows_loja = search_database(prompt_for_loja)

    exact_matches = []
    for r in rows_loja:
        try:
            exact_matches.append({
                "produto": r[0],
                "tipo": r[1],
                "qtd": int(r[2]),
                "preco": float(r[3]),
                "tamanho": r[4],
                "material": r[5],
                "estampa": r[6]
            })
        except (IndexError, ValueError):
            pass

    if exact_matches:
        agent_cache[agent_id]["matching_items"] = exact_matches
        return exact_matches

    # Fallback
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
            pass

    min_price = reference_price * 0.8
    max_price = reference_price * 1.2

    fallback_prompt = prompt_loja_fallback_chain.run({
        "store_number": store_number,
        "user_request": buyer_request,
        "min_price": min_price,
        "max_price": max_price
    })
    fallback_sql, rows_loja_fallback = search_database(fallback_prompt)

    recommended_items = []
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
            pass

    agent_cache[agent_id]["matching_items"] = recommended_items
    return recommended_items

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

        # Fetch matching or fallback items
        final_items = get_matching_items(buyer_request, store_number, agent_id)
        if final_items:
            lines.append("Itens Disponíveis:")
            for it in final_items:
                lines.append(
                    f"   - {it['produto']} ({it['tipo']}), "
                    f"tamanho={it['tamanho']}, material={it['material']}, "
                    f"estampa={it['estampa']}, qtd={it['qtd']}, R${it['preco']}"
                )
        else:
            lines.append("(Nenhum item encontrado ou recomendado)")

    except ValueError as e:
        lines.append(f"Erro: {str(e)}")

    return "\n".join(lines)


#####################################################################
# 7) SetBuyerPreferences + Model + Memory
#####################################################################

@app.route('/setBuyerPreferences', methods=['POST'])
def set_buyer_preferences():
    data = request.get_json()

    print("[setBuyerPreferences] Recebi JSON:", data)
    
    agent_id = data.get("agent_id", "default_agent")
    desired_item = data.get("desired_item", "camiseta branca")
    max_price = data.get("max_price", 60)

    agent_cache[agent_id]["desired_item"] = desired_item
    agent_cache[agent_id]["max_price"] = max_price

    return jsonify({"response": f"Preferencias salvas: item={desired_item}, max={max_price}."})

class AgentResponse(BaseModel):
    answer: str
    final_offer: bool

parser = PydanticOutputParser(pydantic_object=AgentResponse)

# Memória para conversa do Buyer (para o LLM relembrar contexto)
buyer_memory = ConversationBufferMemory(
    memory_key="history",
    return_messages=True
)

########################################
# SellerChain (mantemos como antes)
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

Responda com um JSON contendo os campos:
{format_instructions}

Em final_offer, responda se a resposta é uma oferta conclusiva para o comprador decidir em relação ao produto.
- Se for uma oferta, use "final_offer": true.
- Se não for uma oferta, use "final_offer": false.
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
    partial_variables={"format_instructions": parser.get_format_instructions()},
    messages=[seller_system_msg, seller_human_msg]
)

seller_chain = LLMChain(
    llm=openai_llm,
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
    Clears the buyer memory and also clears the agent cache for that user.
    """
    data = request.get_json()
    agent_id = data.get("agent_id", "default_agent")

    # Clear global conversation memory
    buyer_memory.clear()

    # Clear server-side cache for this agent
    agent_cache[agent_id].clear()

    return jsonify({"response": f"Application started! Buyer memory cleared for agent_id={agent_id}."})

@app.route('/request/guide', methods=['POST'])
def guide_request():
    data = request.get_json()
    buyer_request = data.get("prompt", "")
    agent_id = data.get("agent_id", "default_agent")

    try:
        store_number = get_store_number(buyer_request, agent_id)
        store_id = agent_cache[agent_id].get("store_id")
        store_tipo = agent_cache[agent_id].get("store_tipo")

        coords = get_store_coordinates(store_number, agent_id)
        if coords:
            x, y, z = coords
            answer = (
                f"Loja encontrada: id={store_id}, tipo='{store_tipo}', número={store_number}. "
                f"Localização: x={x}, y={y}, z={z}."
            )
        else:
            answer = (
                f"Loja encontrada: id={store_id}, tipo='{store_tipo}', número={store_number}, "
                "mas posição não cadastrada."
            )

        response = AgentResponse(answer=answer, final_offer=False)
        return jsonify(response.dict())

    except ValueError as e:
        response = AgentResponse(answer=str(e), final_offer=True)
        return jsonify(response.dict())

@app.route('/request/store', methods=['POST'])
def store_request():
    data = request.get_json()
    prompt = data.get("prompt", "")
    agent_id = data.get("agent_id", "default_agent")

    # 1) multi_table_search to get inventory details
    stock_info = multi_table_search(prompt, agent_id)

    # 2) Chamar SellerChain
    seller_response_raw = seller_chain.run(
        buyer_utterance=prompt,
        stock_info=stock_info,
        history=buyer_memory.load_memory_variables({})["history"]
    )
    seller_response = parser.parse(seller_response_raw)

    # 3) Save only the answer in memory
    buyer_memory.save_context({"input": ""}, {"output": seller_response.answer})

    return jsonify(seller_response.dict())

@app.route('/request/client', methods=['POST'])
def client_request():
    data = request.get_json()
    prompt = data.get("prompt", "")
    agent_id = data.get("agent_id", "default_agent")

    # 1) Recuperar item e preço do agent_cache
    desired_item = agent_cache[agent_id].get("desired_item", "camiseta branca")
    max_price = agent_cache[agent_id].get("max_price", 60)

    # 2) Montar prompt dinâmico do Buyer
    dynamic_buyer_system_template = f"""
    Você é o Buyer (comprador) em uma loja no shopping.
    Não se identifique como IA.

    Objetivo:
    - Você quer comprar alguma coisa ou não.
    - Você pode fazer NO MÁXIMO 3 perguntas sobre preço, quantidade, material, tamanho ou estampa.
    - Depois de 3 perguntas, OBRIGATORIAMENTE deve decidir:
        - Se for comprar: escreva EXATAMENTE "Vou levar"
        - Se não for comprar: escreva EXATAMENTE "Não vou levar"
    - Você deve querer apenas aquilo que foi designado a você comprar e nada mais, não faça perguntas sobre outros produtos.
    - Se encontrar {desired_item} por até R$ {max_price:.2f}, você tende a comprar.

    Histórico da conversa até agora:
    {{history}}

    Responda com um JSON contendo os campos:
    {{format_instructions}}
    """

    print("=== [DEBUG] Buyer System Prompt Dinâmico ===")
    print(dynamic_buyer_system_template)
    print("============================================")

    # 3) Construir system/human
    buyer_system_msg = SystemMessagePromptTemplate.from_template(dynamic_buyer_system_template)

    # Fazemos um template fixo para a fala do Seller:
    buyer_human_template = """
A última fala do Vendedor (Seller) foi:
{seller_utterance}

Agora responda como BUYER:
1. Se ainda não atingiu 3 perguntas e não decidiu, faça sua pergunta ou observação.
2. Se já fez 3 perguntas, OBRIGATORIAMENTE diga "Vou levar" ou "Não vou levar".
3. Não se identifique como IA.
"""
    buyer_human_msg = HumanMessagePromptTemplate.from_template(buyer_human_template)

    dynamic_buyer_prompt = ChatPromptTemplate(
        input_variables=["history", "seller_utterance"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
        messages=[buyer_system_msg, buyer_human_msg]
    )

    # 4) Criar chain temporária
    temp_buyer_chain = LLMChain(
        llm=openai_llm,
        prompt=dynamic_buyer_prompt,
        memory=buyer_memory,
        verbose=False
    )

    # 5) Gerar resposta
    buyer_response_raw = temp_buyer_chain.run(seller_utterance=prompt)

    # (Opcional) Logar a resposta bruta
    print("=== [DEBUG] Buyer LLM Raw Response ===")
    print(buyer_response_raw)
    print("======================================")

    buyer_response = parser.parse(buyer_response_raw)
    return jsonify(buyer_response.dict())

@app.route('/resumoOferta', methods=['POST'])
def resumo_oferta():
    """
    Gera um resumo amigável da conversa usando o histórico do buyer.
    """
    data = request.get_json()
    agent_id = data.get("agent_id", "default_agent")

    history = buyer_memory.load_memory_variables({}).get("history", [])

    print("=== Histórico da conversa ===")
    for msg in history:
        print(f"{msg.type.upper()}: {msg.content}")

    # Summarizing prompt
    resumo_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(
            "Você é um assistente que resume uma conversa de compra em uma frase clara e amigável. Você DEVE retornar o valor do produto que o usuário deseja."
        ),
        HumanMessagePromptTemplate.from_template(
            "Resuma a seguinte conversa de compra:\n\n{conversa}"
        )
    ])

    conversa_texto = "\n".join(f"{msg.type.upper()}: {msg.content}" for msg in history)

    chain = LLMChain(
        llm=openai_llm,
        prompt=resumo_prompt,
        verbose=False
    )

    resumo = chain.run(conversa=conversa_texto)
    return jsonify({"answer": resumo})


if __name__ == '__main__':
    # In produção, use um servidor WSGI. Aqui, debug=True para teste.
    app.run(host='0.0.0.0', port=8000, debug=True)
