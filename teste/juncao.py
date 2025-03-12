import os
from dotenv import load_dotenv

#####################################################################
# 1) ENV Setup + LLM
#####################################################################
import openai
# If you are using "langchain_community" for ChatOpenAI:
from langchain_community.chat_models import ChatOpenAI
# Otherwise from langchain_openai import ChatOpenAI
# or from langchain.chat_models import ChatOpenAI

from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    PromptTemplate
)
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory

# For DB
from sqlalchemy import create_engine, text
from langchain_experimental.sql import SQLDatabaseChain
from langchain_community.utilities import SQLDatabase

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
model_name = os.getenv("OPENAI_MODEL_NAME", "gpt-4")


#####################################################################
# 2) Database Setup
#####################################################################
db_uri = "postgresql://myuser:mypassword@shopping.cib0gcgyigl5.us-east-1.rds.amazonaws.com:5432/shopping"
engine = create_engine(db_uri)
database = SQLDatabase(engine)


#####################################################################
# 3) Base LLM for SQL & Revised Custom Prompt (with valid store numbers)
#####################################################################
llm_for_sql = ChatOpenAI(
    model_name=model_name,
    openai_api_key=api_key,
    temperature=0.3
)

# Notice double braces around {numero} so the LLM doesn't treat it as a variable
# Also mention that store numbers are only 100, 105, 110, 115, 120
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

TABLE `loja_{{numero}}` (for each valid store number like 100,105,110...):
  - id (integer)
  - produto (varchar)
  - tipo (varchar)
  - qtd (numeric)
  - preco (numeric)

No other `loja_{{n}}` tables exist. For example, do not use `loja_1`.

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
    verbose=False
)

def search_database(nl_query: str):
    """
    Convert NL -> SQL using `sql_chain`, then run it.
    Return (sql_text, rows).
    """
    chain_output = sql_chain.invoke({"query": nl_query})
    sql_text = chain_output.get("result", "")
    if not sql_text:
        return ("", [])

    rows = []
    try:
        with engine.connect() as conn:
            result_proxy = conn.execute(text(sql_text))
            rows = result_proxy.fetchall()
    except Exception as e:
        print(f"[search_database Error]: {e}")

    return (sql_text, rows)


#####################################################################
# 4) Additional LLM Chains (PromptGenerator, etc.)
#####################################################################
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

O comprador quer: "{user_request}"

Gere UMA LINHA de texto (em português) no formato:

Na tabela 'loja_{store_number}', retorne produto, tipo, qtd, preco 
where produto ILIKE '%...%' AND tipo ILIKE '%...%' AND qtd > 0.

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

Na tabela 'loja_{store_number}', retorne produto, tipo, qtd, preco 
where qtd > 0 AND preco BETWEEN {min_price} AND {max_price} 
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
# 5) multi_table_search – your snippet #1 logic with dynamic fallback price
#####################################################################
def multi_table_search(buyer_request: str) -> str:
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
    store_row = rows_store[0]
    store_info = {
        "id": store_row[0],
        "tipo": store_row[1],
        "numero": int(store_row[2])
    }

    # Step 3: get store coords from 'posicao' (optional)
    nl_query_pos = f"Na tabela 'posicao', retorne x,y,z onde numero = {store_info['numero']}."
    sql_pos, rows_pos = search_database(nl_query_pos)
    coords = []
    for r in rows_pos:
        coords.append({"x": float(r[0]), "y": float(r[1]), "z": float(r[2])})

    # Step 4: check in loja_{numero}
    store_number = store_info["numero"]
    item_request = buyer_request

    # 4A) Primary attempt: in-stock items
    prompt_for_loja = prompt_loja_chain.run({
        "store_number": store_number,
        "user_request": item_request
    })
    sql_loja, rows_loja = search_database(prompt_for_loja)

    matching_items = []
    for r in rows_loja:
        matching_items.append({
            "produto": r[0],
            "tipo": r[1],
            "qtd": int(r[2]),
            "preco": float(r[3])
        })

    exact_match_in_stock = matching_items
    recommended_items = []
    fallback_prompt = ""
    fallback_sql = ""

    # 4B) Fallback logic if no exact match in stock
    if not exact_match_in_stock:
        # We'll see if the item exists ignoring stock to get its price
        reference_price = 250.0  # default
        ignore_stock_query = f"""
        SELECT produto, tipo, qtd, preco
        FROM loja_{store_number}
        WHERE produto ILIKE '%{item_request}%'
          AND tipo ILIKE '%{item_request}%'
        LIMIT 1
        """
        _, ignore_stock_rows = search_database(ignore_stock_query)
        if ignore_stock_rows:
            # Found item but presumably out of stock
            row0 = ignore_stock_rows[0]
            reference_price = float(row0[3])

        min_price = reference_price * 0.8
        max_price = reference_price * 1.2

        # 4C) fallback prompt
        fallback_prompt = prompt_loja_fallback_chain.run({
            "store_number": store_number,
            "user_request": item_request,
            "min_price": min_price,
            "max_price": max_price
        })
        fallback_sql, rows_loja_fallback = search_database(fallback_prompt)
        for r in rows_loja_fallback:
            recommended_items.append({
                "produto": r[0],
                "tipo": r[1],
                "qtd": int(r[2]),
                "preco": float(r[3])
            })

    # Merge
    final_items = exact_match_in_stock if exact_match_in_stock else recommended_items

    # Step 5) Build summary text
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
            summary_lines.append(f"   - {it['produto']} ({it['tipo']}), qtd={it['qtd']}, R${it['preco']}")
    else:
        summary_lines.append("(Nenhum item encontrado ou recomendado)")

    return "\n".join(summary_lines)


