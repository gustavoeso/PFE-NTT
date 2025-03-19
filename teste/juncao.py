import os
from dotenv import load_dotenv

#####################################################################
# 1) ENV Setup + LLM
#####################################################################
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
    temperature=0.0   # <--- zero
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
    verbose=False
)

def search_database(nl_query: str):
    """
    Convert NL -> SQL using `sql_chain`, then run it.
    Return (sql_text, rows).
    """
    try:
        chain_output = sql_chain.invoke({"query": nl_query})
    except Exception as e:
        print(f"[search_database] Error generating SQL: {e}")
        return ("", [])

    sql_text = chain_output.get("result", "")
    if not sql_text:
        return ("", [])

    rows = []
    try:
        with engine.connect() as conn:
            result_proxy = conn.execute(text(sql_text))
            rows = result_proxy.fetchall()
    except Exception as e:
        print(f"[search_database] Error executing SQL: {e}")

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
  - tamanho (texto)
  - material (texto)
  - estampa (texto: 'Sim' ou 'Não')

O comprador quer: "{user_request}"

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
# 5) multi_table_search
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

    # find first row with a valid integer in 'numero'
    store_row = None
    for r in rows_store:
        # expected (id, tipo, numero)
        try:
            _ = int(r[2])  # parse
            store_row = r
            break
        except ValueError:
            continue

    if store_row is None:
        # no row had a valid numeric 'numero'
        return (
            f"=== LOG: Nenhum 'numero' válido encontrado.\n"
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
    item_request = buyer_request

    # 4A) Primary attempt
    prompt_for_loja = prompt_loja_chain.run({
        "store_number": store_number,
        "user_request": item_request
    })
    sql_loja, rows_loja = search_database(prompt_for_loja)

    matching_items = []
    for r in rows_loja:
        # columns: produto, tipo, qtd, preco, tamanho, material, estampa
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
        WHERE produto ILIKE '%{item_request}%'
          AND tipo ILIKE '%{item_request}%'
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
            "user_request": item_request,
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
# 6) BuyerChain & SellerChain
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
- Depois de 3 perguntas, você OBRIGATORIAMENTE deve decidir:
  - Se for comprar: escreva EXATAMENTE "Vou levar"
  - Se não for comprar: escreva EXATAMENTE "Não vou levar"

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
    llm=ChatOpenAI(
        openai_api_key=api_key,
        model_name=model_name,
        temperature=0.3
    ),
    prompt=seller_prompt,
    verbose=False
)

#####################################################################
# 7) (Opcional) ControllerChain - NÃO USADO
#####################################################################
"""
Este trecho ilustra um controlador baseado em LLM.
Podemos comentar ou remover, pois a checagem abaixo em Python substitui.
"""
# from langchain.prompts import PromptTemplate
# controller_system_template = """
# Você é o agente controlador da conversa. 
# A última frase do comprador (Buyer) foi: {last_buyer_message}

# REGRAS (importantíssimo):
# - Se a última frase do Buyer CONTÉM (sem case-sensitive) "vou levar" ou "não vou levar", responda SOMENTE "STOP".
# - Caso contrário, responda SOMENTE "CONTINUE".

# Apenas responda "STOP" ou "CONTINUE". Sem nada mais.
# """
# controller_prompt = PromptTemplate(
#     input_variables=["last_buyer_message"],
#     template=controller_system_template
# )
# controller_chain = LLMChain(
#     llm=ChatOpenAI(
#         openai_api_key=api_key,
#         model_name=model_name,
#         temperature=0.0
#     ),
#     prompt=controller_prompt,
#     verbose=False
# )

#####################################################################
# 8) Função de checagem direta no Python (elimina a necessidade do controller_chain)
#####################################################################
def should_stop_conversation() -> bool:
    """
    Se a última fala do Buyer conter "vou levar" ou "não vou levar"
    (ignora maiúscula/minúscula e acentuação), paramos a conversa imediatamente.
    """
    mem_vars = buyer_memory.load_memory_variables({})
    msgs = mem_vars["history"]
    if not msgs:
        return False

    last_message = msgs[-1]
    # Verifica se a última mensagem foi mesmo do Buyer (ou seja, "human")
    if last_message.type != "human":
        return False

    buyer_text = last_message.content.lower()
    # Checa substrings
    # Também tratamos "não" e "nao"
    if "vou levar." in buyer_text or "não vou levar." in buyer_text or "nao vou levar." in buyer_text:
        return True

    return False

#####################################################################
# 9) Main Loop
#####################################################################
def main():
    print("=== Conversa: Buyer vs Seller (3 TABELAS) ===\n")

    buyer_utterance = input("Digite a FALA INICIAL do Buyer: ").strip()
    print()

    '''
    TODO: Implementar a possibilidade de inserir o preço que deseja pagar.
          Isso faz com que o vendedor tenha que buscar um produto que 
          esteja dentro do preço desejado.
    '''
    # Salva a primeira fala do Buyer na memória
    buyer_memory.save_context({"input": ""}, {"output": buyer_utterance})
    print(f"Buyer (turno 1): {buyer_utterance}\n")

    max_turns = 20
    turn = 2
    seller_response = ""

    while turn <= max_turns:
        if should_stop_conversation():
            print("=== STOP. Encerrando conversa. ===")
            break

        if turn % 2 == 0:
            # Vez do SELLER
            try:
                stock_info = multi_table_search(buyer_utterance)
            except Exception as e:
                stock_info = f"(Erro ao buscar estoque: {e})"

            current_history = buyer_memory.load_memory_variables({})["history"]
            try:
                seller_response = seller_chain.run(
                    buyer_utterance=buyer_utterance,
                    stock_info=stock_info,
                    history=current_history
                )
            except Exception as e:
                seller_response = f"Desculpe, houve um erro interno: {e}"

            print(f"Seller (turno {turn}): {seller_response}\n")
            # Armazena a fala do Seller na memória do Buyer
            buyer_memory.save_context({"input": ""}, {"output": seller_response})

        else:
            # Vez do BUYER
            try:
                buyer_response = buyer_chain.run(seller_utterance=seller_response)
            except Exception as e:
                buyer_response = f"Desculpe, houve um erro interno: {e}"

            print(f"Buyer (turno {turn}): {buyer_response}\n")
            if buyer_response.lower().replace('.', '') in ["vou levar", "não vou levar", "nao vou levar"]:
                print("=== STOP. Encerrando conversa. ===")
                break
            buyer_utterance = buyer_response

        turn += 1
    else:
        print(f"=== A conversa atingiu {max_turns} turnos e foi encerrada ===")


if __name__ == "__main__":
    main()
