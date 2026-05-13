"""Tests for FIX-MD-10: ollama_endpoint not used."""
import inspect


def test_ollama_endpoint_is_used():
    """MEDIUM-10: ollama_endpoint parameter must be used for Ollama Cloud routing."""
    from app.services.llm_router import LLMRouter
    
    source = inspect.getsource(LLMRouter._stream_ollama_cloud)
    
    assert "ollama_endpoint" in source, (
        "MEDIUM-10: _stream_ollama_cloud doesn't use ollama_endpoint. "
        "User's custom endpoint is ignored."
    )
    assert "settings.ollama_cloud_url" in source, (
        "MEDIUM-10: _stream_ollama_cloud should fall back to settings.ollama_cloud_url."
    )
