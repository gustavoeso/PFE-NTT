from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from server.websocket_handler import websocket_endpoint
import uvicorn

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

app.websocket("/ws/{agent_id}")(websocket_endpoint)

@app.get("/")
async def root():
    return HTMLResponse("<h1>Servidor WebSocket rodando!</h1>")

if __name__ == "__main__":
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)