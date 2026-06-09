"""Unit tests for Custom OpenAI-compatible endpoint configuration (Option B) support."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.llm_router import LLMRouter, LLMProvider


@pytest.mark.asyncio
async def test_llm_router_uses_custom_openai_stream():
    """Verify that stream_explain routes to CUSTOM_OPENAI when custom_api_key/url are supplied."""
    router = LLMRouter()
    
    with patch.object(router, '_get_cached', new_callable=AsyncMock) as mock_cached:
        mock_cached.return_value = None
        
        # Mock settings to disable Ollama Cloud
        with patch("app.services.llm_router.settings") as mock_settings:
            mock_settings.ollama_cloud_url = ""
            mock_settings.github_models_pat = ""
            
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
                        custom_api_url="https://custom.openai.endpoint/v1",
                        custom_api_key="sk-custom-openai-key",
                        custom_api_model="custom-gpt-4o"
                    ):
                        pass
                except Exception:
                    pass
                
                # Check that stream was called with the custom key and correct model
                mock_stream.assert_called_once()
                args, kwargs = mock_stream.call_args
                url = args[1]
                assert url == "https://custom.openai.endpoint/v1/chat/completions"
                
                headers = kwargs.get("headers", {})
                assert headers.get("Authorization") == "Bearer sk-custom-openai-key"
                
                json_payload = kwargs.get("json", {})
                assert json_payload.get("model") == "custom-gpt-4o"
                assert json_payload.get("stream") is True


@pytest.mark.asyncio
async def test_llm_router_falls_back_when_custom_openai_fails():
    """Verify stream_explain falls back to standard providers if custom_openai fails."""
    router = LLMRouter()
    
    with patch.object(router, '_get_cached', new_callable=AsyncMock) as mock_cached:
        mock_cached.return_value = None
        
        with patch("app.services.llm_router.settings") as mock_settings:
            # Enable GitHub Models as a fallback option
            mock_settings.ollama_cloud_url = ""
            mock_settings.github_models_pat = "server-fallback-pat"
            mock_settings.github_models_model = "gpt-4o-mini"
            
            # Mock _stream_custom_openai to raise an error
            with patch.object(router, '_stream_custom_openai', side_effect=Exception("Connection failed")):
                mock_stream_context = MagicMock()
                mock_stream_context.__aenter__ = AsyncMock()
                mock_stream_context.__aexit__ = AsyncMock()
                
                # Mock GITHUB_MODELS http stream call
                with patch.object(router._http, "stream", return_value=mock_stream_context) as mock_stream:
                    try:
                        async for _ in router.stream_explain(
                            code="x = 1",
                            line_number=1,
                            line_content="x = 1",
                            locals_dict={},
                            custom_api_url="https://custom.openai.endpoint/v1",
                            custom_api_key="sk-custom-openai-key"
                        ):
                            pass
                    except Exception:
                        pass
                    
                    # Verify fallback stream (GitHub models) was invoked instead
                    mock_stream.assert_called_once()
                    _, kwargs = mock_stream.call_args
                    headers = kwargs.get("headers", {})
                    assert headers.get("Authorization") == "Bearer server-fallback-pat"


@pytest.mark.asyncio
async def test_grade_explanation_uses_custom_openai():
    """Verify grade_explanation makes POST requests to custom OpenAI if configured."""
    router = LLMRouter()
    
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [{
            "message": {
                "content": '{"score": 90, "rating_suggestion": "good", "feedback": "Well done!"}'
            }
        }]
    }
    
    with patch.object(router._http, "post", return_value=mock_resp) as mock_post:
        result = await router.grade_explanation(
            code="x = 1",
            steps_json="[]",
            user_answer="variable x updates to 1",
            custom_api_url="https://custom.openai.endpoint/v1",
            custom_api_key="sk-custom-openai-key",
            custom_api_model="custom-model"
        )
        
        assert result.get("score") == 90
        assert result.get("rating_suggestion") == "good"
        
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        url = args[0]
        assert url == "https://custom.openai.endpoint/v1/chat/completions"
        
        headers = kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer sk-custom-openai-key"
        
        json_payload = kwargs.get("json", {})
        assert json_payload.get("model") == "custom-model"
        assert json_payload.get("response_format") == {"type": "json_object"}


@pytest.mark.asyncio
async def test_update_profile_accepts_custom_openai_fields():
    """Verify profiles router PATCH endpoint accepts and updates custom OpenAI columns."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value=[{
        "custom_api_url": "https://newurl.com",
        "custom_api_key": "newkey",
        "custom_api_model": "newmodel"
    }])
    
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.patch = AsyncMock(return_value=mock_response)
    
    with patch('app.routers.auth.get_current_user', return_value={"id": "user-uuid"}):
        with patch('app.routers.profiles.httpx.AsyncClient', return_value=mock_client):
            from app.routers.profiles import update_profile
            result = await update_profile(
                custom_api_url="https://newurl.com",
                custom_api_key="newkey",
                custom_api_model="newmodel",
                authorization="Bearer user-uuid-token"
            )
            
            assert result.get("custom_api_url") == "https://newurl.com"
            assert result.get("custom_api_key") == "newkey"
            assert result.get("custom_api_model") == "newmodel"
            
            mock_client.patch.assert_called_once()
            _, kwargs = mock_client.patch.call_args
            assert kwargs["json"]["custom_api_url"] == "https://newurl.com"
            assert kwargs["json"]["custom_api_key"] == "newkey"
            assert kwargs["json"]["custom_api_model"] == "newmodel"
