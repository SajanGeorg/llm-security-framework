import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["GEMINI_API_KEY"],
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
)

resp = client.chat.completions.create(
    model="gemini-2.5-flash",      # paste the exact ID from AI Studio
    messages=[{"role": "user", "content": "Reply with oh yeah: Pika pikachu working"}],
    temperature=0,
)
print(resp.choices[0].message.content)