from fastapi import FastAPI, Request
import uvicorn
import os

# Import your conversation logic from conversation.py:
from conversation import (
    buyer_memory,
    buyer_chain,
    seller_chain,
    multi_table_search,
    should_stop_conversation
)

app = FastAPI()

# ------------------------------------------------
# (Optional) Clear the buyer's memory on startup
# ------------------------------------------------
@app.post("/startApplication")
async def start_application():
    # Clear buyer memory so the conversation is fresh
    buyer_memory.clear()
    return {"status": "Aplicação iniciada corretamente."}


# ------------------------------------------------
# 1) Buyer Turn
# ------------------------------------------------
@app.post("/conversation/buyer")
async def buyer_turn(request: Request):
    """
    This endpoint simulates the Buyer speaking next.
    We feed the last Seller utterance as "seller_utterance" in JSON.
    Then the Buyer chain produces a new response.
    We'll also check if the conversation ended.
    """
    data = await request.json()
    last_seller_utterance = data.get("seller_utterance", "")

    # Buyer responds
    buyer_reply = buyer_chain.run(seller_utterance=last_seller_utterance)
    conversation_ended = should_stop_conversation()

    return {
        "buyer_reply": buyer_reply,
        "conversation_ended": conversation_ended
    }


# ------------------------------------------------
# 2) Seller Turn
# ------------------------------------------------
@app.post("/conversation/seller")
async def seller_turn(request: Request):
    """
    This endpoint simulates the Seller speaking next.
    We feed the last Buyer utterance as "buyer_utterance" in JSON.
    The Seller will do a DB search (via multi_table_search) and produce a response.
    Then we store Seller's response in buyer_memory so that the Buyer sees it next time.
    """
    data = await request.json()
    buyer_utterance = data.get("buyer_utterance", "")

    # 1) Use DB logic to find "stock_info"
    stock_info = multi_table_search(buyer_utterance)

    # 2) The seller crafts a response with that stock_info + conversation history
    #    We retrieve buyer's memory to get the conversation so far
    history_so_far = buyer_memory.load_memory_variables({})["history"]
    seller_response = seller_chain.run(
        buyer_utterance=buyer_utterance,
        stock_info=stock_info,
        history=history_so_far
    )

    # 3) We manually store the Seller's message into the Buyer memory, so the Buyer sees it
    buyer_memory.save_context({"input": ""}, {"output": seller_response})

    return {
        "seller_reply": seller_response
    }


# ------------------------------------------------
# If you want to remove or comment out the OLD /request/{agent_id} 
# endpoints, you can do so. If you want to keep them,
# just leave them in. Up to you.
# ------------------------------------------------

"""
# Example: removing or commenting out the old code
# @app.post("/request/{agent_id}")
# async def process_prompt(agent_id: str, request: Request):
#     return {"response": "Deprecated or not used anymore."}
"""

# ------------------------------------------------
# Run the server
# ------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)
