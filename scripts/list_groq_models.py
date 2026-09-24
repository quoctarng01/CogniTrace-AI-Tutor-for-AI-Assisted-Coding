"""List all available Groq models for this account."""
import asyncio

import httpx

GROQ_API_URL = "https://api.groq.com/openai/v1/models"


async def main():
    from pathlib import Path
    env_path = Path(__file__).parent.parent / "backend" / ".env"
    key = ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        k, _, v = line.partition("=")
        if k.strip() == "GROQ_API_KEY":
            key = v.strip().strip('"').strip("'")
            break

    if not key or key.startswith("gsk_REPLACE"):
        print("[ERROR] No valid GROQ_API_KEY found in backend/.env")
        return

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(
            GROQ_API_URL,
            headers={"Authorization": f"Bearer {key}"},
        )

    if resp.status_code != 200:
        print(f"[ERROR] {resp.status_code}: {resp.text[:200]}")
        return

    models = sorted(m["id"] for m in resp.json()["data"])
    print(f"Found {len(models)} models available on your Groq account:\n")
    for m in models:
        print(f"  {m}")


if __name__ == "__main__":
    asyncio.run(main())
