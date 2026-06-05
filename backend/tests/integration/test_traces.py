import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_run_trace_returns_steps_and_trace_id():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/traces/run",
            json={"code": "x = 1\nprint(x)", "language": "python"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "steps" in data
    assert "total_steps" in data

@pytest.mark.asyncio
async def test_run_trace_blocks_side_effects():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/traces/run",
            json={"code": "import os\nprint(os.getcwd())"},
        )
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "SIDE_EFFECT_BLOCKED"
