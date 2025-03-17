# server.py
from fastapi import FastAPI, Request
import uvicorn
import os

# IMPORT the new conversation logic from conversation.py
from conversation import (
    buyer_chain,
    seller_chain,
    should_stop_conversation,
    multi_table_search,
    buyer_memory
)

# For the old "guide" approach, you can either keep it inline
# or define a chain like you used to. Let’s define it inline here:
from langchain_community.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

model_name = os.getenv("MODEL_NAME", "gpt-4o-mini")
api_key = os.getenv("OPENAI_API_KEY")

# We'll keep a dictionary for our "guide" chain if you want:
agentsDict = {}
memoryDict = {}

# Let's define the chain for "guide," same as your old approach:
llm = ChatOpenAI(model_name=model_name, api_key=api_key, temperature=0)

guide_system_template = """
Você é o Guia do Shopping, educado e prestativo, responsável por ajudar clientes a encontrar lojas específicas.
Não se identifique como IA.

As lojas disponíveis são:
1. Loja de Roupas
2. Loja de Eletrônicos
3. Loja de Brinquedos
4. Loja de Alimentos

Histórico da conversa até agora:
{history}
"""

guide_human_template = """
A última resposta recebida foi:
{last_response}

Agora responda como guia:
- Sempre indique uma das quatro lojas mencionadas acima, escolhendo a mais apropriada para o item solicitado pelo cliente.
- Você DEVE mencionar explicitamente o número da loja escolhida junto com o nome da loja na sua resposta.
- Mencione sempre apenas uma loja.
- Em sua resposta deve haver sempre apenas um único número, representando a loja escolhida.
- Não mencione lojas que não estejam na lista.

Exemplo correto: "Você pode encontrar esse item na Loja 1, a Loja de Roupas."
"""

guide_prompt = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(guide_system_template),
    HumanMessagePromptTemplate.from_template(guide_human_template)
])

guide_memory = ConversationBufferMemory(memory_key="history", return_messages=True)
guide_chain = LLMChain(llm=llm, prompt=guide_prompt, memory=guide_memory)

agentsDict["guide"] = guide_chain
memoryDict["guide"] = guide_memory

# We'll keep the old approach for a "client" chain if you want
# But now "client" is actually your new "buyer" logic from conversation.py.
# We'll just handle that in /request/client logic below.

@app.post("/startApplication")
async def start_application():
    # Clear memory for buyer and guide
    buyer_memory.clear()
    memoryDict["guide"].clear()
    return {"status": "Aplicação iniciada corretamente."}


@app.post("/request/{agent_id}")
async def process_prompt(agent_id: str, request: Request):
    """
    This single route will handle all {agent_id} calls from Unity:
     - /request/client => the "Buyer" logic
     - /request/seller => the "Seller" logic
     - /request/guide  => the old "Guide" chain
    JSON body:
      { "prompt": "...", "speaker": "client" or "guide" or "seller" }
    """
    data = await request.json()
    prompt_text = data.get("prompt", "")
    speaker = data.get("speaker", "")  # might be "client" or "guide" or "seller"

    # 1) If agent_id == "guide", we use the old approach
    if agent_id == "guide":
        if "guide" not in agentsDict:
            return {"response": f"Agente '{agent_id}' não encontrado."}
        
        # We'll interpret "prompt_text" as "last_response"
        guide_reply = agentsDict["guide"].run(last_response=prompt_text)

        # Save to guide memory
        memoryDict["guide"].save_context({"input": prompt_text}, {"output": guide_reply})

        return {"response": guide_reply}

    # 2) If agent_id == "client" => "Buyer"
    elif agent_id == "client":
        # The Buyer sees the last Seller utterance as prompt_text
        buyer_reply = buyer_chain.run(seller_utterance=prompt_text)
        conversation_done = should_stop_conversation()

        # Return the Buyer’s text. If you want, also return whether the conversation ended:
        return {
            "response": buyer_reply,
            "conversation_ended": conversation_done
        }

    # 3) If agent_id == "seller"
    elif agent_id == "seller":
        # The Seller sees the last Buyer utterance as prompt_text
        # Then uses multi_table_search and seller_chain
        stock_info = multi_table_search(prompt_text)

        # Seller sees the conversation so far from the buyer memory
        history = buyer_memory.load_memory_variables({})["history"]
        seller_reply = seller_chain.run(
            buyer_utterance=prompt_text,
            stock_info=stock_info,
            history=history
        )

        # We store the seller's reply in the buyer memory
        buyer_memory.save_context({"input": "", "output": seller_reply})

        return {"response": seller_reply}

    else:
        return {"response": f"Agente '{agent_id}' não encontrado."}


if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)
