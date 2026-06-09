"""Unit tests for Custom API Key (github_models_pat) support."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.llm_router import LLMRouter


@pytest.mark.asyncio
async def test_llm_router_uses_custom_pat_override():
    """Verify that stream_explain uses custom PAT parameter over settings default."""
    router = LLMRouter()
    
    # Force a cache miss
    with patch.object(router, '_get_cached', new_callable=AsyncMock) as mock_cached:
        mock_cached.return_value = None
        
        # Mock settings to have a default PAT
        with patch("app.services.llm_router.settings") as mock_settings:
            mock_settings.github_models_pat = "default-server-pat"
            mock_settings.github_models_model = "gpt-4o-mini"
            mock_settings.ollama_cloud_url = "" # disable ollama cloud fallback
            
            # Mock the stream response for _stream_github_models
            mock_stream_context = MagicMock()
            mock_stream_context.__aenter__ = AsyncMock()
            mock_stream_context.__aexit__ = AsyncMock()
            
            # We mock the http client .stream method
            with patch.object(router._http, "stream", return_value=mock_stream_context) as mock_stream:
                # We expect it to raise an error after calling stream, but we can verify the headers
                try:
                    async for _ in router.stream_explain(
                        code="x = 1",
                        line_number=1,
                        line_content="x = 1",
                        locals_dict={},
                        github_models_pat="user-custom-pat-override"
                    ):
                        pass
                except Exception:
                    pass
                
                # Check that stream was called with the custom PAT in headers
                mock_stream.assert_called_once()
                _, kwargs = mock_stream.call_args
                headers = kwargs.get("headers", {})
                assert headers.get("Authorization") == "Bearer user-custom-pat-override"


@pytest.mark.asyncio
async def test_llm_router_falls_back_to_settings_pat():
    """Verify that stream_explain falls back to default settings PAT if no custom PAT provided."""
    router = LLMRouter()
    
    with patch.object(router, '_get_cached', new_callable=AsyncMock) as mock_cached:
        mock_cached.return_value = None
        
        with patch("app.services.llm_router.settings") as mock_settings:
            mock_settings.github_models_pat = "default-server-pat"
            mock_settings.github_models_model = "gpt-4o-mini"
            mock_settings.ollama_cloud_url = ""
            
            mock_stream_context = MagicMock()
            mock_stream_context.__aenter__ = AsyncMock()
            mock_stream_context.__aexit__ = AsyncMock()
            
            with patch.object(router._http, "stream", return_value=mock_stream_context) as mock_stream:
                try:
                    async for _ in router.stream_explain(
                        code="x = 1",
                        line_number=1,
                        line_content="x = 1",
                        locals_dict={},
                        github_models_pat=None
                    ):
                        pass
                except Exception:
                    pass
                
                mock_stream.assert_called_once()
                _, kwargs = mock_stream.call_args
                headers = kwargs.get("headers", {})
                assert headers.get("Authorization") == "Bearer default-server-pat"


@pytest.mark.asyncio
async def test_update_profile_accepts_github_models_pat():
    """Verify that update_profile accepts and sends github_models_pat to Supabase."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value=[{
        "experience_level": "mid",
        "github_models_pat": "new-user-pat-key"
    }])
    
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.patch = AsyncMock(return_value=mock_response)
    
    with patch('app.routers.auth.get_current_user', return_value={"id": "user-uuid"}):
        with patch('app.routers.profiles.httpx.AsyncClient', return_value=mock_client):
            from app.routers.profiles import update_profile
            result = await update_profile(
                github_models_pat="new-user-pat-key",
                authorization="Bearer user-uuid-token"
            )
            
            assert result.get("github_models_pat") == "new-user-pat-key"
            
            # Check patch payload
            mock_client.patch.assert_called_once()
            _, kwargs = mock_client.patch.call_args
            assert kwargs["json"]["github_models_pat"] == "new-user-pat-key"
