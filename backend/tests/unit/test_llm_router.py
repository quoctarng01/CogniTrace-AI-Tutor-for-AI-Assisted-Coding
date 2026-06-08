"""Unit tests for llm_router.py — FIX-CR-01, FIX-MD-03."""
import pytest
from unittest.mock import AsyncMock, patch
from app.services.llm_router import make_cache_key, LLMRouter


def test_make_cache_key_includes_locals():
    """Two identical lines with different variable states must produce different cache keys."""
    code = "result = [x * 2 for x in items]"
    line_number = 1
    line_content = "result = [x * 2 for x in items]"
    
    key1 = make_cache_key(code, line_number, line_content, {"items": [1, 2, 3], "result": [2, 4]})
    key2 = make_cache_key(code, line_number, line_content, {"items": [], "result": []})
    
    # CRITICAL: These must be different because variable state is different
    assert key1 != key2, (
        "Cache key ignores locals_dict — identical lines with different variable state "
        "return the same key. This is CRITICAL-01."
    )


def test_make_cache_key_same_locals_same_key():
    """Identical context produces identical key (cache hit behavior)."""
    code = "x = 1"
    key1 = make_cache_key(code, 1, "x = 1", {"x": 1})
    key2 = make_cache_key(code, 1, "x = 1", {"x": 1})
    assert key1 == key2


def test_make_cache_key_different_line():
    """Different line numbers produce different keys even with same code."""
    code = "x = 1\ny = 2"
    key1 = make_cache_key(code, 1, "x = 1", {})
    key2 = make_cache_key(code, 2, "y = 2", {})
    assert key1 != key2


@pytest.mark.asyncio
async def test_cache_hit_streams_word_by_word():
    """MEDIUM-03: Cache hit should stream tokens word-by-word, not as one blob."""
    router = LLMRouter()
    
    with patch.object(router, '_get_cached', new_callable=AsyncMock) as mock_cached:
        mock_cached.return_value = "This is a cached explanation."  # 5 words
        
        tokens = []
        async for token, provider in router.stream_explain(
            code="x = 1",
            line_number=1,
            line_content="x = 1",
            locals_dict={},
        ):
            if token == "__done__":
                break
            tokens.append(token)
        
        # Should have multiple tokens (one per word), not one blob
        assert len(tokens) > 1, (
            f"MEDIUM-03: Cache hit returned {len(tokens)} token(s) — should be one token per word. "
            f"Tokens: {tokens}"
        )
        assert " ".join(t.strip() for t in tokens) == "This is a cached explanation."


@pytest.mark.asyncio
async def test_grade_explanation_success():
    """Verify that grade_explanation correctly processes success response and parses JSON."""
    router = LLMRouter()
    
    # Mock settings to use GitHub Models
    with patch("app.services.llm_router.settings") as mock_settings:
        mock_settings.github_models_pat = "mock_pat"
        mock_settings.github_models_model = "mock_model"
        
        # Mock the post request on router._http
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = lambda: {
            "choices": [
                {
                    "message": {
                        "content": '{"score": 90, "rating_suggestion": "good", "feedback": "Good job."}'
                    }
                }
            ]
        }
        
        with patch.object(router._http, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            result = await router.grade_explanation(
                code="x = 1",
                steps_json="[]",
                user_answer="x becomes 1"
            )
            
            assert result["score"] == 90
            assert result["rating_suggestion"] == "good"
            assert result["feedback"] == "Good job."
            
            # Verify post was called with correct structure
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert "json" in kwargs
            assert kwargs["json"]["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_diagnose_misconception_success():
    """Verify that diagnose_misconception calls LLM and returns tag and explanation."""
    router = LLMRouter()
    
    with patch("app.services.llm_router.settings") as mock_settings:
        mock_settings.github_models_pat = "mock_pat"
        mock_settings.github_models_model = "mock_model"
        
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json = lambda: {
            "choices": [
                {
                    "message": {
                        "content": '{"tag": "state_mutation_confusion", "explanation": "x mutated."}'
                    }
                }
            ]
        }
        
        with patch.object(router._http, "post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            result = await router.diagnose_misconception(
                code="x = 5\nx = 10",
                checkpoint_type="variable_prediction",
                variable_name="x",
                correct_value="10",
                user_prediction="5",
                lineno=2
            )
            
            assert result["tag"] == "state_mutation_confusion"
            assert result["explanation"] == "x mutated."
            
            mock_post.assert_called_once()

