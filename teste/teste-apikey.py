import openai
import os
from dotenv import load_dotenv

# Carregar o .env
load_dotenv()

# Obter a API Key
api_key = os.getenv("OPENAI_API_KEY")

# Verificar se a chave foi carregada corretamente
if not api_key:
    print("Erro: API Key não encontrada no .env")
else:
    print("API Key carregada:", api_key[:5] + "..." + api_key[-5:])  # Oculta parte da chave para segurança

# Configurar cliente da OpenAI corretamente (método atualizado)
client = openai.OpenAI(api_key=api_key)

# Testar chamada simples à API
try:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Diga 'Olá Mundo'"}]
    )
    print("Resposta da OpenAI:", response.choices[0].message.content)
except openai.AuthenticationError as e:
    print("Erro de autenticação:", e)
except Exception as e:
    print("Outro erro ocorreu:", e)
