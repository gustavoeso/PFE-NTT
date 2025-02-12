from openai import OpenAI

client = OpenAI(
  api_key="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"
)

completion = client.chat.completions.create(
  model="gpt-4o-mini",
  store=True,
  messages=[
    {"role": "user", "content": "write a haiku about ai"}
  ]
)

print(completion.choices[0].message);