# T5: Grok - Fast & Cheap LLM

## Overview
Grok-beta via xAI API using OpenAI-compatible client. Best for cheap/fast inference, fallback LLM, and streaming.

---

## 🚀 Quick Setup

```python
from openai import OpenAI
import os

client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1"
)

response = client.chat.completions.create(
    model="grok-beta",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ]
)

print(response.choices[0].message.content)
```

---

## 💬 Streaming

```python
stream = client.chat.completions.create(
    model="grok-beta",
    messages=[{"role": "user", "content": "Write a poem"}],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="", flush=True)
```

---

## 🎯 When to Use Grok

✅ **Good for**:
- Fast responses (low latency)
- Cheap inference ($5/M tokens vs $15/M for Claude)
- Fallback when primary LLM down
- Non-critical tasks
- High-volume generation

❌ **Not good for**:
- Complex reasoning
- Long context (128K max)
- Tool use (no function calling yet)
- High-stakes outputs

---

## 📊 Pricing Comparison

| Model | Input | Output | Context |
|-------|-------|--------|---------|
| Grok-beta | $5/M | $15/M | 128K |
| Claude Sonnet | $3/M | $15/M | 200K |
| GPT-4 | $10/M | $30/M | 128K |

**Grok wins on**: Output tokens, speed
**Claude wins on**: Context, reasoning, tools

---

## 🔧 Advanced Options

```python
response = client.chat.completions.create(
    model="grok-beta",
    messages=messages,
    temperature=0.7,      # 0-2, higher = more creative
    max_tokens=2000,      # Max output length
    top_p=0.9,           # Nucleus sampling
    frequency_penalty=0,  # Reduce repetition
    presence_penalty=0,   # Encourage new topics
    stream=False         # Set True for streaming
)
```

---

## 🎭 System Prompts

```python
messages = [
    {
        "role": "system",
        "content": """You are a code assistant. Rules:
        - Be concise
        - Prefer Python
        - Include error handling
        - Add comments for complex logic"""
    },
    {"role": "user", "content": "Write a file reader"}
]
```

---

## 🔄 Multi-Turn Conversations

```python
conversation = [
    {"role": "system", "content": "You are helpful."},
]

while True:
    user_input = input("You: ")
    if user_input == "quit":
        break

    # Add user message
    conversation.append({"role": "user", "content": user_input})

    # Get response
    response = client.chat.completions.create(
        model="grok-beta",
        messages=conversation
    )

    assistant_msg = response.choices[0].message.content
    conversation.append({"role": "assistant", "content": assistant_msg})

    print(f"Grok: {assistant_msg}")
```

---

## 🎯 SDK Tool Pattern

```python
from claude_agent_sdk import tool

@tool(
    name="grok_generate",
    description="Generate text using Grok LLM (fast and cheap)",
    input_schema={"prompt": str, "max_tokens": int}
)
async def grok_generate(args: dict):
    prompt = args.get("prompt")
    max_tokens = args.get("max_tokens", 1000)

    client = OpenAI(
        api_key=os.getenv("XAI_API_KEY"),
        base_url="https://api.x.ai/v1"
    )

    try:
        response = client.chat.completions.create(
            model="grok-beta",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens
        )

        result = response.choices[0].message.content

        return {
            "content": [{"type": "text", "text": result}]
        }

    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Grok error: {str(e)}"}],
            "isError": True
        }
```

---

## 🚨 Error Handling

```python
from openai import OpenAI, APIError, RateLimitError

try:
    response = client.chat.completions.create(...)

except RateLimitError:
    # Hit rate limit
    print("Rate limit exceeded. Wait and retry.")

except APIError as e:
    # API error
    print(f"API error: {e.status_code} - {e.message}")

except Exception as e:
    # Other errors
    print(f"Unexpected error: {e}")
```

---

## ⚡ Async Usage

```python
from openai import AsyncOpenAI

async_client = AsyncOpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1"
)

async def generate_async(prompt: str):
    response = await async_client.chat.completions.create(
        model="grok-beta",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# Use with asyncio
import asyncio
result = asyncio.run(generate_async("Hello"))
```

---

## 📊 Response Object

```python
response = client.chat.completions.create(...)

# Access fields
response.id                    # Request ID
response.model                 # "grok-beta"
response.created               # Unix timestamp
response.choices[0].message.content  # Generated text
response.choices[0].finish_reason    # "stop", "length", etc.
response.usage.prompt_tokens   # Input tokens
response.usage.completion_tokens  # Output tokens
response.usage.total_tokens    # Total
```

---

## 🔧 Environment Setup

```bash
# .env
XAI_API_KEY=xai-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Get key from: https://x.ai/api

---

## 🎯 Use Cases

### Cheap Summarization
```python
def summarize_cheap(text: str):
    response = client.chat.completions.create(
        model="grok-beta",
        messages=[{
            "role": "user",
            "content": f"Summarize in 3 bullet points:\n\n{text}"
        }],
        max_tokens=200
    )
    return response.choices[0].message.content
```

### Fast Classification
```python
def classify_sentiment(text: str):
    response = client.chat.completions.create(
        model="grok-beta",
        messages=[{
            "role": "user",
            "content": f"Classify sentiment (positive/negative/neutral): {text}"
        }],
        max_tokens=10
    )
    return response.choices[0].message.content.strip().lower()
```

### Fallback LLM
```python
def generate_with_fallback(prompt: str):
    try:
        # Try Claude first
        return claude_generate(prompt)
    except Exception:
        # Fallback to Grok
        return grok_generate(prompt)
```

---

## 📖 Docs

- xAI API: https://docs.x.ai/api
- OpenAI Python client: https://github.com/openai/openai-python
- Grok pricing: https://x.ai/api#pricing

---

*Grok-beta is OpenAI-compatible. Use the `openai` Python client with custom base_url.*
