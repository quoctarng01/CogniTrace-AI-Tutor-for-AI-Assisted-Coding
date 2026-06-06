"""Unit tests for profiles — FIX-HI-03."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_get_profile_queries_supabase():
    """HI-03: get_profile should fetch from Supabase, not return placeholders."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value=[{
        "id": "profile-uuid",
        "user_id": "user-uuid",
        "experience_level": "junior",
        "ai_tools_usage": "heavy",
        "plan": "pro",
    }])
    
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)
    
    with patch('app.routers.auth.get_current_user', return_value={"id": "user-uuid"}):
        with patch('app.routers.profiles.httpx.AsyncClient', return_value=mock_client):
            from app.routers.profiles import get_profile
            result = await get_profile(authorization="Bearer user-uuid-token")
            
            assert result.get("plan") == "pro", (
                f"HI-03: get_profile returned placeholder data: {result}. "
                "Must query Supabase for real profile data."
            )
            assert result.get("id") != "placeholder", "Should not return placeholder id"


@pytest.mark.asyncio
async def test_update_profile_writes_to_supabase():
    """HI-03: update_profile should write to Supabase, not return placeholders."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value=[{
        "experience_level": "mid",
        "ai_tools_usage": "moderate",
    }])
    
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.patch = AsyncMock(return_value=mock_response)
    
    with patch('app.routers.auth.get_current_user', return_value={"id": "user-uuid"}):
        with patch('app.routers.profiles.httpx.AsyncClient', return_value=mock_client):
            from app.routers.profiles import update_profile
            result = await update_profile(
                experience_level="mid",
                authorization="Bearer user-uuid-token"
            )
            
            assert result.get("experience_level") == "mid", (
                "HI-03: update_profile returned placeholder data."
            )
