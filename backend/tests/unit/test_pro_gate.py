"""Unit tests for pro gate — FIX-CR-03."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_is_pro_user_returns_true_for_pro_plan():
    """is_pro_user should return True when Supabase has plan='pro'."""
    # httpx response.json() is synchronous, not async
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value=[{"plan": "pro"}])
    
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)
    
    with patch('app.dependencies.httpx.AsyncClient', return_value=mock_client):
        from app.dependencies import is_pro_user
        result = await is_pro_user("user-uuid-123")
        
        assert result is True, (
            "CRITICAL-03: is_pro_user returned False for a pro user. "
            "Pro gating is non-functional - anyone can access Pro features for free."
        )


@pytest.mark.asyncio
async def test_is_pro_user_returns_false_for_free_plan():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value=[{"plan": "free"}])
    
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)
    
    with patch('app.dependencies.httpx.AsyncClient', return_value=mock_client):
        from app.dependencies import is_pro_user
        result = await is_pro_user("user-uuid-123")
        
        assert result is False


@pytest.mark.asyncio
async def test_is_pro_user_returns_false_for_none():
    from app.dependencies import is_pro_user
    result = await is_pro_user(None)
    assert result is False


@pytest.mark.asyncio
async def test_is_pro_user_returns_false_on_error():
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(side_effect=Exception("Network error"))
    mock_client.__aexit__ = AsyncMock(return_value=None)
    
    with patch('app.dependencies.httpx.AsyncClient', return_value=mock_client):
        from app.dependencies import is_pro_user
        result = await is_pro_user("user-uuid-123")
        
        assert result is False, "Should return False (fail closed) on errors"
