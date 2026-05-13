"""
LLM Router — GitHub Models only.

Key design:
  - GitHub Models (models.github.ai) is the ONLY provider — uses your GitHub PAT.
  - Explanations are cached by SHA-256 before any API call is made.
"""
from __future__ import annotations

import json
import hashlib
import logging
from typing import AsyncGenerator, Optional
from dataclasses import dataclass
from enum import Enum

import httpx

from app.config import settings
from app.services.rate_limit import check_rate_limit

logger = logging.getLogger("codescope.llm_router")

# ── Types ──────────────────────────────────────────────────────────

class LLMProvider(Enum):
    OLLAMA_CLOUD = "ollama_cloud"
    GITHUB_MODELS = "github_models"

@dataclass
class LLMResponse:
    provider: LLMProvider
    model_name: str
    text: str
    cached: bool = False
    duration_ms: float = 0.0

# ── System Prompt ─────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a Python code educator. Explain why a specific line of
code exists, given the current execution context.

Current line: {line_content}
Local variable state:
{locals_json}

Instructions:
- Explain WHY this specific line is necessary given the current state.
- Do NOT explain what the code does generally — explain the specific execution reason.
- Be concise: 2-3 sentences maximum.
- Include a brief code snippet if it clarifies the explanation.
- If the line involves a branch decision (if/else), explain which branch was taken and why.
- If the line is in a loop, explain the iteration context.
"""

# ── Cache Key ─────────────────────────────────────────────────────

def make_cache_key(code: str, line_number: int, line_content: str, locals_dict: dict) -> str:
    """
    Content-addressable cache key for explanations.
    Two identical (code, line_number, line_content, locals) requests return the same explanation.
    """
    locals_hash = hashlib.sha256(
        json.dumps(locals_dict, sort_keys=True).encode()
    ).hexdigest()[:16]
    payload = json.dumps({
        "code": code[:200],        # First 200 chars of code
        "ln": line_number,
        "lc": line_content[:50],   # First 50 chars of line
        "lv": locals_hash,          # Variable-state fingerprint
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


# ── LLM Router ────────────────────────────────────────────────────

class LLMRouter:
    """
    Routes explanation requests to the best available LLM provider.
    Tries providers in order until one succeeds.
    """
    
    def __init__(self):
        self._http = httpx.AsyncClient(timeout=30.0)
    
    async def close(self):
        await self._http.aclose()
    
    async def stream_explain(
        self,
        code: str,
        line_number: int,
        line_content: str,
        locals_dict: dict,
        ollama_endpoint: str | None = None,
    ) -> AsyncGenerator[tuple[str, LLMProvider], None]:
        """
        Stream explanation tokens from the best available provider.
        
        Yields: (token: str, provider: LLMProvider)
        When done: yields ("__done__", provider)
        On error: yields (error_message, provider=LLMProvider.GITHUB_MODELS)
        """
        # 1. Check cache first
        cache_key = make_cache_key(code, line_number, line_content, locals_dict)
        cached_text = await self._get_cached(cache_key)
        if cached_text:
            logger.info("explanation_cache_hit", extra={"cache_key": cache_key})
            # Stream cached text word-by-word for consistent streaming behavior
            for word in cached_text.split():
                yield word + " ", LLMProvider.OLLAMA_CLOUD
            yield "__done__", LLMProvider.OLLAMA_CLOUD
            return
        
        # 2. Build prompt
        prompt = SYSTEM_PROMPT.format(
            line_content=line_content,
            locals_json=json.dumps(locals_dict, indent=2),
        )
        
        # 3. Try providers in order
        providers_to_try = []
        
        # 1. Ollama Cloud (primary — free, no setup)
        if settings.ollama_cloud_url:
            providers_to_try.append((LLMProvider.OLLAMA_CLOUD, settings.ollama_cloud_url, cache_key))
        
        # 2. GitHub Models (fallback — requires PAT)
        if settings.github_models_pat:
            providers_to_try.append((LLMProvider.GITHUB_MODELS, "github_models", cache_key))
        
        errors = []
        
        for provider, _endpoint, _cache_key in providers_to_try:
            try:
                if provider == LLMProvider.GITHUB_MODELS:
                    async for token in self._stream_github_models(prompt, cache_key):
                        yield token, provider
                elif provider == LLMProvider.OLLAMA_CLOUD:
                    async for token in self._stream_ollama_cloud(prompt, cache_key, ollama_endpoint):
                        yield token, provider
                
                # Provider succeeded
                yield "__done__", provider
                return
                
            except Exception as e:
                logger.error(
                    "llm_provider_failed",
                    extra={"provider": provider.value, "error": str(e), "error_type": type(e).__name__},
                )
                errors.append(f"{provider.value}: {e}")
                continue
        
        # All providers failed - yield a helpful message
        error_msg = (
            "⚠️ No AI provider is available. "
            "Please set OLLAMA_CLOUD_URL or GITHUB_MODELS_PAT in your .env file.\n\n"
            f"Errors encountered: {'; '.join(errors[:2])}"
        )
        for word in error_msg.split():
            yield word + " ", LLMProvider.OLLAMA_CLOUD
        yield "__done__", LLMProvider.OLLAMA_CLOUD
    
    async def _stream_github_models(self, prompt: str, cache_key: str) -> AsyncGenerator[str, None]:
        """Stream from GitHub Models API (OpenAI-compatible format).
        
        Uses non-streaming httpx request then manually yields tokens for compatibility.
        """
        model = settings.github_models_model or "openai/gpt-4o-mini"
        timeout = 30.0
        
        url = "https://models.github.ai/inference/chat/completions"
        pat = settings.github_models_pat
        
        headers = {
            "Authorization": f"Bearer {pat}",
            "Content-Type": "application/json",
        }
        
        # Use shared HTTP client for connection pooling
        response = await self._http.post(
            url,
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,  # Non-streaming for compatibility
            },
            headers=headers,
        )
        
        if response.status_code >= 400:
            logger.error(f"GitHub API error: {response.status_code} - {response.text}")
            raise httpx.HTTPStatusError(
                f"HTTP {response.status_code}",
                request=response.request,
                response=response,
            )
        
        # Parse the non-streaming response
        data = response.json()
        choices = data.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            content = message.get("content", "")
            
            # Yield tokens one by one (word by word for streaming effect)
            words = content.split()
            for word in words:
                yield word + " "
    
    async def _stream_ollama_cloud(
        self,
        prompt: str,
        cache_key: str,
        ollama_endpoint: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream from Ollama Cloud API (https://ollama.com/api/chat).
        Primary provider — free, no setup required.
        Uses user-provided ollama_endpoint if available, otherwise falls back to settings.
        """
        url = f"{ollama_endpoint or settings.ollama_cloud_url}/chat"
        headers = {"Content-Type": "application/json"}
        
        body = {
            "model": settings.ollama_model or "llama3.2",
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        }
        
        response = await self._http.post(url, json=body, headers=headers)
        if response.status_code >= 400:
            logger.error(f"Ollama Cloud error: {response.status_code}")
            raise httpx.HTTPStatusError(
                f"HTTP {response.status_code}",
                request=response.request,
                response=response,
            )

        async for line in response.aiter_lines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                if "message" in data and "content" in data["message"]:
                    content = data["message"]["content"]
                    # Stream word by word
                    for word in content.split():
                        yield word + " "
            except json.JSONDecodeError:
                continue
    
    # ── Cache Layer ───────────────────────────────────────────────
    
    async def _get_cached(self, cache_key: str) -> Optional[str]:
        """Fetch cached explanation from Supabase."""
        if not settings.supabase_url or not settings.supabase_service_key:
            return None
        
        try:
            resp = await self._http.post(
                f"{settings.supabase_url}/rest/v1/rpc/get_explanation",
                headers={
                    "apikey": settings.supabase_service_key,
                    "Authorization": f"Bearer {settings.supabase_service_key}",
                    "Content-Type": "application/json",
                },
                json={"p_cache_key": cache_key},
            )
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    return data[0].get("explanation_text")
        except Exception as e:
            logger.warning("cache_fetch_failed", extra={"error": str(e)})
        
        return None
    
    async def _store_cached(
        self,
        cache_key: str,
        text: str,
        provider_used: str,
        model_name: str,
        trace_id: str | None = None,
        line_number: int | None = None,
    ) -> None:
        """Store explanation in Supabase cache."""
        if not settings.supabase_url or not settings.supabase_service_key:
            return
        
        try:
            resp = await self._http.post(
                f"{settings.supabase_url}/rest/v1/explanations",
                headers={
                    "apikey": settings.supabase_service_key,
                    "Authorization": f"Bearer {settings.supabase_service_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=representation",
                },
                json={
                    "cache_key": cache_key,
                    "explanation_text": text,
                    "model_used": provider_used,
                    "model_name": model_name,
                    "cached": True,
                    "trace_id": trace_id,
                    "line_number": line_number,
                },
            )
            if resp.status_code not in (200, 201):
                logger.warning(
                    "cache_store_failed",
                    extra={"error": f"status={resp.status_code}, body={resp.text[:200]}"}
                )
        except Exception as e:
            logger.warning("cache_store_failed", extra={"error": str(e)})


# Global singleton
llm_router = LLMRouter()