#####################################################################
# 6) Conversation: BuyerChain, SellerChain, ControllerChain
#####################################################################

# Only Buyer chain uses memory. 
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
- Se ainda não decidiu, você pode fazer perguntas.
- Quando decidir, diga explicitamente "Vou levar" ou "Não vou levar".
  É SOMENTE COM ESSAS EXATAS PALAVRAS que você finaliza sua decisão.

Histórico da conversa até agora:
{history}
"""

buyer_human_template = """
A última fala do Vendedor (Seller) foi:
{seller_utterance}

Agora responda como BUYER:
1. Se ainda estiver indeciso, faça perguntas ou diga o que acha.
2. Para encerrar, diga EXATAMENTE "Vou levar" ou "Não vou levar".
3. Não se identifique como IA.
"""

buyer_system_msg = SystemMessagePromptTemplate.from_template(buyer_system_template)
buyer_human_msg = HumanMessagePromptTemplate.from_template(buyer_human_template)

buyer_prompt = ChatPromptTemplate(
    input_variables=["history", "seller_utterance"],
    messages=[buyer_system_msg, buyer_human_msg]
)

buyer_chain = LLMChain(
    llm=ChatOpenAI(
        openai_api_key=api_key,
        model_name=model_name,
        temperature=0.3
    ),
    prompt=buyer_prompt,
    memory=buyer_memory,  
    verbose=False
)


########################################
# SellerChain (NO memory)
########################################
seller_system_template = """
Você é o Seller (vendedor) em uma loja no shopping.
Não se identifique como IA.

Objetivo:
- Vender produtos (ou responder perguntas) usando dados reais do estoque.
- Responda perguntas do Buyer sobre produto, preço, quantidade, etc.
- Não encerre a conversa você mesmo.

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
3. Não encerre. Aguarde o Buyer dizer "Vou levar" ou "Não vou levar".
"""

seller_system_msg = SystemMessagePromptTemplate.from_template(seller_system_template)
seller_human_msg = HumanMessagePromptTemplate.from_template(seller_human_template)

seller_prompt = ChatPromptTemplate(
    input_variables=["history", "buyer_utterance", "stock_info"],
    messages=[seller_system_msg, seller_human_msg]
)

seller_chain = LLMChain(
    llm=ChatOpenAI(
        openai_api_key=api_key,
        model_name=model_name,
        temperature=0.3
    ),
    prompt=seller_prompt,
    verbose=False
)


########################################
# ControllerChain
########################################
controller_prompt_template = """
Você é um agente controlador que analisa o histórico da conversa (Buyer e Seller)
e decide se deve ENCERRAR ou CONTINUAR.

REGRAS:
- Responda "STOP" SOMENTE se o Buyer disser EXATAMENTE "Vou levar" ou EXATAMENTE "Não vou levar".
- Caso contrário => CONTINUE.
- Não use nada além de STOP ou CONTINUE (sem aspas).

Exemplos:
[CONTINUE] Buyer: "Acho que vou levar."
[STOP] Buyer: "Vou levar"
[STOP] Buyer: "Não vou levar"

Histórico:
{history}
"""

controller_prompt = PromptTemplate(
    input_variables=["history"],
    template=controller_prompt_template
)

controller_chain = LLMChain(
    llm=ChatOpenAI(
        openai_api_key=api_key,
        model_name=model_name,
        temperature=0.0
    ),
    prompt=controller_prompt,
    verbose=False
)

def should_stop_conversation() -> bool:
    mem_vars = buyer_memory.load_memory_variables({})
    msgs = mem_vars["history"]
    history_str = ""
    for m in msgs:
        role = "Buyer" if m.type == "human" else "Seller"
        history_str += f"{role}: {m.content}\n"

    result = controller_chain.run({"history": history_str})
    return "STOP" in result.upper()


#####################################################################
# 7) Main Loop
#####################################################################
def main():
    print("=== Conversa: Buyer vs Seller (3 TABELAS) ===\n")

    buyer_utterance = input("Digite a FALA INICIAL do Buyer: ").strip()
    print()
    # Save the first Buyer message into buyer_memory
    buyer_memory.save_context({"input": ""}, {"output": buyer_utterance})
    print(f"Buyer (turno 1): {buyer_utterance}\n")

    max_turns = 20
    turn = 2
    seller_response = ""

    while turn <= max_turns:
        # Check if conversation stops
        if should_stop_conversation():
            print("=== O Controller decidiu encerrar a conversa (STOP) ===")
            break

        if turn % 2 == 0:
            # Seller's turn
            stock_info = multi_table_search(buyer_utterance)

            # Provide the entire conversation to the Seller as "history"
            current_history = buyer_memory.load_memory_variables({})["history"]
            seller_response = seller_chain.run(
                buyer_utterance=buyer_utterance,
                stock_info=stock_info,
                history=current_history
            )
            print(f"Seller (turno {turn}): {seller_response}\n")

            # Manually store Seller's message in the Buyer memory
            buyer_memory.save_context({"input": ""}, {"output": seller_response})

        else:
            # Buyer's turn
            buyer_response = buyer_chain.run(seller_utterance=seller_response)
            print(f"Buyer (turno {turn}): {buyer_response}\n")
            buyer_utterance = buyer_response

        turn += 1
    else:
        print(f"=== A conversa atingiu {max_turns} turnos e foi encerrada ===")


if __name__ == "__main__":
    main()
