#!/usr/bin/env python3
"""Quick Groq API test with any model."""
import asyncio, time, sys
from pathlib import Path

ENV = Path(__file__).resolve().parents[1] / "backend" / ".env"

def _env(key):
    for line in ENV.read_text(encoding="utf-8").splitlines():
        k, _, v = line.partition("=")
        if k.strip() == key:
            return v.strip().strip('"').strip("'")
    return ""

async def main():
    key = _env("GROQ_API_KEY")
    if not key or key.startswith("gsk_REPLACE"):
        print("[ERROR] No key"); sys.exit(1)

    # Test both chat and OSS-specific models
    tests = [
        ("llama-3.3-70b-versatile", "https://api.groq.com/openai/v1/chat/completions"),
        ("openai/gpt-oss-120b", "https://api.groq.com/openai/v1/chat/completions"),
        ("allam-2-7b", "https://api.groq.com/openai/v1/chat/completions"),
    ]

    for model, url in tests:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Reply with one word: pong"}],
            "temperature": 0.0, "max_tokens": 10, "stream": False,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            t0 = time.perf_counter()
            resp = await client.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, json=payload)
            ms = int((time.perf_counter()-t0)*1000)
        status = resp.status_code
        body = resp.json() if status == 200 else resp.text[:120]
        icon = "[OK]" if status == 200 else "[FAIL]"
        print(f"{icon} [{status}] {model:<35} {ms:>5}ms  {body if status != 200 else resp.json()['choices'][0]['message']['content'].strip()!r}")

if __name__ == "__main__":
    import httpx
    asyncio.run(main())
