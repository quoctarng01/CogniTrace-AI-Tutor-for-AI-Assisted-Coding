import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_trace_endpoint_rate_limited():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Send 31 requests in 60 seconds
        results = []
        for _ in range(31):
            resp = await client.post(
                "/api/traces/run",
                json={"code": "x = 1"},
            )
            results.append(resp.status_code)

        # First 30 should succeed, 31st should be rate limited
        assert results[-1] == 429
