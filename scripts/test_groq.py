#!/usr/bin/env python3
"""
test_groq.py — One-shot Groq connectivity check.

Reads GROQ_API_KEY from backend/.env, makes a single /chat/completions call,
prints ✅ Groq works (latency=Xms) or the exact error.

Usage:
    py scripts\\test_groq.py
"""

import asyncio
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / "backend" / ".env"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"


def _read_env() -> tuple[str, str]:
    if not ENV_PATH.exists():
        print(f"[FAIL] backend/.env not found at {ENV_PATH}")
        print("        Run scripts/setup_groq.py first, or copy .env.template-pilot.")
        sys.exit(1)

    api_key, model = "", DEFAULT_MODEL
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k == "GROQ_API_KEY":
            api_key = v
        elif k == "GROQ_MODEL":
            if v:
                model = v

    if not api_key or api_key == "gsk_REPLACE_WITH_YOUR_KEY":
        print("[FAIL] GROQ_API_KEY is empty or still the placeholder.")
        print("       Get a key at https://console.groq.com/keys and add it to backend/.env.")
        sys.exit(1)

    if not api_key.startswith("gsk_"):
        print(f"[WARN] Key does not start with 'gsk_'. Got: {api_key[:6]}...")
        print("       Continuing anyway — Groq will reject it if it's wrong.")

    return api_key, model


async def _check(api_key: str, model: str) -> tuple[int, int, str]:
    """Return (status_code, latency_ms, response_text_or_error)."""
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "Reply with one word: 'pong'"},
        ],
        "temperature": 0.0,
        "max_tokens": 10,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(GROQ_URL, headers=headers, json=payload)
    latency_ms = int((time.perf_counter() - start) * 1000)
    if resp.status_code != 200:
        return resp.status_code, latency_ms, resp.text[:300]
    data = resp.json()
    text = data["choices"][0]["message"]["content"].strip()
    return resp.status_code, latency_ms, text


async def main() -> None:
    print("=" * 60)
    print("Groq connectivity check")
    print("=" * 60)
    api_key, model = _read_env()
    masked = api_key[:7] + "..." + api_key[-4:]
    print(f"  Key:   {masked}")
    print(f"  Model: {model}")
    print(f"  URL:   {GROQ_URL}")
    print()
    print("Calling /chat/completions...")
    status, latency_ms, body = await _check(api_key, model)
    if status == 200:
        print(f"\n[OK] Status 200 in {latency_ms}ms")
        print(f"     Reply: {body!r}")
        print("\n[SUCCESS] Groq works. You can run the full eval:")
        print("          py scripts\\evaluate_task_battery.py --output results\\ --runs 1")
    else:
        print(f"\n[FAIL] Status {status} after {latency_ms}ms")
        print(f"       Body: {body}")
        if status == 401:
            print("\n[FIX]  Key is invalid or revoked.")
            print("       1. Go to https://console.groq.com/keys")
            print("       2. Delete the old key, create a new one")
            print("       3. Update GROQ_API_KEY in backend/.env")
        elif status == 429:
            print("\n[FIX]  Rate-limited. Wait 60s or use --provider github.")
        elif status == 404:
            print(f"\n[FIX]  Model {model!r} not found on Groq.")
            print("       Try: llama-3.3-70b-versatile, llama-3.1-8b-instant,")
            print("             mixtral-8x7b-32768, openai/gpt-oss-120b")
        else:
            print(f"\n[FIX]  Unexpected error {status}. See body above.")


if __name__ == "__main__":
    asyncio.run(main())
