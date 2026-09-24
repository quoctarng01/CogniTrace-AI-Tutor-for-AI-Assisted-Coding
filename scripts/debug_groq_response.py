#!/usr/bin/env python3
"""Debug Groq response for openai/gpt-oss-120b with enough tokens."""
import asyncio, json
from pathlib import Path

ENV = Path(__file__).resolve().parents[1] / "backend" / ".env"

def _env(key):
    for line in ENV.read_text(encoding="utf-8").splitlines():
        k, _, v = line.partition("=")
        if k.strip() == key:
            return v.strip().strip('"').strip("'")
    return ""

async def main():
    import httpx
    key = _env("GROQ_API_KEY")
    model = "openai/gpt-oss-120b"
    url = "https://api.groq.com/openai/v1/chat/completions"

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly one word: pong"}],
        "temperature": 0.0,
        "max_tokens": 512,  # Enough for reasoning + answer
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            url,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
        )

    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    reasoning = data["choices"][0]["message"].get("reasoning", "")
    finish_reason = data["choices"][0].get("finish_reason", "")

    print(f"Status: {resp.status_code}")
    print(f"finish_reason: {finish_reason}")
    print(f"content: {content!r}")
    print(f"reasoning (first 200 chars): {reasoning[:200]!r}")

    if content.strip():
        print(f"\n[OK] Model works. content field has: {content!r}")
    elif reasoning.strip():
        print(f"\n[INFO] Only reasoning field has content. Need to adapt the eval pipeline to read from 'reasoning' for this model.")
    else:
        print(f"\n[FAIL] Both content and reasoning are empty.")

if __name__ == "__main__":
    asyncio.run(main())
