"""
LLM Router — routes explanation requests to the best available provider.

Key design:
  - Tries providers in order: Custom OpenAI → Ollama Cloud → GitHub Models.
  - Explanations are cached by SHA-256 before any API call is made.
  - All prompt templates live in `app.services.llm_prompts`.
  - All cache logic lives in `app.services.llm_cache`.
  - This module owns routing, types, and HTTP plumbing only.
"""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

from app.config import settings
from app.services import llm_prompts as prompts
from app.services.llm_cache import ExplanationCache, make_cache_key

logger = logging.getLogger("codescope.llm_router")

# Re-export the cache key helper for backward compatibility — the test
# suite imports `from app.services.llm_router import make_cache_key`.
# Keep this alias so the router module remains the canonical import
# surface for downstream callers.

# ── Types ──────────────────────────────────────────────────────────

class LLMProvider(Enum):
    OLLAMA_CLOUD = "ollama_cloud"
    GITHUB_MODELS = "github_models"
    CUSTOM_OPENAI = "custom_openai"
    GROQ = "groq"

@dataclass
class LLMResponse:
    provider: LLMProvider
    model_name: str
    text: str
    cached: bool = False
    duration_ms: float = 0.0

# ── LLM Router ────────────────────────────────────────────────────

class LLMRouter:
    """
    Routes explanation requests to the best available LLM provider.
    Tries providers in order until one succeeds.
    """

    def __init__(self):
        self._http = httpx.AsyncClient(timeout=30.0)
        self._cache = ExplanationCache(http=self._http)

    async def close(self):
        await self._http.aclose()

    async def stream_explain(
        self,
        code: str,
        line_number: int,
        line_content: str,
        locals_dict: dict,
        ollama_endpoint: str | None = None,
        github_models_pat: str | None = None,
        **kwargs,
    ) -> AsyncGenerator[tuple[str, LLMProvider], None]:
        """
        Stream explanation tokens from the best available provider.
        
        Yields: (token: str, provider: LLMProvider)
        When done: yields ("__done__", provider)
        On error: yields (error_message, provider=LLMProvider.GITHUB_MODELS)
        """
        # 1. Check cache first
        cache_key = make_cache_key(code, line_number, line_content, locals_dict)
        cached_text = await self._cache.get(cache_key)
        if cached_text:
            logger.info("explanation_cache_hit", extra={"cache_key": cache_key})
            # Stream cached text word-by-word for consistent streaming behavior
            for word in cached_text.split():
                yield word + " ", LLMProvider.OLLAMA_CLOUD
            yield "__done__", LLMProvider.OLLAMA_CLOUD
            return

        # 2. Build messages (system = fixed instructions, user = runtime context)
        #    The prompts module owns these strings so the router file stays focused
        #    on routing, not on prompt engineering.
        user_message = prompts.USER_EXPLAIN_TEMPLATE.format(
            code=code[:2000],  # Truncate very long code to avoid token waste
            line_number=line_number,
            line_content=line_content,
            locals_json=json.dumps(locals_dict, indent=2),
        )

        # 3. Try providers in order
        providers_to_try = []

        custom_url = kwargs.get("custom_api_url")
        custom_key = kwargs.get("custom_api_key")
        custom_model = kwargs.get("custom_api_model")

        # 1. Custom OpenAI (highest priority if configured)
        if custom_url and custom_key:
            providers_to_try.append((LLMProvider.CUSTOM_OPENAI, custom_url, cache_key))

        # 2. Groq Cloud (OpenAI-compatible, free tier, fast — preferred when configured)
        if settings.groq_api_key:
            providers_to_try.append((LLMProvider.GROQ, settings.groq_base_url, cache_key))

        # 3. Ollama Cloud (free, no setup)
        if settings.ollama_cloud_url:
            providers_to_try.append((LLMProvider.OLLAMA_CLOUD, settings.ollama_cloud_url, cache_key))

        # 4. GitHub Models (fallback — requires PAT)
        pat = github_models_pat or settings.github_models_pat
        if pat:
            providers_to_try.append((LLMProvider.GITHUB_MODELS, "github_models", cache_key))

        errors = []
        full_text: list[str] = []
        final_provider = LLMProvider.GITHUB_MODELS

        for provider, _endpoint, _cache_key in providers_to_try:
            try:
                if provider == LLMProvider.CUSTOM_OPENAI:
                    async for token in self._stream_custom_openai(prompts.SYSTEM_EXPLAIN, user_message, cache_key, custom_url, custom_key, custom_model):
                        full_text.append(token)
                        yield token, provider
                elif provider == LLMProvider.GROQ:
                    async for token in self._stream_custom_openai(
                        prompts.SYSTEM_EXPLAIN,
                        user_message,
                        cache_key,
                        custom_url=f"{settings.groq_base_url}/chat/completions",
                        custom_key=settings.groq_api_key,
                        custom_model=settings.groq_model,
                    ):
                        full_text.append(token)
                        yield token, provider
                elif provider == LLMProvider.GITHUB_MODELS:
                    async for token in self._stream_github_models(prompts.SYSTEM_EXPLAIN, user_message, cache_key, github_models_pat):
                        full_text.append(token)
                        yield token, provider
                elif provider == LLMProvider.OLLAMA_CLOUD:
                    async for token in self._stream_ollama_cloud(prompts.SYSTEM_EXPLAIN, user_message, cache_key, ollama_endpoint):
                        full_text.append(token)
                        yield token, provider

                # Provider succeeded — record which one
                final_provider = provider
                yield "__done__", provider

                # Write successful explanation to cache for future requests
                if full_text:
                    combined = "".join(full_text)
                    # The pilot study middleware (see app.services.study_session)
                    # may have bound a study-session UUID to this request's
                    # context-var. Forward it so the row is FK-tagged with the
                    # session it belongs to. None for non-pilot traffic.
                    from app.services.study_session import get_current_study_session_id
                    await self._cache.store(
                        cache_key=cache_key,
                        text=combined,
                        provider_used=final_provider.value,
                        model_name=(
                            custom_model or "gpt-4o-mini"
                            if final_provider == LLMProvider.CUSTOM_OPENAI
                            else (
                                settings.groq_model
                                if final_provider == LLMProvider.GROQ
                                else (
                                    settings.github_models_model
                                    if final_provider == LLMProvider.GITHUB_MODELS
                                    else (settings.ollama_model or "llama3.2")
                                )
                            )
                        ),
                        line_number=line_number,
                        study_session_id=get_current_study_session_id(),
                    )
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

    async def stream_explain_blind(
        self,
        code: str,
        line_number: int,
        line_content: str,
        ollama_endpoint: str | None = None,
        github_models_pat: str | None = None,
        **kwargs,
    ) -> AsyncGenerator[tuple[str, LLMProvider], None]:
        """
        A/B ablation: the "blind" / ungrounded half of the demo.

        Same provider chain as `stream_explain`, but:
          - Uses a stripped system prompt (no "read the trace first" instruction).
          - Uses a stripped user prompt (no `locals_dict`).
          - **Skips the cache entirely.** Each demo run hits the provider
            fresh so the audience sees the ungrounded response generate live,
            not a cached answer.

        Yields: (token: str, provider: LLMProvider)
        When done: yields ("__done__", provider)
        On error: yields (error_message, provider=LLMProvider.GITHUB_MODELS)
        """
        user_message = prompts.USER_EXPLAIN_BLIND_TEMPLATE.format(
            code=code[:2000],
            line_number=line_number,
            line_content=line_content,
        )

        providers_to_try = []
        custom_url = kwargs.get("custom_api_url")
        custom_key = kwargs.get("custom_api_key")
        custom_model = kwargs.get("custom_api_model")

        if custom_url and custom_key:
            providers_to_try.append((LLMProvider.CUSTOM_OPENAI, custom_url))
        if settings.groq_api_key:
            providers_to_try.append((LLMProvider.GROQ, settings.groq_base_url))
        if settings.ollama_cloud_url:
            providers_to_try.append((LLMProvider.OLLAMA_CLOUD, settings.ollama_cloud_url))
        pat = github_models_pat or settings.github_models_pat
        if pat:
            providers_to_try.append((LLMProvider.GITHUB_MODELS, "github_models"))

        errors = []
        for provider, _endpoint in providers_to_try:
            try:
                if provider == LLMProvider.CUSTOM_OPENAI:
                    async for token in self._stream_custom_openai(
                        prompts.SYSTEM_EXPLAIN_BLIND,
                        user_message,
                        cache_key="ab-blind-no-cache",
                        custom_url=custom_url,
                        custom_key=custom_key,
                        custom_model=custom_model,
                    ):
                        yield token, provider
                elif provider == LLMProvider.GROQ:
                    async for token in self._stream_custom_openai(
                        prompts.SYSTEM_EXPLAIN_BLIND,
                        user_message,
                        cache_key="ab-blind-no-cache",
                        custom_url=f"{settings.groq_base_url}/chat/completions",
                        custom_key=settings.groq_api_key,
                        custom_model=settings.groq_model,
                    ):
                        yield token, provider
                elif provider == LLMProvider.GITHUB_MODELS:
                    async for token in self._stream_github_models(
                        prompts.SYSTEM_EXPLAIN_BLIND,
                        user_message,
                        cache_key="ab-blind-no-cache",
                        github_models_pat=github_models_pat,
                    ):
                        yield token, provider
                elif provider == LLMProvider.OLLAMA_CLOUD:
                    async for token in self._stream_ollama_cloud(
                        prompts.SYSTEM_EXPLAIN_BLIND,
                        user_message,
                        cache_key="ab-blind-no-cache",
                        ollama_endpoint=ollama_endpoint,
                    ):
                        yield token, provider

                yield "__done__", provider
                return

            except Exception as e:
                logger.error(
                    "ab_blind_provider_failed",
                    extra={"provider": provider.value, "error": str(e)},
                )
                errors.append(f"{provider.value}: {e}")
                continue

        error_msg = (
            "⚠️ No AI provider is available for the blind condition. "
            f"Errors: {'; '.join(errors[:2])}"
        )
        for word in error_msg.split():
            yield word + " ", LLMProvider.OLLAMA_CLOUD
        yield "__done__", LLMProvider.OLLAMA_CLOUD

    async def judge_ab(
        self,
        code: str,
        line_number: int,
        line_content: str,
        locals_dict: dict,
        blind_text: str,
        grounded_text: str,
        github_models_pat: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Score both sides of the A/B using the RQ1 0/1/2 rubric.

        Two non-streaming judge calls (one per side) so the verdict can
        include a per-side reasoning sentence. Returns:
            {
              "blind_score": 0|1|2,
              "blind_reasoning": str,
              "grounded_score": 0|1|2,
              "grounded_reasoning": str,
              "winner": "blind" | "grounded" | "tie",
            }
        Falls back to `prompts.FALLBACK_AB_VERDICT` if every provider fails.
        """
        custom_url = kwargs.get("custom_api_url")
        custom_key = kwargs.get("custom_api_key")
        custom_model = kwargs.get("custom_api_model")

        async def _judge_one(side_text: str) -> dict[str, Any]:
            user_msg = prompts.USER_AB_JUDGE_TEMPLATE.format(
                code=code[:2000],
                line_number=line_number,
                line_content=line_content,
                locals_json=json.dumps(locals_dict, indent=2),
                explanation=side_text[:1500],
            )
            # Try Custom OpenAI first
            if custom_url and custom_key:
                url = custom_url.rstrip("/")
                if not (url.endswith("/chat/completions") or url.endswith("/completions")):
                    if "/v1" in url:
                        url = f"{url}/chat/completions"
                    else:
                        url = f"{url}/v1/chat/completions"
                try:
                    resp = await self._http.post(
                        url,
                        json={
                            "model": custom_model or "gpt-4o-mini",
                            "messages": [
                                {"role": "system", "content": prompts.SYSTEM_AB_JUDGE},
                                {"role": "user", "content": user_msg},
                            ],
                            "response_format": {"type": "json_object"},
                        },
                        headers={
                            "Authorization": f"Bearer {custom_key}",
                            "Content-Type": "application/json",
                        },
                    )
                    if resp.status_code == 200:
                        return json.loads(resp.json()["choices"][0]["message"]["content"])
                except Exception as e:
                    logger.error("ab_judge_custom_openai_failed err=%s", e)

            # Groq (OpenAI-compatible, free tier, fast)
            if settings.groq_api_key:
                try:
                    resp = await self._http.post(
                        f"{settings.groq_base_url}/chat/completions",
                        json={
                            "model": settings.groq_model,
                            "messages": [
                                {"role": "system", "content": prompts.SYSTEM_AB_JUDGE},
                                {"role": "user", "content": user_msg},
                            ],
                            "response_format": {"type": "json_object"},
                        },
                        headers={
                            "Authorization": f"Bearer {settings.groq_api_key}",
                            "Content-Type": "application/json",
                        },
                    )
                    if resp.status_code == 200:
                        return json.loads(resp.json()["choices"][0]["message"]["content"])
                except Exception as e:
                    logger.error("ab_judge_groq_failed err=%s", e)

            # GitHub Models
            pat = github_models_pat or settings.github_models_pat
            if pat:
                model = settings.github_models_model or "openai/gpt-4o-mini"
                try:
                    resp = await self._http.post(
                        "https://models.github.ai/inference/chat/completions",
                        json={
                            "model": model,
                            "messages": [
                                {"role": "system", "content": prompts.SYSTEM_AB_JUDGE},
                                {"role": "user", "content": user_msg},
                            ],
                            "response_format": {"type": "json_object"},
                        },
                        headers={
                            "Authorization": f"Bearer {pat}",
                            "Content-Type": "application/json",
                        },
                    )
                    if resp.status_code == 200:
                        return json.loads(resp.json()["choices"][0]["message"]["content"])
                except Exception as e:
                    logger.error("ab_judge_github_models_failed err=%s", e)

            # Ollama Cloud
            if settings.ollama_cloud_url:
                try:
                    resp = await self._http.post(
                        f"{settings.ollama_cloud_url}/chat",
                        json={
                            "model": settings.ollama_model or "llama3.2",
                            "messages": [
                                {"role": "system", "content": prompts.SYSTEM_AB_JUDGE},
                                {"role": "user", "content": user_msg},
                            ],
                            "stream": False,
                            "format": "json",
                        },
                        headers={"Content-Type": "application/json"},
                    )
                    if resp.status_code == 200:
                        return json.loads(resp.json()["message"]["content"])
                except Exception as e:
                    logger.error("ab_judge_ollama_failed err=%s", e)

            return {"score": 1, "reasoning": "Judge unavailable — defaulting to partial."}

        blind_j = await _judge_one(blind_text)
        grounded_j = await _judge_one(grounded_text)

        b_score = int(blind_j.get("score", 0))
        g_score = int(grounded_j.get("score", 0))

        if g_score > b_score:
            winner = "grounded"
        elif b_score > g_score:
            winner = "blind"
        else:
            winner = "tie"

        return {
            "blind_score": b_score,
            "blind_reasoning": str(blind_j.get("reasoning", ""))[:240],
            "grounded_score": g_score,
            "grounded_reasoning": str(grounded_j.get("reasoning", ""))[:240],
            "winner": winner,
        }

    async def _stream_custom_openai(
        self,
        system_msg: str,
        user_msg: str,
        cache_key: str,
        custom_url: str,
        custom_key: str,
        custom_model: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream from a custom OpenAI-compatible endpoint using true server-sent events."""
        url = custom_url.rstrip("/")
        if not (url.endswith("/chat/completions") or url.endswith("/completions")):
            if "/v1" in url:
                url = f"{url}/chat/completions"
            else:
                url = f"{url}/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {custom_key}",
            "Content-Type": "application/json",
        }
        model = custom_model or "gpt-4o-mini"

        async with self._http.stream(
            "POST",
            url,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                "stream": True,
            },
            headers=headers,
        ) as response:
            if response.status_code >= 400:
                error_body = await response.aread()
                logger.error(
                    f"Custom OpenAI API error: {response.status_code} - {error_body[:200]}"
                )
                raise httpx.HTTPStatusError(
                    f"HTTP {response.status_code}",
                    request=response.request,
                    response=response,
                )

            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue

                payload = line[len("data: "):]

                if payload.strip() == "[DONE]":
                    break

                try:
                    chunk = json.loads(payload)
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue

    async def _stream_github_models(self, system_msg: str, user_msg: str, cache_key: str, github_models_pat: str | None = None) -> AsyncGenerator[str, None]:
        """Stream from GitHub Models API using true server-sent events.

        Uses stream=True so tokens appear as the model generates them,
        instead of waiting for the full response before yielding anything.

        The GitHub Models API is OpenAI-compatible. With stream=True it returns
        newline-delimited JSON chunks in the format:
            data: {"choices":[{"delta":{"content":"Hello"}}]}
            data: [DONE]
        """
        model = settings.github_models_model or "openai/gpt-4o-mini"
        url = "https://models.github.ai/inference/chat/completions"
        pat = github_models_pat or settings.github_models_pat

        headers = {
            "Authorization": f"Bearer {pat}",
            "Content-Type": "application/json",
        }

        # Use stream=True so httpx does not buffer the full response body.
        # We stream line-by-line using aiter_lines().
        async with self._http.stream(
            "POST",
            url,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg},
                ],
                "stream": True,
            },
            headers=headers,
        ) as response:
            if response.status_code >= 400:
                # Read the full error body before raising (only on error, safe to buffer)
                error_body = await response.aread()
                logger.error(
                    f"GitHub API error: {response.status_code} - {error_body[:200]}"
                )
                raise httpx.HTTPStatusError(
                    f"HTTP {response.status_code}",
                    request=response.request,
                    response=response,
                )

            async for line in response.aiter_lines():
                # SSE lines are prefixed with "data: "
                if not line.startswith("data: "):
                    continue

                payload = line[len("data: "):]

                # The stream ends with "data: [DONE]"
                if payload.strip() == "[DONE]":
                    break

                try:
                    chunk = json.loads(payload)
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    # Malformed chunk — skip silently
                    continue

    async def _stream_ollama_cloud(
        self,
        system_msg: str,
        user_msg: str,
        cache_key: str,
        ollama_endpoint: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream from Ollama Cloud API (https://ollama.com/api/chat).
        Primary provider — free, no setup required.
        Uses user-provided ollama_endpoint if available, otherwise falls back to settings.
        """
        base_endpoint = ollama_endpoint or settings.ollama_cloud_url
        if "localhost" in base_endpoint or "127.0.0.1" in base_endpoint:
            base_endpoint = base_endpoint.rstrip("/")
            if base_endpoint.endswith("/api"):
                url = f"{base_endpoint}/chat"
            else:
                url = f"{base_endpoint}/api/chat"
        else:
            url = f"{base_endpoint}/chat"
        headers = {"Content-Type": "application/json"}

        body = {
            "model": settings.ollama_model or "llama3.2",
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
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

    async def grade_explanation(
        self,
        code: str,
        steps_json: str,
        user_answer: str,
        github_models_pat: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Grade the student's answer comparing it to the code and execution trace.
        Returns a dict containing 'score', 'rating_suggestion', and 'feedback'.
        """
        # Pull both prompts from the centralized prompts module so this method
        # never needs to define a prompt itself.
        system_grader_prompt = prompts.SYSTEM_GRADE_EXPLANATION

        user_content = prompts.USER_GRADE_EXPLANATION_TEMPLATE.format(
            code=code,
            steps_json=steps_json,
            user_answer=user_answer,
        )

        # Choose provider based on config
        custom_url = kwargs.get("custom_api_url")
        custom_key = kwargs.get("custom_api_key")
        custom_model = kwargs.get("custom_api_model")

        if custom_url and custom_key:
            url = custom_url.rstrip("/")
            if not (url.endswith("/chat/completions") or url.endswith("/completions")):
                if "/v1" in url:
                    url = f"{url}/chat/completions"
                else:
                    url = f"{url}/v1/chat/completions"
            model = custom_model or "gpt-4o-mini"
            try:
                resp = await self._http.post(
                    url,
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_grader_prompt},
                            {"role": "user", "content": user_content},
                        ],
                        "response_format": {"type": "json_object"},
                    },
                    headers={
                        "Authorization": f"Bearer {custom_key}",
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code == 200:
                    try:
                        return json.loads(resp.json()["choices"][0]["message"]["content"])
                    except Exception as e:
                        logger.error(f"Failed to parse Custom OpenAI grade response: {e}")
            except Exception as e:
                logger.error(f"Custom OpenAI grade request failed: {e}")

        # Choose provider based on config
        pat = github_models_pat or settings.github_models_pat
        if pat:
            # Use GitHub Models (OpenAI-compatible)
            model = settings.github_models_model or "openai/gpt-4o-mini"
            url = "https://models.github.ai/inference/chat/completions"
            try:
                resp = await self._http.post(
                    url,
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_grader_prompt},
                            {"role": "user", "content": user_content},
                        ],
                        "response_format": {"type": "json_object"},
                    },
                    headers={
                        "Authorization": f"Bearer {pat}",
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code == 200:
                    try:
                        return json.loads(resp.json()["choices"][0]["message"]["content"])
                    except Exception as e:
                        logger.error(f"Failed to parse GitHub Models grade response: {e}")
            except Exception as e:
                logger.error(f"GitHub Models grade request failed: {e}")

        # Fallback to Ollama Cloud or general default JSON response
        if settings.ollama_cloud_url:
            url = f"{settings.ollama_cloud_url}/chat"
            try:
                resp = await self._http.post(
                    url,
                    json={
                        "model": settings.ollama_model or "llama3.2",
                        "messages": [
                            {"role": "system", "content": system_grader_prompt},
                            {"role": "user", "content": user_content},
                        ],
                        "stream": False,
                        "format": "json",
                    },
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 200:
                    try:
                        content = resp.json()["message"]["content"]
                        return json.loads(content)
                    except Exception as e:
                        logger.error(f"Failed to parse Ollama grade response: {e}")
            except Exception as e:
                logger.error(f"Ollama grade request failed: {e}")

        # Safe fallback (no provider responded, or every response was unparseable)
        return dict(prompts.FALLBACK_GRADING)

    async def diagnose_misconception(
        self,
        code: str,
        checkpoint_type: str,
        variable_name: str | None,
        correct_value: str,
        user_prediction: str,
        lineno: int,
        github_models_pat: str | None = None,
        checkpoint_mode: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Diagnose a student's misconception by comparing their wrong
        prediction with the correct interpreter state.

        T1-C (Adaptive Checkpoint Difficulty): the ``checkpoint_mode``
        argument selects the system-prompt variant. When omitted (or set
        to ``"direct"``) the prompt is the original
        ``SYSTEM_MISCONCEPTION``. When set to ``"scaffolded"`` or
        ``"contrastive"`` the corresponding mode-aware prompt is used
        and the response is expected to carry an additional ``hint``
        field.

        Returns a dict containing ``tag`` and ``explanation`` (and
        optionally ``hint`` for the adapted modes).
        """
        # Pick the mode-aware prompt. The selection itself (i.e. *which*
        # mode to use) lives in `checkpoint_selector.select_checkpoint_mode`
        # so this method stays routing-only.
        mode = (checkpoint_mode or "direct").lower()
        system_prompt = prompts.system_prompt_for_mode(mode)

        user_content = prompts.USER_MISCONCEPTION_TEMPLATE.format(
            code=code,
            lineno=lineno,
            checkpoint_type=checkpoint_type,
            variable_name=variable_name or 'N/A',
            correct_value=correct_value,
            user_prediction=user_prediction,
        )

        # Choose provider based on config
        custom_url = kwargs.get("custom_api_url")
        custom_key = kwargs.get("custom_api_key")
        custom_model = kwargs.get("custom_api_model")

        if custom_url and custom_key:
            url = custom_url.rstrip("/")
            if not (url.endswith("/chat/completions") or url.endswith("/completions")):
                if "/v1" in url:
                    url = f"{url}/chat/completions"
                else:
                    url = f"{url}/v1/chat/completions"
            model = custom_model or "gpt-4o-mini"
            try:
                resp = await self._http.post(
                    url,
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content},
                        ],
                        "response_format": {"type": "json_object"},
                    },
                    headers={
                        "Authorization": f"Bearer {custom_key}",
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code == 200:
                    try:
                        return json.loads(resp.json()["choices"][0]["message"]["content"])
                    except Exception as e:
                        logger.error(f"Failed to parse Custom OpenAI diagnosis response: {e}")
            except Exception as e:
                logger.error(f"Custom OpenAI diagnosis request failed: {e}")

        # Choose provider based on config
        pat = github_models_pat or settings.github_models_pat
        if pat:
            model = settings.github_models_model or "openai/gpt-4o-mini"
            url = "https://models.github.ai/inference/chat/completions"
            try:
                resp = await self._http.post(
                    url,
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content},
                        ],
                        "response_format": {"type": "json_object"},
                    },
                    headers={
                        "Authorization": f"Bearer {pat}",
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code == 200:
                    try:
                        return json.loads(resp.json()["choices"][0]["message"]["content"])
                    except Exception as e:
                        logger.error(f"Failed to parse GitHub Models diagnosis response: {e}")
            except Exception as e:
                logger.error(f"GitHub Models diagnosis request failed: {e}")

        # Fallback to Ollama Cloud
        if settings.ollama_cloud_url:
            url = f"{settings.ollama_cloud_url}/chat"
            try:
                resp = await self._http.post(
                    url,
                    json={
                        "model": settings.ollama_model or "llama3.2",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content},
                        ],
                        "stream": False,
                        "format": "json",
                    },
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 200:
                    try:
                        content = resp.json()["message"]["content"]
                        return json.loads(content)
                    except Exception as e:
                        logger.error(f"Failed to parse Ollama diagnosis response: {e}")
            except Exception as e:
                logger.error(f"Ollama diagnosis request failed: {e}")

        # Safe fallback (no provider responded, or every response was unparseable)
        return dict(prompts.FALLBACK_MISCONCEPTION)

    async def generate_code_repair_challenge(
        self,
        original_code: str,
        misconception_tag: str,
        github_models_pat: str | None = None,
        **kwargs,
    ) -> str:
        """
        Generate a dynamic programming challenge targeting a specific misconception
        inspired by the student's original trace code.
        """
        # Pull the system/user prompts from the prompts module — this method
        # only routes the request, never defines a prompt.
        # Both system and user templates use {tag} so format once here.
        system_prompt = prompts.SYSTEM_REPAIR_GEN.format(tag=misconception_tag)

        user_content = prompts.USER_REPAIR_GEN_TEMPLATE.format(
            original_code=original_code,
            misconception_tag=misconception_tag,
        )

        # Choose provider based on config
        custom_url = kwargs.get("custom_api_url")
        custom_key = kwargs.get("custom_api_key")
        custom_model = kwargs.get("custom_api_model")

        if custom_url and custom_key:
            url = custom_url.rstrip("/")
            if not (url.endswith("/chat/completions") or url.endswith("/completions")):
                if "/v1" in url:
                    url = f"{url}/chat/completions"
                else:
                    url = f"{url}/v1/chat/completions"
            model = custom_model or "gpt-4o-mini"
            try:
                resp = await self._http.post(
                    url,
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content},
                        ],
                    },
                    headers={
                        "Authorization": f"Bearer {custom_key}",
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                logger.error(f"Custom OpenAI generate challenge failed: {e}")

        # Choose provider
        pat = github_models_pat or settings.github_models_pat
        if pat:
            model = settings.github_models_model or "openai/gpt-4o-mini"
            url = "https://models.github.ai/inference/chat/completions"
            try:
                resp = await self._http.post(
                    url,
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content},
                        ],
                    },
                    headers={
                        "Authorization": f"Bearer {pat}",
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                logger.error(f"GitHub Models generate challenge failed: {e}")

        # Fallback to Ollama Cloud
        if settings.ollama_cloud_url:
            url = f"{settings.ollama_cloud_url}/chat"
            try:
                resp = await self._http.post(
                    url,
                    json={
                        "model": settings.ollama_model or "llama3.2",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content},
                        ],
                        "stream": False,
                    },
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 200:
                    return resp.json()["message"]["content"].strip()
            except Exception as e:
                logger.error(f"Ollama generate challenge failed: {e}")

        # Default fallback code snippet
        return f"""# TUTOR CHALLENGE: Spot and fix the {misconception_tag.replace('_', ' ')} error below.
# Write the corrected code.
def fix_me(items):
    # Bug related to {misconception_tag} is present here
    return items
"""

    async def grade_code_repair(
        self,
        original_code: str,
        misconception_tag: str,
        user_fix: str,
        github_models_pat: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Grade the student's code repair attempt targeting a specific misconception.
        """
        # Pull both prompts from the prompts module — formatter the system
        # prompt with the misconception tag once.
        system_grader_prompt = prompts.SYSTEM_GRADE_REPAIR.format(tag=misconception_tag)

        user_content = prompts.USER_GRADE_REPAIR_TEMPLATE.format(
            original_code=original_code,
            misconception_tag=misconception_tag,
            user_fix=user_fix,
        )

        # Choose provider based on config
        custom_url = kwargs.get("custom_api_url")
        custom_key = kwargs.get("custom_api_key")
        custom_model = kwargs.get("custom_api_model")

        if custom_url and custom_key:
            url = custom_url.rstrip("/")
            if not (url.endswith("/chat/completions") or url.endswith("/completions")):
                if "/v1" in url:
                    url = f"{url}/chat/completions"
                else:
                    url = f"{url}/v1/chat/completions"
            model = custom_model or "gpt-4o-mini"
            try:
                resp = await self._http.post(
                    url,
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_grader_prompt},
                            {"role": "user", "content": user_content},
                        ],
                        "response_format": {"type": "json_object"},
                    },
                    headers={
                        "Authorization": f"Bearer {custom_key}",
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code == 200:
                    try:
                        return json.loads(resp.json()["choices"][0]["message"]["content"])
                    except Exception as e:
                        logger.error(f"Failed to parse Custom OpenAI grade repair response: {e}")
            except Exception as e:
                logger.error(f"Custom OpenAI grade repair request failed: {e}")

        # Choose provider
        pat = github_models_pat or settings.github_models_pat
        if pat:
            model = settings.github_models_model or "openai/gpt-4o-mini"
            url = "https://models.github.ai/inference/chat/completions"
            try:
                resp = await self._http.post(
                    url,
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_grader_prompt},
                            {"role": "user", "content": user_content},
                        ],
                        "response_format": {"type": "json_object"},
                    },
                    headers={
                        "Authorization": f"Bearer {pat}",
                        "Content-Type": "application/json",
                    },
                )
                if resp.status_code == 200:
                    try:
                        return json.loads(resp.json()["choices"][0]["message"]["content"])
                    except Exception as e:
                        logger.error(f"Failed to parse GitHub Models grade repair response: {e}")
            except Exception as e:
                logger.error(f"GitHub Models grade repair request failed: {e}")

        # Fallback to Ollama Cloud
        if settings.ollama_cloud_url:
            url = f"{settings.ollama_cloud_url}/chat"
            try:
                resp = await self._http.post(
                    url,
                    json={
                        "model": settings.ollama_model or "llama3.2",
                        "messages": [
                            {"role": "system", "content": system_grader_prompt},
                            {"role": "user", "content": user_content},
                        ],
                        "stream": False,
                        "format": "json",
                    },
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 200:
                    try:
                        content = resp.json()["message"]["content"]
                        return json.loads(content)
                    except Exception as e:
                        logger.error(f"Failed to parse Ollama grade repair response: {e}")
            except Exception as e:
                logger.error(f"Ollama grade repair request failed: {e}")

        # Safe fallback (no provider responded, or every response was unparseable)
        return dict(prompts.FALLBACK_GRADING)



# Global singleton
llm_router = LLMRouter()
