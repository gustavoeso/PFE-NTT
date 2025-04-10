import json
from fastapi import WebSocket, WebSocketDisconnect
from server.utils.memory import connections, agent_cache, agent_memory
from server.llm.chains import buyer_chain, seller_chain, resumo_chain
from server.db.queries import get_store_number, get_store_coordinates, get_matching_items, multi_table_search
from server.models.schemas import AgentResponse

async def websocket_endpoint(websocket: WebSocket, agent_id: str):
    await websocket.accept()
    connections[agent_id] = websocket
    agent_cache[agent_id].clear()
    agent_memory[agent_id].clear()

    try:
        while True:
            data = await websocket.receive_text()
            data_json = json.loads(data)
            action = data_json.get("action")
            prompt = data_json.get("prompt")

            if action == "start":
                await websocket.send_text(json.dumps({"message": f"Sessão iniciada para agent_id={agent_id}"}))

            elif action == "buyer_message":
                memory_msgs = agent_memory[agent_id]
                history_text = "\n".join(f"{m['role'].upper()}: {m['text']}" for m in memory_msgs)

                result = buyer_chain.invoke({
                    "history": history_text,
                    "seller_utterance": prompt
                })

                agent_memory[agent_id].append({"role": "seller", "text": prompt})
                agent_memory[agent_id].append({"role": "buyer", "text": result.answer})

                await websocket.send_text(json.dumps(result.dict()))

            elif action == "store_request":
                store_number = get_store_number(prompt, agent_id)
                stock_info = multi_table_search(prompt, agent_id)
                matching_items = get_matching_items(prompt, store_number, agent_id)

                history_text = "\n".join(f"{m['role'].upper()}: {m['text']}" for m in agent_memory[agent_id])

                result = seller_chain.invoke({
                    "buyer_utterance": prompt,
                    "history": history_text,
                    "stock_info": stock_info
                })

                agent_memory[agent_id].append({"role": "buyer", "text": prompt})
                agent_memory[agent_id].append({"role": "seller", "text": result.answer})

                await websocket.send_text(json.dumps(result.dict()))

            elif action == "get_summary":
                memory_msgs = agent_memory[agent_id]
                conversa_texto = "\n".join(f"{m['role'].upper()}: {m['text']}" for m in memory_msgs)

                resumo = resumo_chain.invoke({"conversa": conversa_texto})
                await websocket.send_text(json.dumps({"resumo": resumo}))

            elif action == "guide_request":
                try:
                    store_number = get_store_number(prompt, agent_id)
                    store_id = agent_cache[agent_id].get("store_id")
                    store_tipo = agent_cache[agent_id].get("store_tipo")
                    coords = get_store_coordinates(store_number, agent_id)
                    if coords:
                        x, y, z = coords
                        answer = f"Loja encontrada: id={store_id}, tipo='{store_tipo}', número={store_number}. Localização: x={x}, y={y}, z={z}."
                    else:
                        answer = f"Loja encontrada: id={store_id}, tipo='{store_tipo}', número={store_number}, mas posição não cadastrada."

                    await websocket.send_text(json.dumps({"answer": answer, "final_offer": False}))

                except ValueError as e:
                    await websocket.send_text(json.dumps({"answer": str(e), "final_offer": True}))

    except WebSocketDisconnect:
        print(f"[INFO] Desconectado: {agent_id}")
        connections.pop(agent_id, None)
        agent_cache.pop(agent_id, None)
        agent_memory.pop(agent_id, None)