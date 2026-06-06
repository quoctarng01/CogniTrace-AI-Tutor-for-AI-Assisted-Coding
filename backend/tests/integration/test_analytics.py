import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_track_event_saves_successfully():
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json = MagicMock(return_value={"ok": True})
    
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch("httpx.AsyncClient", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/analytics/track",
                json={
                    "anon_id": "test-anon-id",
                    "event_type": "test_event",
                    "metadata": {"key": "value"}
                },
            )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
