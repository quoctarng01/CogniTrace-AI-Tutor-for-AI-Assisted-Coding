import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.routers.review import get_review_card, grade_review_card, GradeRequest

@pytest.mark.asyncio
async def test_get_review_card_generates_challenge_for_misconception():
    """Verify that get_review_card dynamically requests challenge generation from LLM when the card has a misconception tag."""
    mock_card_resp = MagicMock()
    mock_card_resp.status_code = 200
    mock_card_resp.json = MagicMock(return_value=[{
        "id": "card-uuid",
        "trace_id": "trace-uuid",
        "concept_tag": "off_by_one",
        "next_review_date": "2026-06-09",
        "interval_days": 1,
        "easiness_factor": 2.5,
        "repetitions": 0,
    }])
    
    mock_trace_resp = MagicMock()
    mock_trace_resp.status_code = 200
    mock_trace_resp.json = MagicMock(return_value=[{
        "id": "trace-uuid",
        "code": "for i in range(10):",
        "steps": "[]"
    }])
    
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(side_effect=[mock_card_resp, mock_trace_resp])
    
    with patch('app.routers.review.get_current_user', return_value={"id": "user-uuid"}), \
         patch('app.routers.review.get_profile_id_for_user', new_callable=AsyncMock) as mock_get_profile, \
         patch('app.routers.review.httpx.AsyncClient', return_value=mock_client), \
         patch('app.services.llm_router.llm_router.generate_code_repair_challenge', new_callable=AsyncMock) as mock_generate:
         
        mock_get_profile.return_value = "profile-uuid"
        mock_generate.return_value = "def corrected_func(): pass"
        
        result = await get_review_card("card-uuid", authorization="Bearer token")
        
        assert result.concept_tag == "off_by_one"
        assert result.code_repair_challenge == "def corrected_func(): pass"
        mock_generate.assert_called_once_with(
            original_code="for i in range(10):",
            misconception_tag="off_by_one"
        )

@pytest.mark.asyncio
async def test_grade_review_card_calls_grade_code_repair():
    """Verify that grade_review_card delegates to grade_code_repair for cards tagged with misconceptions."""
    req = GradeRequest(
        card_id="card-uuid",
        user_answer="def fixed(): pass"
    )
    
    mock_card_resp = MagicMock()
    mock_card_resp.status_code = 200
    mock_card_resp.json = MagicMock(return_value=[{
        "id": "card-uuid",
        "trace_id": "trace-uuid",
        "concept_tag": "off_by_one",
    }])
    
    mock_trace_resp = MagicMock()
    mock_trace_resp.status_code = 200
    mock_trace_resp.json = MagicMock(return_value=[{
        "id": "trace-uuid",
        "code": "for i in range(10):",
        "steps": "[]"
    }])
    
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(side_effect=[mock_card_resp, mock_trace_resp])
    
    mock_grade_result = {
        "score": 95,
        "rating_suggestion": "easy",
        "feedback": "Perfect repair!"
    }
    
    with patch('app.routers.review.get_current_user', return_value={"id": "user-uuid"}), \
         patch('app.routers.review.get_profile_id_for_user', new_callable=AsyncMock) as mock_get_profile, \
         patch('app.routers.review.httpx.AsyncClient', return_value=mock_client), \
         patch('app.services.llm_router.llm_router.grade_code_repair', new_callable=AsyncMock) as mock_grade:
         
        mock_get_profile.return_value = "profile-uuid"
        mock_grade.return_value = mock_grade_result
        
        result = await grade_review_card(req, authorization="Bearer token")
        
        assert result["score"] == 95
        assert result["rating_suggestion"] == "easy"
        assert result["feedback"] == "Perfect repair!"
        mock_grade.assert_called_once_with(
            "for i in range(10):",
            "off_by_one",
            "def fixed(): pass"
        )
