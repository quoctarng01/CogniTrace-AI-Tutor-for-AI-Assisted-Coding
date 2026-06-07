"""Unit tests for LLM providers — FIX-HI-04."""


def test_ollama_cloud_is_primary_provider():
    """HI-04: Ollama Cloud should be the primary (first) LLM provider."""
    from app.services.llm_router import LLMProvider
    
    # Verify enum has both providers
    assert hasattr(LLMProvider, 'OLLAMA_CLOUD'), "LLMProvider enum missing OLLAMA_CLOUD"
    assert hasattr(LLMProvider, 'GITHUB_MODELS'), "LLMProvider enum missing GITHUB_MODELS"
    
    # Enum order reflects priority
    providers = list(LLMProvider)
    assert providers[0] == LLMProvider.OLLAMA_CLOUD, (
        "HI-04: Ollama Cloud should be primary provider (first in enum). "
        "Current code has GitHub Models as the only provider."
    )


def test_stream_ollama_cloud_method_exists():
    """HI-04: stream_explain should have a method for Ollama Cloud streaming."""
    from app.services.llm_router import LLMRouter
    
    router = LLMRouter()
    assert hasattr(router, '_stream_ollama_cloud'), (
        "HI-04: _stream_ollama_cloud method not found. "
        "Ollama Cloud is not implemented."
    )
