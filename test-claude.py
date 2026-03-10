import os
import anthropic
from dotenv import load_dotenv

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")

response = client.messages.create(
    model=model,
    max_tokens=100,
    messages=[
        {
            "role": "user",
            "content": "What is the capital of France?"
        }
    ]
)
print(response.content[0].text)
