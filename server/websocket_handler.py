import json
from fastapi import WebSocket, WebSocketDisconnect
from server.utils.memory import connections, agent_cache, agent_memory, productIndex, stores
from server.llm.chains import buyer_chain, seller_chain, resumo_chain, parser, interestChecker_chain, first_interest_chain
from server.db.queries import get_store_tipo, multi_table_search, find_all_stores

async def websocket_endpoint(websocket: WebSocket, agent_id: str):
    await websocket.accept()
    connections[agent_id] = websocket
    agent_cache[agent_id].clear()
    agent_memory[agent_id].clear()

    try:
        while True:
            data = await websocket.receive_text()
            print(">> Conteúdo recebido:", repr(data))
            data = data.replace('\n', '\\n')
            data_json = json.loads(data)
            action = data_json.get("action")
            prompt = data_json.get("prompt")

            if action == "start":
                agent_cache[agent_id].clear()
                agent_memory[agent_id].clear()  
                stores.clear()
                find_all_stores()
                await websocket.send_text(json.dumps({"message": f"Sessão iniciada para agent_id={agent_id}"}))

            elif action == "nextProduct":
                productIndex[agent_id] += 1

            elif action == "buyer_interested":
                request_id = data_json.get("request_id", "undefined")
                result = interestChecker_chain.invoke({
                    "storeDescription": prompt,
                    "buyerInterest": agent_cache[agent_id]["interests"],
                    "format_instructions": parser.get_format_instructions()
                })

                response_data = result.dict()
                response_data["request_id"] = request_id
                await websocket.send_text(json.dumps(response_data))

            elif action == "buyer_message":
                request_id = data_json.get("request_id", "undefined")
                memory_msgs = agent_memory[agent_id]
                history_text = "\n".join(f"{m['role'].upper()}: {m['text']}" for m in memory_msgs)

                result = buyer_chain.invoke({
                    "history": history_text,
                    "seller_utterance": prompt,
                    "buyer_interests": agent_cache[agent_id]["interests"],
                    "desired_item": agent_cache[agent_id]["desired_items"][productIndex[agent_id]],
                    "max_price": agent_cache[agent_id]["max_prices"][productIndex[agent_id]],
                    "format_instructions": parser.get_format_instructions()
                })

                print(f"[INFO] Enviando resposta para o cliente: {result.final_offer}")

                agent_memory[agent_id].append({"role": "seller", "text": prompt})
                agent_memory[agent_id].append({"role": "buyer", "text": result.answer})

                response_data = result.dict()
                response_data["request_id"] = request_id
                await websocket.send_text(json.dumps(response_data))

            elif action == "firstInterestMessage":
                request_id = data_json.get("request_id", "undefined")
                memory_msgs = agent_memory[agent_id]
                history_text = "\n".join(f"{m['role'].upper()}: {m['text']}" for m in memory_msgs)

                result = first_interest_chain.invoke({
                    "history": history_text,
                    "buyer_interests": agent_cache[agent_id]["interests"],
                    "desired_item": agent_cache[agent_id]["desired_items"][productIndex[agent_id]],
                    "max_price": agent_cache[agent_id]["max_prices"][productIndex[agent_id]]
                })

                agent_memory[agent_id].append({"role": "seller", "text": prompt})
                agent_memory[agent_id].append({"role": "buyer", "text": result.content})

                response_data = result.dict()
                response_data["request_id"] = request_id
                response_data["answer"] = result.content
                await websocket.send_text(json.dumps(response_data))


            elif action == "store_request":
                request_id = data_json.get("request_id", "undefined")
                store_description = data_json.get("store_description", "Nenhuma descrição de loja encontrada.")
                stock_info = multi_table_search(agent_cache[agent_id]["desired_items"][productIndex[agent_id]], agent_id, store_description)

                history_text = "\n".join(f"{m['role'].upper()}: {m['text']}" for m in agent_memory[agent_id])

                result = seller_chain.invoke({
                    "buyer_utterance": prompt,
                    "history": history_text,
                    "stock_info": stock_info
                })

                agent_memory[agent_id].append({"role": "buyer", "text": prompt})
                agent_memory[agent_id].append({"role": "seller", "text": result.content})

                response_data = result.dict()
                response_data["request_id"] = request_id
                response_data["answer"] = result.content
                await websocket.send_text(json.dumps(response_data))

            elif action == "get_summary":
                request_id = data_json.get("request_id", "undefined")
                conversa_texto = data_json.get("conversa", "Nenhuma conversa encontrada.")

                result = resumo_chain.invoke({"conversa": conversa_texto})
                response_data = {"answer": result.content, "request_id": request_id}

                await websocket.send_text(json.dumps(response_data))

            elif action == "guide_request":
                request_id = data_json.get("request_id", "undefined")

                try:
                    desired_item = agent_cache[agent_id]["desired_items"][productIndex[agent_id]]
                    store_tipo = get_store_tipo(desired_item)
                    store_id = stores[store_tipo][1]
                    store_number = stores[store_tipo][0]

                    answer = (
                        f"Loja encontrada: id={store_id}, tipo='{store_tipo}', número={store_number}"
                    )

                    print(f"[INFO] Enviando resposta para o cliente: {answer}")
                    agent_memory[agent_id].append({"role": "guide", "text": answer})

                    await websocket.send_text(json.dumps({
                        "request_id": request_id,
                        "answer": answer,
                    }))

                except ValueError as e:
                    await websocket.send_text(json.dumps({
                        "request_id": request_id,
                        "answer": str(e),
                    }))


            elif action == "setBuyerPreferences":
                try:
                    productIndex[agent_id] = 0
                    desired_items = data_json.get("desired_item", [])
                    max_prices = data_json.get("max_price", [])
                    interests = data_json.get("interests")

                    if isinstance(desired_items, str):
                        desired_items = [desired_items]
                    if isinstance(max_prices, (int, float, str)):
                        max_prices = [float(max_prices)]

                    if isinstance(desired_items, dict) and "list" in desired_items:
                        desired_items = desired_items["list"]
                    if isinstance(max_prices, dict) and "list" in max_prices:
                        max_prices = max_prices["list"]

                    if len(desired_items) != len(max_prices):
                        raise ValueError("Número de produtos e preços não corresponde.")

                    agent_cache[agent_id]["desired_items"] = desired_items
                    agent_cache[agent_id]["max_prices"] = max_prices
                    agent_cache[agent_id]["interests"] = interests
                    print(agent_cache[agent_id]["interests"])

                    await websocket.send_text(json.dumps({
                        "response": f"Preferências salvas: itens={desired_items}, preços={max_prices}"
                    }))
                
                except ValueError as e:
                    await websocket.send_text(json.dumps({"response": str(e)}))


    except WebSocketDisconnect:
        print(f"[INFO] Desconectado: {agent_id}")
        connections.pop(agent_id, None)
        agent_cache.pop(agent_id, None)
        agent_memory.pop(agent_id, None)