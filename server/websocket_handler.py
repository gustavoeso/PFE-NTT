import json
from fastapi import WebSocket, WebSocketDisconnect
from server.utils.memory import connections, agent_cache, agent_memory
from server.llm.chains import buyer_chain, seller_chain, resumo_chain, parser
from server.db.queries import get_store_number, get_store_coordinates, get_matching_items, multi_table_search

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
                agent_cache[agent_id].clear()
                agent_memory[agent_id].clear()  # já presente
                await websocket.send_text(json.dumps({"message": f"Sessão iniciada para agent_id={agent_id}"}))

            elif action == "buyer_message":
                request_id = data_json.get("request_id", "undefined")
                memory_msgs = agent_memory[agent_id]
                history_text = "\n".join(f"{m['role'].upper()}: {m['text']}" for m in memory_msgs)

                result = buyer_chain.invoke({
                    "history": history_text,
                    "seller_utterance": prompt,
                    "desired_item": agent_cache[agent_id]["desired_item"],
                    "max_price": agent_cache[agent_id]["max_price"],
                    "format_instructions": parser.get_format_instructions()
                })

                print(f"[INFO] Enviando resposta para o cliente: {result.final_offer}")

                agent_memory[agent_id].append({"role": "seller", "text": prompt})
                agent_memory[agent_id].append({"role": "buyer", "text": result.answer})

                response_data = result.dict()
                response_data["request_id"] = request_id
                await websocket.send_text(json.dumps(response_data))

            elif action == "store_request":
                request_id = data_json.get("request_id", "undefined")
                store_number = get_store_number(prompt, agent_id)
                stock_info = multi_table_search(prompt, agent_id)

                history_text = "\n".join(f"{m['role'].upper()}: {m['text']}" for m in agent_memory[agent_id])

                result = seller_chain.invoke({
                    "buyer_utterance": prompt,
                    "history": history_text,
                    "stock_info": stock_info,
                    "format_instructions": parser.get_format_instructions()
                })

                agent_memory[agent_id].append({"role": "buyer", "text": prompt})
                agent_memory[agent_id].append({"role": "seller", "text": result.answer})

                response_data = result.dict()
                response_data["request_id"] = request_id
                await websocket.send_text(json.dumps(response_data))

            elif action == "get_summary":
                request_id = data_json.get("request_id", "undefined")
                conversa_texto = data_json.get("conversa", "Nenhuma conversa encontrada.")

                result = resumo_chain.invoke({"conversa": conversa_texto})
                response_data = {"answer": result.content, "final_offer": False, "request_id": request_id}

                await websocket.send_text(json.dumps(response_data))

            elif action == "guide_request":
                request_id = data_json.get("request_id", "undefined")

                try:
                    store_number = get_store_number(prompt, agent_id)
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

                    print(f"[INFO] Enviando resposta para o cliente: {answer}")

                    agent_memory[agent_id].append({"role": "guide", "text": answer})
                    await websocket.send_text(json.dumps({
                        "request_id": request_id,
                        "answer": answer,
                        "final_offer": False
                    }))

                except ValueError as e:
                    await websocket.send_text(json.dumps({
                        "request_id": request_id,
                        "answer": str(e),
                        "final_offer": True
                    }))

            elif action == "setBuyerPreferences":
                try:
                    desired_item = data_json.get("desired_item", "camiseta branca")
                    max_price = data_json.get("max_price", 60)

                    agent_cache[agent_id]["desired_item"] = desired_item
                    agent_cache[agent_id]["max_price"] = max_price

                    await websocket.send_text(json.dumps({"response": f"Preferencias salvas: item={desired_item}, max={max_price}."}))
                
                except ValueError as e:
                    await websocket.send_text(json.dumps({"response": str(e)}))

    except WebSocketDisconnect:
        print(f"[INFO] Desconectado: {agent_id}")
        connections.pop(agent_id, None)
        agent_cache.pop(agent_id, None)
        agent_memory.pop(agent_id, None)