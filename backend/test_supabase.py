import httpx
import asyncio

async def test():
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Try with a valid UUID format
        r = await client.post(
            'https://cyzpvltrayvpdooxgmaj.supabase.co/rest/v1/traces',
            headers={
                'apikey': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImN5enB2bHRyYXl2cGRvb3hnbWFqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3ODEzOTc3NCwiZXhwIjoyMDkzNzE1Nzc0fQ.0JMJHwPfqXJW_cIEb1kIcQhXSJ4j28yEVNz64R8vWIM',
                'Content-Type': 'application/json',
                'Prefer': 'return=representation'
            },
            json={
                'user_id': '12345678-1234-1234-1234-123456789012',  # Use valid UUID format
                'code': 'print(1)',
                'share_token': 'test123'
            }
        )
        print(f"POST status: {r.status_code}")
        print(f"POST response: {r.text}")

asyncio.run(test())
