import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.routers.llm import diagnose_checkpoint_error, DiagnoseRequest

@pytest.mark.asyncio
async def test_diagnose_checkpoint_error_unauthenticated():
    """Verify that unauthenticated diagnosis returns the LLM analysis without DB insertions."""
    req = DiagnoseRequest(
        code="x = 5\nx = 10",
        checkpoint_type="variable_prediction",
        variable_name="x",
        correct_value="10",
        user_prediction="5",
        line_number=2,
    )
    
    mock_diagnosis = {
        "tag": "state_mutation_confusion",
        "explanation": "Variable x mutated from 5 to 10."
    }
    
    with patch('app.routers.llm.llm_router.diagnose_misconception', new_callable=AsyncMock) as mock_diagnose:
        mock_diagnose.return_value = mock_diagnosis
        
        result = await diagnose_checkpoint_error(req, authorization=None)
        
        assert result["tag"] == "state_mutation_confusion"
        assert result["explanation"] == "Variable x mutated from 5 to 10."
        mock_diagnose.assert_called_once_with(
            code="x = 5\nx = 10",
            checkpoint_type="variable_prediction",
            variable_name="x",
            correct_value="10",
            user_prediction="5",
            lineno=2,
        )

@pytest.mark.asyncio
async def test_diagnose_checkpoint_error_authenticated():
    """Verify that authenticated diagnosis triggers Supabase insertions for trace and review card."""
    req = DiagnoseRequest(
        code="x = 5\nx = 10",
        checkpoint_type="variable_prediction",
        variable_name="x",
        correct_value="10",
        user_prediction="5",
        line_number=2,
        steps=[{"step": 0}],
    )
    
    mock_diagnosis = {
        "tag": "state_mutation_confusion",
        "explanation": "Variable x mutated."
    }
    
    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 201
    mock_post_resp.json = MagicMock(return_value=[{"id": "new-trace-uuid"}])
    
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(return_value=mock_post_resp)
    
    with patch('app.routers.llm.llm_router.diagnose_misconception', new_callable=AsyncMock) as mock_diagnose, \
         patch('app.routers.llm.get_current_user', return_value={"id": "user-uuid"}), \
         patch('app.routers.llm.get_profile_id_for_user', new_callable=AsyncMock) as mock_get_profile, \
         patch('app.routers.llm.httpx.AsyncClient', return_value=mock_client):
         
        mock_diagnose.return_value = mock_diagnosis
        mock_get_profile.return_value = "profile-uuid"
        
        result = await diagnose_checkpoint_error(req, authorization="Bearer valid-token")
        
        assert result["tag"] == "state_mutation_confusion"
        assert result["explanation"] == "Variable x mutated."
        
        # Verify that client.post was called to insert both trace and review card
        assert mock_client.post.call_count == 2
