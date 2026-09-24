"""Cache layer for LLM router explanations (Workstream 6).

Stores successful explanations keyed by SHA-256 hash so identical
(code, line_number, line_content, locals) requests can return the
cached text without calling the upstream provider. This is the
"content-addressable caching" mentioned in the empirical contribution
of the thesis — it provides a deterministic answer surface that lets us
measure whether trace grounding moves the needle.
"""
from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger("cognitrace.llm_cache")


class ExplanationCache:
    """Persistent, content-addressable cache for explanation text."""

    def __init__(self, http: httpx.AsyncClient | None = None):
        self._http = http or httpx.AsyncClient(timeout=10.0)

    async def close(self) -> None:
        await self._http.aclose()

    async def get(self, cache_key: str) -> str | None:
        """Return cached explanation text for `cache_key`, or None if absent."""
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
            logger.warning("cache_fetch_failed err=%s", e)
        return None

    async def store(
        self,
        cache_key: str,
        text: str,
        provider_used: str,
        model_name: str,
        line_number: int | None = None,
        trace_id: str | None = None,
        study_session_id: str | None = None,
    ) -> None:
        """Persist a successful explanation. Errors are logged but not raised.

        Failures here are non-fatal: missing the cache write just means a
        future request will re-call the provider, not a 502 to the user.

        The `study_session_id` is an optional opaque UUID that ties this row
        to the pilot participant's session when the request originated from
        a `X-Study-Session` header. It is `None` for non-pilot traffic.
        """
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
                    "study_session_id": study_session_id,
                },
            )
            if resp.status_code not in (200, 201):
                logger.warning(
                    "cache_store_failed status=%d body=%s",
                    resp.status_code,
                    resp.text[:200],
                )
        except Exception as e:
            logger.warning("cache_store_failed err=%s", e)


# ── Cache-key computation (used by both router and tests) ──────────

def make_cache_key(code: str, line_number: int, line_content: str, locals_dict: dict) -> str:
    """Return the SHA-256 cache key for an explanation request.

    Identical (code, line, locals) → identical key → cached text reused.
    The locals fingerprint is the 16-hex SHA-256 of the JSON-sorted dict.
    """
    import hashlib
    import json

    locals_hash = hashlib.sha256(
        json.dumps(locals_dict, sort_keys=True).encode()
    ).hexdigest()[:16]
    payload = json.dumps({
        "code": code[:200],
        "ln": line_number,
        "lc": line_content[:50],
        "lv": locals_hash,
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()
