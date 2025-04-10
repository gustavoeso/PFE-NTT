from collections import defaultdict

# Conexões WebSocket por agent_id
connections = {}

# Cache de dados do agente (loja, posição, estoque...)
agent_cache = defaultdict(dict)

# Histórico de mensagens por agente (lista de dicts: {"role": "buyer"/"seller", "text": "..."})
agent_memory = defaultdict(list)