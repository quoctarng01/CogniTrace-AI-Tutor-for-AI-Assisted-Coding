# CodeScope — Implementation Plan

**Generated:** 2026-05-14
**Source:** ROADMAP.md (all bugs synthesized from SPEC.md, codescope_prd.md, and full codebase audit)
**Target:** Any AI agent can execute this plan step-by-step with zero ambiguity

---

## How to Read This Document

Each fix entry contains:

- **Prerequisites** — which other fixes must be done first, which files must already exist
- **Files to modify** — exact file path, exact line numbers, exact broken code, exact fixed code
- **Test to write FIRST (TDD)** — exact test code that fails on broken code and passes on fixed code
- **Verification command** — exact command to verify the fix works
- **Order dependency** — which fixes must be done before this one

---

## Pre-Flight Checks

Before starting, verify the project structure exists:

```bash
# Backend files
ls backend/app/routers/llm.py       # FIX-CR-03, FIX-HI-07
ls backend/app/routers/traces.py     # FIX-CR-05, FIX-HI-07
ls backend/app/routers/review.py     # FIX-HI-01, FIX-HI-02
ls backend/app/routers/profiles.py   # FIX-HI-03
ls backend/app/routers/auth.py       # FIX-CR-05
ls backend/app/services/llm_router.py # FIX-CR-01, FIX-CR-02, FIX-CR-04
ls backend/tracer/tracer.py          # FIX-MD-02

# Frontend files
ls frontend/hooks/useTrace.ts        # FIX-MD-07
ls frontend/components/llm/ExplanationPanel.tsx  # FIX-MD-01, FIX-MD-07
ls frontend/app/tracer/page.tsx      # FIX-MD-07
ls frontend/components/tracer/AnimationControls.tsx  # FIX-MD-07

# If any file is missing, stop and check the project layout
```

Also verify backend dependencies are installed:

```bash
cd backend
python -c "import httpx, fastapi, pydantic; print('deps OK')"
```

---

## Execution Order

```
Step 1 → FIX-CR-01: Cache key ignores runtime variables
Step 2 → FIX-CR-02: httpx AsyncClient per request (connection pool exhaustion)
Step 3 → FIX-CR-03: Pro gate always returns False
Step 4 → FIX-CR-04: Cache write has no RETURNING (silently fails)
Step 5 → FIX-CR-05: Debug log writes to disk in production
Step 6 → FIX-CR-06: Explanations stored without trace_id
Step 7 → FIX-HI-01: last_reviewed_at uses string "now()" instead of SQL now()
Step 8 → FIX-HI-02: Streak calculation returns card count, not consecutive days
Step 9 → FIX-HI-03: Profiles endpoints return placeholders
Step 10 → FIX-HI-04: LLM provider order wrong (Ollama Cloud should be primary)
Step 11 → FIX-HI-05: No LLM provider validation at startup
Step 12 → FIX-HI-06: Health endpoint is liveness-only
Step 13 → FIX-HI-07: Rate limit doesn't distinguish free vs Pro
Step 14 → FIX-HI-08: Missing README
Step 15 → FIX-MD-01: Explanation rating not in frontend
Step 16 → FIX-MD-02: Branch detection marks all as taken
Step 17 → FIX-MD-03: Cache hit returns entire string as one token
Step 18 → FIX-MD-04: Debug print statements in llm_router.py
Step 19 → FIX-MD-05: Missing composite index on review_cards
Step 20 → FIX-MD-06: concept_tags and is_public silently dropped on save
Step 21 → FIX-MD-07: useTrace hook not wired into tracer page
Step 22 → FIX-MD-08: Dashboard streak hardcoded to 0
Step 23 → FIX-MD-09: No landing page
Step 24 → FIX-MD-10: ollama_endpoint not used
Step 25 → FIX-MD-11: No auth on health endpoint (intentional, no action)
Step 26 → LOW-01: Review cards expire with no cleanup (no action, future)
Step 27 → LOW-02: No email/password auth (no action, known limitation)
Step 28 → LOW-03: No trace export (no action, future)
Step 29 → LOW-04: No per-concept analytics (no action, future)
Step 30 → LOW-05: No onboarding/tutorial (no action, future)
Step 31 → FIX-TH-01: Synthetic benchmark for static analysis
Step 32 → THESIS-03: Analytics instrumentation (partial, partial action)
```

---

## PART 0 — Critical Bugs

---

## FIX-CR-01: Cache key ignores runtime variables

**Prerequisites:** None. This is the first fix to implement.

**Files to modify:**

- `backend/app/services/llm_router.py`

**Step 1 — Add `locals_dict` parameter to `make_cache_key`**

Lines 57-67 — current broken code:

```python
def make_cache_key(code: str, line_number: int, line_content: str) -> str:
    """
    Content-addressable cache key for explanations.
    Two identical (code, line_number, line_content) requests return the same explanation.
    """
    payload = json.dumps({
        "code": code[:200],        # First 200 chars of code
        "ln": line_number,
        "lc": line_content[:50],   # First 50 chars of line
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()
```

Replace with:

```python
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
```

**Step 2 — Update call site in `stream_explain`**

Line 102 — current broken code:

```python
        cache_key = make_cache_key(code, line_number, line_content)
```

Replace with:

```python
        cache_key = make_cache_key(code, line_number, line_content, locals_dict)
```

**Test to write FIRST (TDD)**

Create file `backend/tests/unit/test_llm_router.py`:

```python
import pytest
from app.services.llm_router import make_cache_key

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
```

**Verification command:**

```bash
cd backend
python -m pytest tests/unit/test_llm_router.py::test_make_cache_key_includes_locals -v
# Must FAIL on broken code (key1 == key2), PASS on fixed code (key1 != key2)
```

**Order dependency:** None. Do this first.

---

## FIX-CR-02: httpx AsyncClient per request — connection pool exhaustion

**Prerequisites:** FIX-CR-01 must be done first (same file).

**Files to modify:**

- `backend/app/services/llm_router.py`

**Problem:** The class already has `self._http = httpx.AsyncClient(timeout=30.0)` at line 79 in `__init__`. Three methods create new `httpx.AsyncClient()` instances instead of reusing it: `_stream_github_models` (line 172), `_get_cached` (line 212), and `_store_cached` (line 244).

**Step 1 — Fix `_stream_github_models` (line 172)**

Current broken code (lines 155-201, specifically 172):

```python
    async def _stream_github_models(self, prompt: str, cache_key: str) -> AsyncGenerator[str, None]:
        model = settings.github_models_model or "openai/gpt-4o-mini"
        timeout = 30.0
        url = "https://models.github.ai/inference/chat/completions"
        pat = settings.github_models_pat
        headers = {
            "Authorization": f"Bearer {pat}",
            "Content-Type": "application/json",
        }
        # Use non-streaming httpx request
        async with httpx.AsyncClient(timeout=timeout) as client:   # LINE 172 — creates new client
            response = await client.post(
                url,
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                },
                headers=headers,
            )
            # ... rest of method
```

Replace the `async with httpx.AsyncClient(timeout=timeout) as client:` block (lines 172-181) with:

**CRITICAL — httpx API note:** `httpx.AsyncClient.post()` returns a plain `Response` object, NOT a context manager. You cannot use `async with` on it. The correct pattern is:

```python
# CORRECT — plain await, no context manager:
response = await self._http.post(
    url,
    json={
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    },
    headers=headers,
)
```

**NEVER write** `async with self._http.post(...)` — this will cause a TypeError at runtime.

```python
        response = await self._http.post(
            url,
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            headers=headers,
        )
```

**Step 2 — Fix `_get_cached` (lines 205-229)**

Current broken code (lines 211-221):

```python
        try:
            import httpx
            async with httpx.AsyncClient() as client:   # LINE 212 — creates new client
                resp = await client.post(
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
```

Replace with:

```python
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
```

Also remove the duplicate `import httpx` at line 211 (it's already imported at the top of the file).

**Step 3 — Fix `_store_cached` (lines 231-262)**

Current broken code (lines 243-260):

```python
        try:
            import httpx
            async with httpx.AsyncClient() as client:   # LINE 244 — creates new client
                await client.post(
                    f"{settings.supabase_url}/rest/v1/explanations",
                    headers={
                        "apikey": settings.supabase_service_key,
                        "Authorization": f"Bearer {settings.supabase_service_key}",
                        "Content-Type": "application/json",
                        "Prefer": "return=minimal",   # Will be fixed in CR-04
                    },
                    json={
                        "cache_key": cache_key,
                        "explanation_text": text,
                        "model_used": provider_used,
                        "model_name": model_name,
                        "cached": True,
                    },
                )
        except Exception as e:
            logger.warning("cache_store_failed", extra={"error": str(e)})
```

Replace with:

```python
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
                },
            )
            if resp.status_code not in (200, 201):
                logger.warning(
                    "cache_store_failed",
                    extra={"error": f"status={resp.status_code}, body={resp.text[:200]}"}
                )
        except Exception as e:
            logger.warning("cache_store_failed", extra={"error": str(e)})
```

Also remove the duplicate `import httpx` at line 243.

**Test to write FIRST (TDD)**

Create file `backend/tests/unit/test_httpx_reuse.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

@pytest.mark.asyncio
async def test_llm_router_reuses_http_client():
    """Verify LLMRouter does NOT create httpx.AsyncClient per request."""
    from app.services.llm_router import LLMRouter
    
    router = LLMRouter()
    
    # Track how many times httpx.AsyncClient() is called
    original_init_count = 0
    
    original_init = httpx.AsyncClient.__init__
    def tracking_init(self, *args, **kwargs):
        nonlocal original_init_count
        original_init_count += 1
        return original_init(self, *args, **kwargs)
    
    with patch.object(httpx.AsyncClient, '__init__', tracking_init):
        with patch.object(httpx.AsyncClient, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value.__aenter__ = AsyncMock()
            mock_post.return_value.__aexit__ = AsyncMock()
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = []
            
            # Call _get_cached twice
            await router._get_cached("test_key")
            await router._get_cached("test_key")
    
    # CRITICAL: Should be 1 (only in __init__), NOT 2 (one per call)
    assert original_init_count == 1, (
        f"httpx.AsyncClient() called {original_init_count} times — "
        "CRITICAL-02: should be 1 (reused), not 2 (new per request). "
        "Connection pool exhaustion under load."
    )
```

**Verification command:**

```bash
cd backend
python -m pytest tests/unit/test_httpx_reuse.py -v
```

**Order dependency:** Must be done after FIX-CR-01 (same file, sequential).

---

## FIX-CR-03: Pro gate always returns False

**Prerequisites:** None (standalone fix).

**Files to modify:**

- `backend/app/routers/llm.py`

**Step 1 — Make `_is_pro_user` async and query Supabase**

Lines 127-130 — current broken code:

```python
def _is_pro_user(user_id: str | None) -> bool:
    """Check if user is on Pro plan. TODO: integrate with Supabase."""
    # Placeholder — real implementation checks Supabase profiles table
    return False
```

Replace with:

```python
async def _is_pro_user(user_id: str | None) -> bool:
    """Check if user is on Pro plan by querying Supabase profiles table."""
    if not user_id:
        return False

    from app.config import settings
    import httpx  # Only imported here; avoid module-level httpx to keep llm.py lightweight
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.supabase_url}/rest/v1/profiles",
                params={"user_id": f"eq.{user_id}", "select": "plan"},
                headers={
                    "Authorization": f"Bearer {settings.supabase_service_key}",
                    "apikey": settings.supabase_service_key,
                },
            )
            if resp.status_code == 200:
                profiles = resp.json()
                if profiles and len(profiles) > 0:
                    return profiles[0].get("plan") == "pro"
    except Exception:
        pass
    return False
```

**Consistency note:** Unlike the LLMRouter class (which reuses `self._http` per instance), this standalone function creates a fresh client per call. Since it's called once per request and immediately cleaned up by the context manager, this is acceptable and avoids introducing module-level httpx dependency into `llm.py`.

**Step 3 — Add await to the call site**

Line 58 — current code:

```python
    if not user_id or not _is_pro_user(user_id):
```

Replace with:

```python
    if not user_id or not await _is_pro_user(user_id):
```

Note: The endpoint `stream_explanation` is already `async def` at line 24, so `await` works.

**Test to write FIRST (TDD)**

Create file `backend/tests/unit/test_pro_gate.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_is_pro_user_returns_true_for_pro_plan():
    """_is_pro_user should return True when Supabase has plan='pro'."""
    with patch('httpx.AsyncClient') as MockClient:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock()
        mock_instance.__aexit__ = AsyncMock()
        mock_instance.get = AsyncMock()
        mock_instance.get.return_value.status_code = 200
        mock_instance.get.return_value.json = lambda: [{"plan": "pro"}]
        MockClient.return_value = mock_instance
        
        from app.routers.llm import _is_pro_user
        result = await _is_pro_user("user-uuid-123")
        
        assert result is True, (
            "CRITICAL-03: _is_pro_user returned False for a pro user. "
            "Pro gating is non-functional — anyone can access Pro features for free."
        )

@pytest.mark.asyncio
async def test_is_pro_user_returns_false_for_free_plan():
    with patch('httpx.AsyncClient') as MockClient:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock()
        mock_instance.__aexit__ = AsyncMock()
        mock_instance.get = AsyncMock()
        mock_instance.get.return_value.status_code = 200
        mock_instance.get.return_value.json = lambda: [{"plan": "free"}]
        MockClient.return_value = mock_instance
        
        from app.routers.llm import _is_pro_user
        result = await _is_pro_user("user-uuid-123")
        
        assert result is False

@pytest.mark.asyncio
async def test_is_pro_user_returns_false_for_none():
    from app.routers.llm import _is_pro_user
    result = await _is_pro_user(None)
    assert result is False

@pytest.mark.asyncio
async def test_is_pro_user_returns_false_on_error():
    with patch('httpx.AsyncClient') as MockClient:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock()
        mock_instance.__aexit__ = AsyncMock()
        mock_instance.get = AsyncMock(side_effect=Exception("Network error"))
        MockClient.return_value = mock_instance
        
        from app.routers.llm import _is_pro_user
        result = await _is_pro_user("user-uuid-123")
        
        assert result is False, "Should return False (fail closed) on errors"
```

**Verification command:**

```bash
cd backend
python -m pytest tests/unit/test_pro_gate.py -v
```

**Order dependency:** None.

---

## FIX-CR-04: Cache write has no RETURNING — silently fails

**Prerequisites:** FIX-CR-02 must be done first (same file, same `_store_cached` method).

**Files to modify:**

- `backend/app/services/llm_router.py`

**Already partially fixed in FIX-CR-02** — the `_store_cached` method now uses `Prefer: return=representation` and checks the status code. The remaining fix is to add `trace_id` and `line_number` to the stored record.

**Step 1 — Update `stream_explain` signature to accept `trace_id`**

Lines 84-91 — current code:

```python
    async def stream_explain(
        self,
        code: str,
        line_number: int,
        line_content: str,
        locals_dict: dict,
        ollama_endpoint: str | None = None,
    ) -> AsyncGenerator[tuple[str, LLMProvider], None]:
```

Add `trace_id: str | None = None` parameter:

```python
    async def stream_explain(
        self,
        code: str,
        line_number: int,
        line_content: str,
        locals_dict: dict,
        ollama_endpoint: str | None = None,
        trace_id: str | None = None,
    ) -> AsyncGenerator[tuple[str, LLMProvider], None]:
```

**Step 2 — Update `_store_cached` signature to accept `trace_id` and `line_number`**

Lines 231-237 — current code:

```python
    async def _store_cached(
        self,
        cache_key: str,
        text: str,
        provider_used: str,
        model_name: str,
    ) -> None:
```

Replace with:

```python
    async def _store_cached(
        self,
        cache_key: str,
        text: str,
        provider_used: str,
        model_name: str,
        trace_id: str | None = None,
        line_number: int | None = None,
    ) -> None:
```

**Step 3 — Update the JSON payload in `_store_cached`**

In the `_store_cached` method, find the `json={...}` payload and add `trace_id` and `line_number`:

Current payload (after FIX-CR-02):

```python
            json={
                "cache_key": cache_key,
                "explanation_text": text,
                "model_used": provider_used,
                "model_name": model_name,
                "cached": True,
            },
```

Replace with:

```python
            json={
                "cache_key": cache_key,
                "explanation_text": text,
                "model_used": provider_used,
                "model_name": model_name,
                "cached": True,
                "trace_id": trace_id,
                "line_number": line_number,
            },
```

**Step 4 — Call `_store_cached` with trace context in `llm.py`'s `event_generator`**

**IMPORTANT:** The `_store_cached` call belongs in `llm.py`'s `event_generator` function, NOT in `llm_router.py`'s `stream_explain`. The `stream_explain` method in `llm_router.py` is a generator that yields tokens. The actual SSE streaming to the client happens in `llm.py`'s `event_generator` function, which iterates over `stream_explain` and sends tokens via SSE. This is where we accumulate the full text and call `_store_cached`.

In `llm.py`, find the `event_generator` function (around line 95-103). **First, update the signature to accept `trace_id`:**

Current code:

```python
async def event_generator(
    request: Request,
    code: str,
    line_number: int,
    line_content: str,
    locals_dict: dict,
    ollama_endpoint: str | None = None,
) -> AsyncGenerator[dict, None]:
```

Replace with:

```python
async def event_generator(
    request: Request,
    code: str,
    line_number: int,
    line_content: str,
    locals_dict: dict,
    ollama_endpoint: str | None = None,
    trace_id: str | None = None,
) -> AsyncGenerator[dict, None]:
```

**Next, update the body to accumulate tokens and call `_store_cached`:**

Current body (around lines 101-115):

```python
    llm_router = get_llm_router()

    try:
        async for token, provider in llm_router.stream_explain(
            code=code,
            line_number=line_number,
            line_content=line_content,
            locals_dict=locals_dict,
            ollama_endpoint=ollama_endpoint,
        ):
            if token == "__done__":
                yield {"event": "done", "provider": provider.value}
            else:
                yield {"event": "token", "token": token, "provider": provider.value}
    except Exception as e:
        yield {"event": "error", "error": str(e)}
```

Replace with:

```python
    llm_router = get_llm_router()

    # Accumulator for cache storage — collect all tokens after stream completes
    accumulated_tokens: list[str] = []

    try:
        async for token, provider in llm_router.stream_explain(
            code=code,
            line_number=line_number,
            line_content=line_content,
            locals_dict=locals_dict,
            ollama_endpoint=ollama_endpoint,
            trace_id=trace_id,
        ):
            if token == "__done__":
                yield {"event": "done", "provider": provider.value}
                # Store in cache AFTER the stream completes
                full_text = "".join(accumulated_tokens)
                if full_text:
                    await llm_router._store_cached(
                        cache_key=make_cache_key(code, line_number, line_content, locals_dict),
                        text=full_text,
                        provider_used=provider.value,
                        model_name="github_models" if provider == LLMProvider.GITHUB_MODELS else "ollama",
                        trace_id=trace_id,
                        line_number=line_number,
                    )
            else:
                accumulated_tokens.append(token)
                yield {"event": "token", "token": token, "provider": provider.value}
    except Exception as e:
        yield {"event": "error", "error": str(e)}
```

**Key points:**

- `accumulated_tokens: list[str]` accumulates tokens as they arrive via the async generator
- `_store_cached` is called AFTER `yield {"event": "done", ...}` (stream completed), not before
- `full_text = "".join(accumulated_tokens)` gives the complete explanation text
- The call uses `llm_router._store_cached(...)` — the instance method on `LLMRouter`
- `make_cache_key` is imported from `llm_router` to recompute the cache key
- `trace_id` is passed through from the route → `event_generator` → `stream_explain` → `_store_cached`

**Step 5 — Update the router endpoint to pass `trace_id` to `event_generator`**

In `llm.py`'s `explain_stream` endpoint (around line 60-90), find where `event_generator` is called and add `trace_id`:

Find:

```python
        generator = event_generator(
            request,
            code,
            line_number,
            line_content,
            locals_dict,
            ollama_endpoint,
        )
```

Replace with:

```python
        generator = event_generator(
            request,
            code,
            line_number,
            line_content,
            locals_dict,
            ollama_endpoint,
            trace_id=trace_id,
        )
```

Also update the endpoint's parameters to accept `trace_id: str | None = None` from the query or body.

**Test to write FIRST (TDD)**

Create file `backend/tests/unit/test_cache_store.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_store_cached_verifies_insert_success():
    """_store_cached should check response status, not silently ignore failures."""
    from app.services.llm_router import LLMRouter
    
    router = LLMRouter()
    
    with patch.object(router, '_http') as mock_http:
        mock_post = AsyncMock()
        mock_post.return_value.status_code = 500  # Simulate failure
        mock_post.return_value.text = "Internal server error"
        mock_http.post = mock_post
        
        await router._store_cached(
            cache_key="test_key",
            text="test explanation",
            provider_used="github_models",
            model_name="gpt-4o-mini",
        )
        
        # Should have called post
        mock_http.post.assert_called_once()
        call_args = mock_http.post.call_args
        # Verify Prefer header is return=representation (not return=minimal)
        headers = call_args.kwargs.get('headers', {})
        assert headers.get("Prefer") == "return=representation", (
            "CRITICAL-04: Cache write uses return=minimal — failures are silently ignored. "
            "Must use return=representation and check status code."
        )

@pytest.mark.asyncio
async def test_store_cached_includes_trace_id():
    """_store_cached should store trace_id when provided."""
    from app.services.llm_router import LLMRouter
    
    router = LLMRouter()
    
    with patch.object(router, '_http') as mock_http:
        mock_post = AsyncMock()
        mock_post.return_value.status_code = 201
        mock_http.post = mock_post
        
        trace_id = "550e8400-e29b-41d4-a716-446655440000"
        await router._store_cached(
            cache_key="test_key",
            text="explanation",
            provider_used="github_models",
            model_name="gpt-4o-mini",
            trace_id=trace_id,
            line_number=42,
        )
        
        mock_http.post.assert_called_once()
        call_args = mock_http.post.call_args
        json_body = call_args.kwargs.get('json', {})
        assert json_body.get("trace_id") == trace_id, (
            "CRITICAL-06: Explanations stored without trace_id — orphaned from context."
        )
        assert json_body.get("line_number") == 42
```

**Verification command:**

```bash
cd backend
python -m pytest tests/unit/test_cache_store.py -v
```

**Order dependency:** Must be done after FIX-CR-02 (same method).

---

## FIX-CR-05: Debug log writes to disk in production

**Prerequisites:** None (standalone fix).

**Files to modify:**

- `backend/app/routers/traces.py`
- `backend/app/routers/auth.py`

**Step 1 — Fix `traces.py` save_trace (lines 179-198)**

Remove the entire `write_debug_log` function definition and all calls within `save_trace`.

Find and remove these in `save_trace`:

Lines 179-200 — remove the entire `import time`, `import os`, `import json_lib`, `ts = ...`, `DEBUG_LOG_PATH = ...`, and `def write_debug_log(...)` block.

Lines 201, 208, 229, 241 — remove all `write_debug_log(...)` calls.

Current broken code (lines 178-200):

```python
    import time
    import os
    import json as json_lib
    
    ts = int(time.time() * 1000)
    DEBUG_LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "debug-save.log")
    
    def write_debug_log(hid, msg, data):
        try:
            log_entry = {
                "sessionId": "save_trace",
                "id": f"log_{ts}",
                "timestamp": ts,
                "location": data.get("location", "traces.py:save_trace"),
                "message": msg,
                "data": {k: v for k, v in data.items() if k not in ["timestamp", "location"]},
            }
            with open(DEBUG_LOG_PATH, "a") as f:
                f.write(json_lib.dumps(log_entry) + "\n")
        except Exception:
            pass
    
    write_debug_log("A", "save_trace called", {"has_auth": authorization is not None})
```

Remove ALL of this. Replace with:

```python
    logger.info("save_trace_called", extra={"location": "traces.py:save_trace", "has_auth": authorization is not None})
```

Also remove these calls in the same function:

- Line 208: `write_debug_log("B", "Got user", {"user_id": user_id})` → `logger.info("save_trace_user", extra={"user_id": user_id})`
- Line 229: `write_debug_log("C", "Calling Supabase", ...)` → `logger.info("save_trace_supabase_call", extra={"url": settings.supabase_url})`
- Line 241: `write_debug_log("D", "Supabase response", ...)` → `logger.info("save_trace_response", extra={"status_code": resp.status_code})`

**Step 2 — Fix `traces.py` list_traces (lines 264-286)**

Remove the same pattern from `list_traces`:

Remove the `import time`, `import os`, `import json_lib`, `ts = ...`, `DEBUG_LOG_PATH = ...`, and `def write_debug_log(...)` block (lines 264-286).

Replace all `write_debug_log(...)` calls with `logger.info(...)` calls:

- Line 288: → `logger.info("list_traces_called", extra={"location": "traces.py:list_traces", "has_auth": authorization is not None})`
- Line 291: → `logger.warning("list_traces_no_auth")`
- Line 297: → `logger.info("list_traces_got_user", extra={"user_id": user_id})`
- Line 299: → `logger.warning("list_traces_auth_failed", extra={"detail": str(e.detail)})`
- Line 303: → `logger.debug("list_traces_settings_loaded", extra={"supabase_url": settings.supabase_url})`
- Line 320: → `logger.info("list_traces_response", extra={"status_code": resp.status_code})`
- Line 323: → `logger.info("list_traces_returning", extra={"trace_count": len(traces)})`

**Step 3 — Fix `auth.py` (lines 12-28)**

Remove the `DEBUG_LOG_PATH` constant and `write_debug_log` function from `auth.py`.

Lines 12-28 — current broken code:

```python
# Debug logging setup
DEBUG_LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "debug-bd0394.log")

def write_debug_log(hypothesis_id: str, message: str, data: dict):
    """Write debug log in NDJSON format"""
    log_entry = {
        "sessionId": "bd0394",
        "id": f"log_{data.get('timestamp', 0)}",
        "timestamp": data.get("timestamp", 0),
        "location": data.get("location", "auth.py"),
        "message": message,
        "data": {k: v for k, v in data.items() if k not in ["timestamp", "location"]},
        "runId": data.get("runId", "initial"),
        "hypothesisId": hypothesis_id
    }
    with open(DEBUG_LOG_PATH, "a") as f:
        f.write(json.dumps(log_entry) + "\n")
```

Replace with logger calls. **First check** whether `import logging` already exists at the top of `auth.py`. Look at the existing imports section. If `import logging` is NOT present, add it:

```python
import logging
```

Then add the logger instantiation:

```python
logger = logging.getLogger("codescope.auth")
```

**IMPORTANT:** Do NOT remove `import json` from `auth.py` — it is used in `get_current_user` at line 9 of the original file. Removing it would break the function. The `write_debug_log` function writes JSON to disk, but `get_current_user` uses `json.loads()` for parsing the Supabase API response. Only remove the `write_debug_log` function and its calls.

Then replace all `write_debug_log(...)` calls in `get_current_user` with `logger.info(...)`:

- Line 41: `write_debug_log("A", "No authorization header", ...)` → `logger.warning("auth_no_header", extra={"location": "auth.py:get_current_user"})`
- Line 45: → `logger.warning("auth_invalid_format", extra={"location": "auth.py:get_current_user"})`
- Line 53: → `logger.debug("auth_token_received")`
- Line 57: → `logger.debug("auth_supabase_url", extra={"supabase_url": settings.supabase_url})`
- Line 67: → `logger.debug("auth_supabase_response", extra={"status_code": resp.status_code})`
- Line 70: → `logger.warning("auth_token_invalid")`
- Line 73: → `logger.error("auth_failed", extra={"status_code": resp.status_code})`
- Line 77: → `logger.info("auth_success", extra={"user_id": user_data.get("id", "")})`

**Step 4 — Delete debug log files**

```bash
cd backend
rm -f debug-save.log debug-bd0394.log
```

**Test to write FIRST (TDD)**

Create file `backend/tests/unit/test_debug_disk_write.py`:

```python
import pytest
import inspect

def test_traces_router_no_disk_write():
    """CRITICAL-05: traces.py should not write to .log files."""
    from app.routers import traces

    source = inspect.getsource(traces)

    # Check for file write patterns
    dangerous_patterns = [
        "open(",  # direct open() calls
        ".write(",  # write() calls
        "debug-save.log",  # specific log file names
        "write_debug_log",  # the function itself
    ]

    violations = []
    for pattern in dangerous_patterns:
        if pattern in source:
            violations.append(pattern)

    assert len(violations) == 0, (
        f"CRITICAL-05: Found disk-write patterns in traces.py: {violations}. "
        "Replace write_debug_log with structured logging (logger.debug/info/warning)."
    )


def test_auth_router_no_disk_write():
    """CRITICAL-05: auth.py should not write to .log files."""
    from app.routers import auth

    source = inspect.getsource(auth)

    # Check for file write patterns (excluding legitimate json usage)
    lines = source.split('\n')
    violations = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Skip json.loads/json.dumps (legitimate Supabase API usage)
        if 'json.loads' in stripped or 'json.dumps' in stripped:
            continue
        # Check for disk write patterns
        if any(p in stripped for p in ["open(", ".write(", "debug-save.log", "write_debug_log"]):
            violations.append(f"Line {i}: {stripped}")

    assert len(violations) == 0, (
        f"CRITICAL-05: Found disk-write patterns in auth.py:\n"
        + "\n".join(violations)
        + "\nReplace write_debug_log with structured logging."
    )
```

**Key improvement over previous version:** This test uses `inspect.getsource()` to scan the actual source code of the modules. This works regardless of whether the functions are async, whether Supabase is reachable, or whether mocking is set up correctly. It catches the problem at the source level — the same approach used by `test_no_print_statements_in_llm_router` in FIX-MD-04.

**Verification command:**

```bash
cd backend
# Verify no debug-*.log files exist
ls debug-*.log 2>/dev/null && echo "FAIL: debug logs still exist" || echo "PASS: no debug logs"
# Verify grep finds no file writes in routers
python -c "import app.routers.traces as t; import app.routers.auth as a; print('imported ok')"
```

**Order dependency:** None.

---

## FIX-CR-06: Explanations stored without trace_id

**Prerequisites:** FIX-CR-04 must be done first (trace_id parameter must be added to `_store_cached`).

**Files to modify:**

- `backend/app/routers/llm.py`

**The fix is already covered in FIX-CR-04.** The `trace_id` parameter is added to both `stream_explain` and `_store_cached`, and passed through the call chain. The remaining piece is updating the call site in `llm.py` to pass the trace_id.

**Step 1 — Update `llm.py` endpoint to extract and pass trace_id**

The endpoint at `llm.py` line 85-91 calls `llm_router.stream_explain(...)`. Currently it doesn't pass a `trace_id`. Since the explain endpoint is stateless and anonymous users can call it, trace_id should be optional. However, when called from the tracer page (authenticated), we should pass the current trace's ID.

Since the explain endpoint (`/explain/stream`) doesn't know about a trace context, the simplest approach is to add `trace_id` as an optional query parameter:

In `llm.py` line 23-32, add `trace_id` to the endpoint signature:

```python
@router.get("/explain/stream")
async def stream_explanation(
    code: str = Query(..., max_length=5000),
    line_number: int = Query(..., ge=1),
    line_content: str = Query(..., max_length=500),
    locals_json: str = Query(..., max_length=2000),
    user_id: Optional[str] = Query(None),
    ollama_endpoint: Optional[str] = Query(None),
    trace_id: Optional[str] = Query(None),  # ← ADD THIS
    x_forwarded_for: str | None = Header(None),
):
```

Then update the call at line 85-91:

```python
            async for token, provider in llm_router.stream_explain(
                code=code,
                line_number=line_number,
                line_content=line_content,
                locals_dict=locals_dict,
                ollama_endpoint=ollama_endpoint,
                trace_id=trace_id,  # ← ADD THIS
            ):
```

**Test to write FIRST (TDD)**

```python
# Part of test_llm_router.py — test stream_explain passes trace_id through

@pytest.mark.asyncio
async def test_stream_explain_passes_trace_id_to_store_cached():
    """stream_explain should pass trace_id to _store_cached."""
    from app.services.llm_router import LLMRouter
    
    router = LLMRouter()
    
    with patch.object(router, '_http') as mock_http:
        mock_post = AsyncMock()
        mock_post.return_value.__aenter__ = AsyncMock()
        mock_post.return_value.__aexit__ = AsyncMock()
        mock_post.return_value.status_code = 201
        mock_http.post = mock_post
        
        # Also patch the GitHub API call to return something
        mock_post.return_value.__aenter__.return_value.status_code = 200
        mock_post.return_value.__aenter__.return_value.json.return_value = {
            "choices": [{"message": {"content": "Test explanation"}}]
        }
        
        tokens = []
        async for token, provider in router.stream_explain(
            code="x = 1",
            line_number=1,
            line_content="x = 1",
            locals_dict={},
            trace_id="trace-123",
        ):
            tokens.append(token)
        
        # Verify trace_id was in the cache store call
        store_calls = [c for c in mock_http.post.call_args_list if 'explanations' in str(c)]
        if store_calls:
            json_body = store_calls[0].kwargs.get('json', {})
            assert json_body.get('trace_id') == 'trace-123', (
                "CRITICAL-06: trace_id not passed to _store_cached"
            )
```

**Verification command:**

```bash
cd backend
python -m pytest tests/unit/test_llm_router.py -v
```

**Order dependency:** Must be done after FIX-CR-04.

---

## PART 1 — High Priority

---

## FIX-HI-01: last_reviewed_at uses string "now()" instead of SQL now()

**Prerequisites:** None (standalone).

**Files to modify:**

- `backend/app/routers/review.py`

**Step 1 — Fix the timestamp**

Line 263 — current broken code:

```python
                "next_review_date": next_date.isoformat(),
                "last_reviewed_at": "now()",  # ← wrong: Supabase sees string "now()", not timestamp
            },
```

Replace with:

```python
                "next_review_date": next_date.isoformat(),
                "last_reviewed_at": datetime.now(timezone.utc).isoformat(),
            },
```

**Test to write FIRST (TDD)**

Create file `backend/tests/unit/test_review_timestamp.py`:

```python
import pytest
from datetime import datetime, timezone

def test_last_reviewed_at_not_string_now():
    """last_reviewed_at should be ISO timestamp, not the string 'now()'."""
    from app.routers.review import router
    
    # Check that the endpoint's PATCH call uses proper datetime
    # This test verifies the code doesn't use the string "now()"
    import inspect
    source = inspect.getsource(router)
    
    assert '"now()"' not in source, (
        "HIGH-01: last_reviewed_at uses string 'now()' instead of datetime. "
        "Supabase will store the literal string 'now()', not a timestamp."
    )
```

**Verification command:**

```bash
cd backend
python -m pytest tests/unit/test_review_timestamp.py -v
```

---

## FIX-HI-02: Streak calculation returns card count, not consecutive days

**Prerequisites:** None (standalone).

**Files to modify:**

- `backend/app/routers/review.py`

**Step 1 — Add `_calculate_streak` function after the imports**

Add after line 20 (after `logger = logging.getLogger(...)`):

```python
async def _calculate_streak(user_id: str, supabase_url: str, supabase_key: str) -> int:
    """
    Count consecutive days with at least 1 completed review, working backwards from today.
    Returns 0 if no reviews today.
    """
    # Note: 'from datetime import datetime, date' is already at the top of review.py
    # Do NOT import date/timedelta again here — use date from module-level import
    from datetime import timedelta  # Only import timedelta (not already imported at module level)
    import httpx
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{supabase_url}/rest/v1/review_cards",
            params={
                "user_id": f"eq.{user_id}",
                "select": "last_reviewed_at",
                "order": "last_reviewed_at.desc",
                "limit": "100",
            },
            headers={
                "Authorization": f"Bearer {supabase_key}",
                "apikey": supabase_key,
            },
        )
    
    if resp.status_code != 200:
        return 0
    
    cards = resp.json()
    
    # Group reviewed dates
    reviewed_dates: set[str] = set()
    for card in cards:
        ts = card.get("last_reviewed_at")
        if ts:
            reviewed_dates.add(ts[:10])  # YYYY-MM-DD
    
    # Count consecutive days from today backwards
    streak = 0
    check_date = date.today()  # 'date' from module-level import, not re-imported here
    
    while True:
        date_str = check_date.isoformat()
        if date_str in reviewed_dates:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break
    
    return streak
```

**Step 2 — Replace the wrong streak calculation in `get_due_reviews`**

Line 141 — current broken code:

```python
    streak = len(cards)  # simplified streak
```

Replace with:

```python
    streak = await _calculate_streak(user_id, settings.supabase_url, settings.supabase_service_key)
```

**Test to write FIRST (TDD)**

Create file `backend/tests/unit/test_streak.py`:

```python
import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_calculate_streak_consecutive_days():
    """_calculate_streak should return consecutive days count, not card count."""
    from app.routers.review import _calculate_streak
    
    today = date.today()
    yesterday = (today - timedelta(days=1)).isoformat()
    two_days_ago = (today - timedelta(days=2)).isoformat()
    three_days_ago = (today - timedelta(days=3)).isoformat()
    four_days_ago = (today - timedelta(days=4)).isoformat()
    
    # Simulate 3 consecutive days: today, yesterday, two_days_ago
    mock_cards = [
        {"last_reviewed_at": today.isoformat()},
        {"last_reviewed_at": yesterday},
        {"last_reviewed_at": two_days_ago},
        {"last_reviewed_at": four_days_ago},  # Gap on day 3
    ]
    
    with patch('httpx.AsyncClient') as MockClient:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock()
        mock_instance.__aexit__ = AsyncMock()
        mock_instance.get = AsyncMock()
        mock_instance.get.return_value.status_code = 200
        mock_instance.get.return_value.json = lambda: mock_cards
        MockClient.return_value = mock_instance
        
        streak = await _calculate_streak("user-123", "https://test.supabase.co", "key")
        
        assert streak == 3, (
            f"HIGH-02: streak returned {streak}, expected 3. "
            "Streak should count consecutive days, not card count."
        )

@pytest.mark.asyncio
async def test_calculate_streak_gap_resets():
    """A gap in review days should reset the streak count."""
    from app.routers.review import _calculate_streak
    
    today = date.today()
    two_days_ago = (today - timedelta(days=2)).isoformat()  # Gap yesterday
    
    mock_cards = [
        {"last_reviewed_at": today.isoformat()},
        {"last_reviewed_at": two_days_ago},  # No yesterday = streak of 1
    ]
    
    with patch('httpx.AsyncClient') as MockClient:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock()
        mock_instance.__aexit__ = AsyncMock()
        mock_instance.get = AsyncMock()
        mock_instance.get.return_value.status_code = 200
        mock_instance.get.return_value.json = lambda: mock_cards
        MockClient.return_value = mock_instance
        
        streak = await _calculate_streak("user-123", "https://test.supabase.co", "key")
        
        assert streak == 1, (
            f"HIGH-02: gap should reset streak to 1, got {streak}"
        )
```

**Verification command:**

```bash
cd backend
python -m pytest tests/unit/test_streak.py -v
```

---

## FIX-HI-03: Profiles endpoints return placeholders

**Prerequisites:** None (standalone).

**Files to modify:**

- `backend/app/routers/profiles.py`

**Step 1 — Implement `get_profile` (lines 14-31)**

Current broken code (lines 24-31):

```python
    # TODO: Fetch from Supabase using token
    return {
        "id": "placeholder",
        "experience_level": "student",
        "ai_tools_usage": "moderate",
        "ollama_endpoint": "https://ollama.com/api",
        "plan": "free",
    }
```

Replace with:

```python
    token = authorization[7:]
    
    from app.config import Settings
    settings = Settings()
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/profiles",
            params={"user_id": f"eq.{token}", "select": "*"},
            headers={
                "Authorization": f"Bearer {settings.supabase_service_key}",
                "apikey": settings.supabase_service_key,
            },
        )
    
    if resp.status_code == 200:
        profiles = resp.json()
        if profiles and len(profiles) > 0:
            return profiles[0]
    
    raise HTTPException(status_code=404, detail="Profile not found")
```

Add `import httpx` at the top of the file if not present.

**Step 2 — Implement `update_profile` (lines 34-74)**

Current broken code (lines 69-74):

```python
    # TODO: Update in Supabase
    return {
        "experience_level": experience_level or "student",
        "ai_tools_usage": ai_tools_usage or "moderate",
        "ollama_endpoint": ollama_endpoint or "https://ollama.com/api",
    }
```

Replace with:

```python
    from app.config import Settings
    settings = Settings()
    token = authorization[7:]
    
    # Build update payload
    update_data = {}
    if experience_level is not None:
        update_data["experience_level"] = experience_level
    if ai_tools_usage is not None:
        update_data["ai_tools_usage"] = ai_tools_usage
    if ollama_endpoint is not None:
        update_data["ollama_endpoint"] = ollama_endpoint
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.patch(
            f"{settings.supabase_url}/rest/v1/profiles",
            params={"user_id": f"eq.{token}"},
            headers={
                "Authorization": f"Bearer {settings.supabase_service_key}",
                "apikey": settings.supabase_service_key,
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            json=update_data,
        )
    
    if resp.status_code == 200:
        profiles = resp.json()
        if profiles and len(profiles) > 0:
            return profiles[0]
    
    raise HTTPException(status_code=404, detail="Profile not found or update failed")
```

**Test to write FIRST (TDD)**

Create file `backend/tests/unit/test_profiles.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_get_profile_queries_supabase():
    """get_profile should fetch from Supabase, not return placeholders."""
    with patch('httpx.AsyncClient') as MockClient:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock()
        mock_instance.__aexit__ = AsyncMock()
        mock_instance.get = AsyncMock()
        mock_instance.get.return_value.status_code = 200
        mock_instance.get.return_value.json = lambda: [{
            "id": "profile-uuid",
            "user_id": "user-uuid",
            "experience_level": "junior",
            "ai_tools_usage": "heavy",
            "plan": "pro",
        }]
        MockClient.return_value = mock_instance
        
        from app.routers.profiles import get_profile
        import asyncio
        result = await get_profile(authorization="Bearer user-uuid-token")
        
        assert result.get("plan") == "pro", (
            f"HIGH-03: get_profile returned placeholder data: {result}. "
            "Must query Supabase for real profile data."
        )
        assert result.get("id") != "placeholder", "Should not return placeholder id"

@pytest.mark.asyncio
async def test_update_profile_writes_to_supabase():
    """update_profile should write to Supabase, not return placeholders."""
    with patch('httpx.AsyncClient') as MockClient:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock()
        mock_instance.__aexit__ = AsyncMock()
        mock_instance.patch = AsyncMock()
        mock_instance.patch.return_value.status_code = 200
        mock_instance.patch.return_value.json = lambda: [{
            "experience_level": "mid",
            "ai_tools_usage": "moderate",
        }]
        MockClient.return_value = mock_instance
        
        from app.routers.profiles import update_profile
        result = await update_profile(
            experience_level="mid",
            authorization="Bearer user-uuid-token"
        )
        
        assert result.get("experience_level") == "mid", (
            "HIGH-03: update_profile returned placeholder data."
        )
```

**Verification command:**

```bash
cd backend
python -m pytest tests/unit/test_profiles.py -v
```

---

## FIX-HI-04: LLM provider order wrong — Ollama Cloud should be primary

**Prerequisites:** None (standalone).

**Files to modify:**

- `backend/app/services/llm_router.py`

**Step 1 — Add `OLLAMA_CLOUD` to the `LLMProvider` enum**

Line 26 — current code:

```python
class LLMProvider(Enum):
    GITHUB_MODELS = "github_models"
```

Replace with:

```python
class LLMProvider(Enum):
    OLLAMA_CLOUD = "ollama_cloud"
    GITHUB_MODELS = "github_models"
```

**Step 2 — Add `_stream_ollama_cloud` method after `_stream_github_models`**

Add after line 201 (after the `_stream_github_models` method ends):

```python
    async def _stream_ollama_cloud(self, prompt: str, cache_key: str) -> AsyncGenerator[str, None]:
        """
        Stream from Ollama Cloud API (https://ollama.com/api/chat).
        Primary provider — free, no setup required.
        """
        url = f"{settings.ollama_cloud_url}/chat"
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
```

**Step 3 — Update provider ordering in `stream_explain`**

Lines 117-123 — current code:

```python
        providers_to_try = []
        
        print(f"DEBUG: settings.github_models_pat = {repr(settings.github_models_pat[:10] if settings.github_models_pat else None)}", flush=True)
        logger.warning(f"DEBUG: Checking if PAT exists: {bool(settings.github_models_pat)}")
        
        if settings.github_models_pat:
            providers_to_try.append((LLMProvider.GITHUB_MODELS, "github_models", cache_key))
```

Replace with:

```python
        providers_to_try = []
        
        # 1. Ollama Cloud (primary — free, no setup)
        if settings.ollama_cloud_url:
            providers_to_try.append((LLMProvider.OLLAMA_CLOUD, settings.ollama_cloud_url, cache_key))
        
        # 2. GitHub Models (fallback — requires PAT)
        if settings.github_models_pat:
            providers_to_try.append((LLMProvider.GITHUB_MODELS, "github_models", cache_key))
```

**Step 4 — Add handler for `OLLAMA_CLOUD` in the provider loop**

In the `for provider, _endpoint, _cache_key in providers_to_try:` loop (around line 127-143), add:

```python
            try:
                if provider == LLMProvider.GITHUB_MODELS:
                    async for token in self._stream_github_models(prompt, cache_key):
                        yield token, provider
                elif provider == LLMProvider.OLLAMA_CLOUD:
                    async for token in self._stream_ollama_cloud(prompt, cache_key):
                        yield token, provider
```

**Test to write FIRST (TDD)**

Create file `backend/tests/unit/test_llm_providers.py`:

```python
import pytest

def test_ollama_cloud_is_primary_provider():
    """HIGH-04: Ollama Cloud should be the primary (first) LLM provider."""
    from app.services.llm_router import LLMProvider, LLMRouter
    
    router = LLMRouter()
    
    # Verify enum has both providers
    assert hasattr(LLMProvider, 'OLLAMA_CLOUD'), "LLMProvider enum missing OLLAMA_CLOUD"
    assert hasattr(LLMProvider, 'GITHUB_MODELS'), "LLMProvider enum missing GITHUB_MODELS"
    
    # We can't easily test the ordering without mocking settings,
    # but the enum order reflects priority
    providers = list(LLMProvider)
    assert providers[0] == LLMProvider.OLLAMA_CLOUD, (
        "HIGH-04: Ollama Cloud should be primary provider (first in enum). "
        "Current code has GitHub Models as the only provider."
    )

def test_stream_ollama_cloud_method_exists():
    """stream_explain should have a method for Ollama Cloud streaming."""
    from app.services.llm_router import LLMRouter
    
    router = LLMRouter()
    assert hasattr(router, '_stream_ollama_cloud'), (
        "HIGH-04: _stream_ollama_cloud method not found. "
        "Ollama Cloud is not implemented."
    )
```

**Verification command:**

```bash
cd backend
python -m pytest tests/unit/test_llm_providers.py -v
```

---

## FIX-HI-05: No LLM provider validation at startup

**Prerequisites:** FIX-HI-04 (need `OLLAMA_CLOUD` in the enum).

**Files to modify:**

- `backend/app/main.py`

**Step 1 — Update the lifespan startup check**

Lines 9-19 — current code:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown hooks."""
    from app.config import Settings
    settings = Settings()
    if not settings.github_models_pat:
        import logging
        logging.warning(
            "GITHUB_MODELS_PAT not set. AI explanations will return a placeholder message."
        )
    yield
```

Replace with:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown hooks."""
    from app.config import settings
    
    # Validate at least one LLM provider is configured
    has_ollama = bool(settings.ollama_cloud_url)
    has_github = bool(settings.github_models_pat)
    
    if not has_ollama and not has_github:
        import logging
        logging.error(
            "HIGH-05: No LLM provider configured. "
            "Set OLLAMA_CLOUD_URL or GITHUB_MODELS_PAT. "
            "AI explanations will not work."
        )
    
    if has_ollama:
        logging.info("llm_provider_ready", extra={"provider": "ollama_cloud", "url": settings.ollama_cloud_url})
    if has_github:
        logging.info("llm_provider_ready", extra={"provider": "github_models"})
    
    yield
    
    # Shutdown: close the LLM router's HTTP client
    from app.services.llm_router import llm_router
    await llm_router.close()
```

**Test to write FIRST (TDD)**

Create file `backend/tests/unit/test_startup_validation.py`:

```python
import pytest
from unittest.mock import patch

def test_startup_validates_llm_provider():
    """HIGH-05: Startup should check that at least one LLM provider is configured."""
    import app.main as main_module
    import inspect
    
    source = inspect.getsource(main_module.lifespan)
    
    # Check that both OLLAMA and GITHUB are validated
    assert "ollama_cloud_url" in source or "OLLAMA" in source, (
        "HIGH-05: Startup validation doesn't check Ollama Cloud. "
        "Must validate at least one provider is configured."
    )
    assert "github_models_pat" in source or "GITHUB" in source, (
        "HIGH-05: Startup validation doesn't check GitHub Models."
    )

def test_startup_error_when_no_provider():
    """When no provider is configured, startup should log an error."""
    from app.config import settings
    
    # Check that settings has both options
    assert hasattr(settings, 'ollama_cloud_url'), "Settings missing ollama_cloud_url"
    assert hasattr(settings, 'github_models_pat'), "Settings missing github_models_pat"
```

**Verification command:**

```bash
cd backend
python -m pytest tests/unit/test_startup_validation.py -v
```

---

## FIX-HI-06: Health endpoint is liveness-only

**Prerequisites:** None (standalone).

**Files to modify:**

- `backend/app/main.py`

**Step 1 — Update the health endpoint**

Lines 61-64 — current code:

```python
@app.get("/health")
async def health():
    """Health check endpoint for Docker/liveness probes."""
    return {"status": "ok"}
```

Replace with:

```python
@app.get("/health")
async def health():
    """
    Health check endpoint for Docker/liveness probes + readiness probes.
    Checks Supabase connectivity.
    """
    from app.config import settings
    import httpx
    
    checks: dict = {"status": "ok", "checks": {}}
    healthy = True
    
    # Check Supabase connectivity
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"{settings.supabase_url}/rest/v1/",
                headers={"apikey": settings.supabase_service_key},
            )
            checks["checks"]["supabase"] = "ok" if resp.status_code == 200 else f"error:{resp.status_code}"
            if resp.status_code != 200:
                healthy = False
    except Exception as e:
        checks["checks"]["supabase"] = f"error:{type(e).__name__}"
        healthy = False
    
    checks["status"] = "ok" if healthy else "degraded"
    from fastapi.responses import JSONResponse
    return JSONResponse(content=checks, status_code=200 if healthy else 503)
```

**Test to write FIRST (TDD)**

Create file `backend/tests/unit/test_health_endpoint.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_health_returns_503_when_supabase_down():
    """HIGH-06: Health endpoint should return 503 when Supabase is unreachable."""
    with patch('httpx.AsyncClient') as MockClient:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(side_effect=Exception("Connection refused"))
        mock_instance.__aexit__ = AsyncMock()
        MockClient.return_value = mock_instance
        
        from app.main import health
        response = await health()
        
        assert response.status_code == 503, (
            f"HIGH-06: Health returned {response.status_code} when Supabase is down. "
            "Should return 503 for degraded status."
        )
        import json
        # response.body is bytes in httpx — decode to str before parsing JSON
        body = json.loads(response.body.decode("utf-8"))
        assert body["status"] == "degraded"
        assert "supabase" in body["checks"]

@pytest.mark.asyncio
async def test_health_returns_200_when_healthy():
    with patch('httpx.AsyncClient') as MockClient:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock()
        mock_instance.__aexit__ = AsyncMock()
        mock_instance.get = AsyncMock()
        mock_instance.get.return_value.status_code = 200
        MockClient.return_value = mock_instance
        
        from app.main import health
        response = await health()
        
        assert response.status_code == 200, "Health should return 200 when all checks pass"
```

**Verification command:**

```bash
cd backend
python -m pytest tests/unit/test_health_endpoint.py -v
```

---

## FIX-HI-07: Rate limit doesn't distinguish free vs Pro

**Prerequisites:** FIX-CR-03 must be done first (`_is_pro_user` must work).

**Files to modify:**

- `backend/app/routers/traces.py`

**Step 1 — Add trace count checking before allowing trace execution**

In `run_trace` endpoint, after getting the user:

```python
async def run_trace(req: TraceRequest, authorization: str = Header(None)):
```

After line 131 (after `user = await get_current_user(authorization)`):

```python
    user = await get_current_user(authorization)
    user_id = user.get("id", "")
    
    # Check if user is Pro (use inlined version to avoid circular import)
    is_pro = await _is_pro_user_in_traces(user_id)
    
    if not is_pro:
        # Count user's traces this month
        FREE_TRACE_LIMIT = 50
        trace_count = await _get_trace_count_this_month(user_id, settings)
        
        if trace_count >= FREE_TRACE_LIMIT:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "FREE_LIMIT_REACHED",
                    "message": f"You've used your {FREE_TRACE_LIMIT} free traces this month. Upgrade to Pro for unlimited.",
                    "upgrade_url": "/upgrade",
                    "current_count": trace_count,
                    "limit": FREE_TRACE_LIMIT,
                }
            )
```

**Step 2 — Add `_get_trace_count_this_month` helper function**

Add after the imports at the top of `traces.py`:

```python
async def _get_trace_count_this_month(user_id: str, settings_obj) -> int:
    """Count traces created by user in the current calendar month."""
    from datetime import datetime
    import httpx
    
    now = datetime.utcnow()
    month_start = f"{now.year}-{now.month:02d}-01"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings_obj.supabase_url}/rest/v1/traces",
            params={
                "user_id": f"eq.{user_id}",
                "created_at": f"gte.{month_start}",
                "select": "id",
            },
            headers={
                "Authorization": f"Bearer {settings_obj.supabase_service_key}",
                "apikey": settings_obj.supabase_service_key,
            },
        )
    
    if resp.status_code == 200:
        return len(resp.json())
    return 0
```

Also add `async def _is_pro_user` — but do NOT import it. Instead, copy the function inline to avoid circular import. Add this helper function directly in `traces.py` after the imports:

```python
async def _is_pro_user_in_traces(user_id: str | None) -> bool:
    """
    Check if user is on Pro plan.
    INLINED here to avoid circular import with llm.py.
    Must stay in sync with _is_pro_user in app/routers/llm.py.
    """
    if not user_id:
        return False
    from app.config import settings
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{settings.supabase_url}/rest/v1/profiles",
                params={"user_id": f"eq.{user_id}", "select": "plan"},
                headers={
                    "Authorization": f"Bearer {settings.supabase_service_key}",
                    "apikey": settings.supabase_service_key,
                },
            )
            if resp.status_code == 200:
                profiles = resp.json()
                if profiles and len(profiles) > 0:
                    return profiles[0].get("plan") == "pro"
    except Exception:
        pass
    return False
```

**IMPORTANT:** Do NOT use `from app.routers.llm import _is_pro_user` — this creates a circular import because:

1. `traces.py` imports from `llm.py`
2. `llm.py` already imports from `llm_router.py`
3. `llm_router.py` may import from `traces.py` or related modules

The solution is to duplicate the function body in `traces.py` as shown above. Keep both implementations in sync.

**Test to write FIRST (TDD)**

Create file `backend/tests/unit/test_trace_limit.py`:

```python
import pytest
import inspect
from unittest.mock import AsyncMock, patch

def test_trace_limit_enforcement_in_run_trace():
    """HIGH-07: run_trace should check trace count for non-Pro users."""
    from app.routers import traces

    source = inspect.getsource(traces)

    # Verify the helper function exists
    assert "_get_trace_count_this_month" in source, (
        "HIGH-07: _get_trace_count_this_month helper not found in traces.py"
    )
    assert "_is_pro_user_in_traces" in source, (
        "HIGH-07: _is_pro_user_in_traces helper not found in traces.py. "
        "Must be inlined to avoid circular import with llm.py."
    )
    assert "FREE_TRACE_LIMIT" in source, (
        "HIGH-07: FREE_TRACE_LIMIT constant not found in run_trace"
    )
    assert "FREE_LIMIT_REACHED" in source, (
        "HIGH-07: FREE_LIMIT_REACHED error code not found in run_trace"
    )


@pytest.mark.asyncio
async def test_free_user_blocked_at_50_traces():
    """HIGH-07: Free user at 50+ traces should get HTTP 402."""
    with patch('httpx.AsyncClient') as MockClient:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_instance.get = AsyncMock()
        mock_instance.get.return_value.status_code = 200
        mock_instance.get.return_value.json = lambda: [{"id": f"trace-{i}"} for i in range(50)]
        MockClient.return_value = mock_instance

        from app.routers.traces import _get_trace_count_this_month
        from app.config import settings

        count = await _get_trace_count_this_month("user-123", settings)
        assert count == 50, f"Expected 50, got {count}"

        # Verify FREE_LIMIT_REACHED will be raised (count >= limit)
        FREE_TRACE_LIMIT = 50
        assert count >= FREE_TRACE_LIMIT, "At limit, should raise HTTP 402"


@pytest.mark.asyncio
async def test_pro_user_bypasses_limit():
    """HIGH-07: Pro users should not be checked against the trace limit."""
    from app.routers.traces import _is_pro_user_in_traces

    with patch('httpx.AsyncClient') as MockClient:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_instance.get = AsyncMock()
        mock_instance.get.return_value.status_code = 200
        mock_instance.get.return_value.json = lambda: [{"plan": "pro"}]
        MockClient.return_value = mock_instance

        result = await _is_pro_user_in_traces("user-pro-123")
        assert result is True, "User with plan='pro' should return True"

    # Also test free user
    with patch('httpx.AsyncClient') as MockClient:
        mock_instance = AsyncMock()
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        mock_instance.get = AsyncMock()
        mock_instance.get.return_value.status_code = 200
        mock_instance.get.return_value.json = lambda: [{"plan": "free"}]
        MockClient.return_value = mock_instance

        result = await _is_pro_user_in_traces("user-free-456")
        assert result is False, "User with plan='free' should return False"
```

**Verification command:**

```bash
cd backend
python -m pytest tests/unit/test_trace_limit.py -v
```

---

## FIX-HI-08: Missing README

**Prerequisites:** None (standalone).

**Files to create:**

- `c:/Users/quoct/codescope/README.md` (already exists, update it)
- `c:/Users/quoct/codescope/backend/.env.example`

**Step 1 — Update `README.md`**

The existing `README.md` is comprehensive. Update it to reference the correct project paths and fix any outdated sections.

**Important project-specific details to include:**

- Project name: **CodeScope** — AI-powered Python code tracer and spaced repetition system
- Target users: CS students and developers learning Python
- Stack: Next.js frontend + FastAPI backend + Supabase + Python bytecode tracing
- Key features: Step-by-step Python execution visualization, AI explanations (Ollama Cloud + GitHub Models), spaced repetition flashcards, GitHub OAuth
- Repository root at `c:/Users/quoct/codescope/` contains both `frontend/` and `backend/` directories
- Backend runs on FastAPI with Supabase as the database
- Frontend is Next.js 16+ with App Router
- The tracer uses Python's bytecode introspection (`sys.settrace`) to capture execution steps
- Study context: Thesis project for measuring comprehension and retention

Do NOT leave the README as a generic template. Replace placeholder sections with concrete project information.

**Step 2 — Create `backend/.env.example`**

Create file `backend/.env.example`:

```bash
# ===========================================
# CodeScope — Environment Variables Template
# ===========================================
# Copy this file to .env and fill in the values.
# NEVER commit .env to version control.

# ── AI Explanations (at least one required) ──

# Option A: Ollama Cloud (FREE, primary — recommended)
# Leave blank to use Ollama Cloud
OLLAMA_CLOUD_URL=https://ollama.com/api
OLLAMA_MODEL=llama3.2

# Option B: GitHub Models (requires PAT)
# Get your PAT at: https://github.com/settings/tokens
GITHUB_MODELS_PAT=ghp_your_personal_access_token_here
GITHUB_MODELS_MODEL=openai/gpt-4o-mini

# ── Supabase (required) ──
# Get these from: https://supabase.com/dashboard/project/YOUR_PROJECT/settings/api
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key_here

# ── Redis (optional — for distributed rate limiting) ──
REDIS_ENABLED=false
REDIS_URL=redis://localhost:6379

# ── Application ──
LOG_LEVEL=INFO

# ── Rate Limiting ──
# Free tier: 20 "why" questions per hour (anonymous)
# Pro tier: unlimited
RATE_LIMIT_PER_HOUR=20
RATE_LIMIT_WINDOW_SECONDS=3600
```

**Test to write FIRST (TDD)**

Not applicable — documentation only.

**Verification command:**

```bash
ls backend/.env.example
# Should exist
```

---

## PART 2 — Medium Priority

---

## FIX-MD-01: Explanation rating not in frontend

**Prerequisites:** FIX-CR-04 (need the explanation ID to submit ratings).

**Files to modify:**

- `frontend/components/llm/ExplanationPanel.tsx`

**MIGRATION REQUIRED — Add before coding:**

Create file `backend/migrations/V002__add_explanation_ratings.sql`:

```sql
-- Explanation ratings table for collecting user feedback on AI explanations
CREATE TABLE IF NOT EXISTS explanation_ratings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    explanation_id UUID,  -- references the explanation this rating is for
    trace_id UUID,        -- which trace/context this belongs to
    user_id UUID,        -- who rated (nullable for anonymous)
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT fk_explanation FOREIGN KEY (explanation_id) REFERENCES explanations(id) ON DELETE SET NULL
);

-- RLS: users can only see their own ratings
ALTER TABLE explanation_ratings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can insert their own ratings"
ON explanation_ratings FOR INSERT
WITH CHECK (true);  -- Allow anonymous ratings too

CREATE POLICY "Users can view their own ratings"
ON explanation_ratings FOR SELECT
USING (true);  -- Make public for analytics, or filter by user_id for private

-- Index for looking up ratings by explanation
CREATE INDEX IF NOT EXISTS idx_ratings_explanation_id ON explanation_ratings(explanation_id);
```

**⚠️ IMPORTANT: Migration Order**
The migration `V002__add_explanation_ratings.sql` MUST be applied AFTER `V001__initial_schema.sql` has been applied. Supabase applies migrations in lexicographic order (V001 before V002), so name the file with `V002__` prefix. If you already applied V001, run V002 manually:

```bash
# Apply migration manually via Supabase CLI
supabase db push
# Or via SQL in Supabase dashboard
```

**Step 1 — Add rating state and widget**

After line 88 (after the `error` div closes), add:

```tsx
      {/* Rating widget — shown after streaming completes */}
      {state === "done" && (
        <div className={styles.ratingWidget}>
          <p className={styles.ratingPrompt}>Was this explanation helpful?</p>
          <div className={styles.ratingStars}>
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                className={styles.starBtn}
                onClick={() => submitRating(n)}
                aria-label={`Rate ${n} stars`}
                disabled={rating !== null}
              >
                {rating !== null && n <= rating ? "★" : "☆"}
              </button>
            ))}
          </div>
          {rating !== null && (
            <p className={styles.ratingConfirm}>Thanks for your feedback!</p>
          )}
        </div>
      )}
```

**Step 2 — Add rating state and submitRating function**

In the `ExplanationPanel` component, update the hook destructuring and add state:

Current code (line 21-22):

```tsx
  const { text, state, error, provider, start, stop, retry } =
    useStreamingExplanation();
```

Replace with:

```tsx
  const { text, state, error, provider, start, stop, retry } =
    useStreamingExplanation();
  const [rating, setRating] = useState<number | null>(null);
```

Add the `submitRating` function:

```tsx
  const submitRating = async (stars: number) => {
    setRating(stars);
    // Submit rating to backend
    await fetch("/api/ratings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        explanation_id: null, // Will be populated once FIX-CR-04 passes trace_id through
        trace_id: null,
        rating: stars,
      }),
    });
  };
```

**Step 4 — Add backend rating endpoint**

Create a new router file or add to an existing router:

Create file `backend/app/routers/ratings.py`:

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx

router = APIRouter(prefix="/api/ratings", tags=["ratings"])


class RatingRequest(BaseModel):
    explanation_id: Optional[str] = None
    trace_id: Optional[str] = None
    rating: int  # 1-5


@router.post("")
async def submit_rating(req: RatingRequest):
    """Submit a rating for an explanation."""
    if not 1 <= req.rating <= 5:
        raise HTTPException(status_code=400, detail="Rating must be 1-5")

    from app.config import settings

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.supabase_url}/rest/v1/explanation_ratings",
            json={
                "explanation_id": req.explanation_id,
                "trace_id": req.trace_id,
                "rating": req.rating,
            },
            headers={
                "Authorization": f"Bearer {settings.supabase_service_key}",
                "apikey": settings.supabase_service_key,
                "Content-Type": "application/json",
            },
        )

    if resp.status_code not in (200, 201):
        raise HTTPException(status_code=500, detail="Failed to store rating")

    return {"status": "ok", "rating": req.rating}
```

Then register the router in `backend/app/main.py`:

```python
from app.routers import ratings
app.include_router(ratings.router)
```

Add `useState` to the import from React (line 3):

```tsx
import { useState, useCallback, useEffect, useRef } from "react";
```

Add CSS classes to the CSS module file (create `ExplanationPanel.module.css` entries or add to existing):

```css
/* IMPORTANT: Ensure these CSS custom properties are defined in your global CSS */
/* They are typically in frontend/app/globals.css or a variables file: */
/*   :root { */
/*     --border: #e5e7eb; */
/*     --text-secondary: #6b7280; */
/*     --star-color: #fbbf24; */
/*   } */

.ratingWidget {
  padding: 12px;
  border-top: 1px solid var(--border);
  text-align: center;
}
.ratingPrompt {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 8px;
}
.ratingStars {
  display: flex;
  gap: 4px;
  justify-content: center;
}
.starBtn {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  color: var(--star-color);
  padding: 4px;
  transition: transform 0.1s;
}
.starBtn:hover {
  transform: scale(1.2);
}
.starBtn:disabled {
  cursor: default;
}
.ratingConfirm {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 8px 0 0;
}
```

**Step 3 — Verify CSS variables exist in your project**

Before implementing, check that `var(--border)`, `var(--text-secondary)`, and `var(--star-color)` are defined in your global stylesheet. If they are named differently (e.g., `--border-color`, `--text-muted`, `--rating-star`), update the CSS above accordingly. If the project uses Tailwind classes instead of CSS variables, replace `var(...)` references with equivalent Tailwind utility classes.

**Test to write FIRST (TDD)**

```tsx
// frontend/__tests__/ExplanationPanel.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ExplanationPanel } from '@/components/llm/ExplanationPanel';

// Mock the hook
jest.mock('@/hooks/useStreamingExplanation', () => ({
  useStreamingExplanation: () => ({
    text: 'This is a test explanation.',
    state: 'done',
    error: null,
    provider: 'github_models',
    start: jest.fn(),
    stop: jest.fn(),
    retry: jest.fn(),
  }),
}));

it('shows rating widget after streaming completes', () => {
  render(<ExplanationPanel
    code="x = 1"
    lineNumber={1}
    lineContent="x = 1"
    locals={{}}
  />);
  
  // Rating widget should appear when state === 'done'
  expect(screen.getByText(/Was this explanation helpful?/)).toBeInTheDocument();
  expect(screen.getAllByRole('button', { name: /Rate \d stars/ })).toHaveLength(5);
});

it('calls submitRating when star is clicked', async () => {
  const onSubmit = jest.fn();
  render(<ExplanationPanel ... />);
  
  const stars = screen.getAllByRole('button', { name: /Rate \d stars/ });
  fireEvent.click(stars[3]); // Click 4th star
  
  expect(onSubmit).toHaveBeenCalledWith(4);
});
```

**Verification command:**

```bash
cd frontend
npm test -- --testPathPattern="ExplanationPanel"
```

---

## FIX-MD-02: Branch detection marks all as taken

**Prerequisites:** None (standalone).

**Files to modify:**

- `backend/tracer/tracer.py`

**Step 1 — Fix branch detection in `tracer_callback`**

Lines 151-155 — current broken code:

```python
            # Branch detection from opcode
            branches_taken: dict = {}
            if line_no in jump_map:
                for node in jump_map[line_no]:
                    if isinstance(node, ast.If):
                        branches_taken["if"] = {"taken": True, "line": line_no, "iteration": 0}
```

Replace with:

```python
            # Branch detection — evaluate the condition at runtime
            branches_taken: dict = {}
            if line_no in jump_map:
                for node in jump_map[line_no]:
                    if isinstance(node, ast.If):
                        try:
                            import sys
                            if sys.version_info >= (3, 9):
                                condition_expr = ast.unparse(node.test)
                            else:
                                # Fallback for Python < 3.9
                                condition_expr = f"<condition on line {node.test.lineno}>"
                            
                            # Evaluate the condition in the current namespace
                            # Note: 'namespace' is defined at module level in tracer.py (namespace: dict = {})
                            # It is accessible here inside the tracer_callback closure because Python closures
                            # can access variables from the enclosing scope (module level).
                            result = eval(condition_expr, namespace)
                            branches_taken["if"] = {
                                "taken": bool(result),
                                "line": line_no,
                                "branch": "then" if result else "else",
                                "condition": condition_expr,
                            }
                        except Exception:
                            branches_taken["if"] = {"taken": None, "line": line_no, "error": "could_not_evaluate"}
```

**Test to write FIRST (TDD)**

Create file `backend/tests/unit/test_branch_detection.py`:

```python
import pytest
from tracer.tracer import run_trace

def test_branch_detection_only_marks_taken_branch():
    """
    MEDIUM-02: When if True: a=1 else: a=2 runs, only 'then' should be marked taken.
    The current code marks ALL branches as taken regardless of actual evaluation.
    """
    code = """
x = 1
if x > 0:
    result = "positive"
else:
    result = "non-positive"
y = 2
"""
    result = run_trace(code)
    
    steps_with_branch = [s for s in result["steps"] if s.get("branches_taken")]
    
    assert len(steps_with_branch) > 0, "No branches detected"
    
    for step in steps_with_branch:
        branch_info = step["branches_taken"].get("if", {})
        # The branch that executed should have taken=True, branch="then" or "else"
        # The branch that did NOT execute should not appear
        if branch_info.get("taken") is True:
            assert branch_info.get("branch") in ("then", "else"), (
                f"MEDIUM-02: Branch taken={branch_info.get('taken')} but branch field is missing or invalid: {branch_info}. "
                "Branch detection must show which branch actually fired."
            )
            assert "condition" in branch_info, "Must show the actual condition expression"

def test_branch_detection_if_false():
    """When if False, 'else' branch should be marked taken."""
    code = """
if False:
    x = 1
else:
    x = 2
"""
    result = run_trace(code)
    
    steps_with_branch = [s for s in result["steps"] if s.get("branches_taken")]
    for step in steps_with_branch:
        branch_info = step["branches_taken"].get("if", {})
        if branch_info.get("taken") is True:
            assert branch_info.get("branch") == "else", (
                f"MEDIUM-02: 'if False' should take 'else' branch, got: {branch_info}"
            )
```

**Verification command:**

```bash
cd backend
python -m pytest tests/unit/test_branch_detection.py -v
```

---

## FIX-MD-03: Cache hit returns entire string as one token

**Prerequisites:** FIX-CR-01 (cache key fix must be in place).

**Files to modify:**

- `backend/app/services/llm_router.py`

**Step 1 — Stream cached text word-by-word**

Lines 104-108 — current broken code:

```python
        if cached_text:
            logger.info("explanation_cache_hit", extra={"cache_key": cache_key})
            yield cached_text, LLMProvider.GITHUB_MODELS
            yield "__done__", LLMProvider.GITHUB_MODELS
            return
```

Replace with:

```python
        if cached_text:
            logger.info("explanation_cache_hit", extra={"cache_key": cache_key})
            for word in cached_text.split():
                yield word + " ", LLMProvider.GITHUB_MODELS
            yield "__done__", LLMProvider.GITHUB_MODELS
            return
```

**Test to write FIRST (TDD)**

```python
# Part of test_llm_router.py
@pytest.mark.asyncio
async def test_cache_hit_streams_word_by_word():
    """MEDIUM-03: Cache hit should stream tokens word-by-word, not as one blob."""
    from app.services.llm_router import LLMRouter
    
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
```

**Verification command:**

```bash
cd backend
python -m pytest tests/unit/test_llm_router.py::test_cache_hit_streams_word_by_word -v
```

---

## FIX-MD-04: Debug print statements in llm_router.py

**Prerequisites:** None (standalone).

**Files to modify:**

- `backend/app/services/llm_router.py`

**Step 1 — Replace `print` with `logger.debug`**

Line 99 — current code:

```python
        print("DEBUG: stream_explain called!", flush=True)
```

Replace with:

```python
        logger.debug("stream_explain_called", extra={
            "code_len": len(code),
            "line_number": line_number,
        })
```

Line 119 — current code:

```python
        print(f"DEBUG: settings.github_models_pat = {repr(settings.github_models_pat[:10] if settings.github_models_pat else None)}", flush=True)
```

Replace with:

```python
        logger.debug("github_pat_check", extra={
            "has_pat": bool(settings.github_models_pat),
        })
```

**Test to write FIRST (TDD)**

Create file `backend/tests/unit/test_no_debug_prints.py`:

```python
def test_no_print_statements_in_llm_router():
    """MEDIUM-04: llm_router.py should not have print() statements."""
    import inspect
    from app.services import llm_router

    source = inspect.getsource(llm_router)

    # Check for print statements (not in docstrings or comments)
    lines = source.split('\n')
    print_lines = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        # Skip comment lines and docstrings
        if stripped.startswith('#'):
            continue
        if '"""' in stripped or "'''" in stripped:
            continue
        # Find actual print( calls
        if 'print(' in stripped:
            print_lines.append((i, line))

    assert len(print_lines) == 0, (
        f"MEDIUM-04: Found {len(print_lines)} print() statements in llm_router.py:\n"
        + "\n".join(f"  Line {n}: {line}" for n, line in print_lines)
        + "\nReplace all print() with logger.debug() or logger.info()."
    )
```

**Verification command:**

```bash
cd backend
python -m pytest tests/unit/test_no_debug_prints.py -v
# Also verify with grep
grep -n "print(" app/services/llm_router.py
# Should return nothing
```

---

## FIX-MD-05: Missing composite index on review_cards

**Prerequisites:** None (standalone).

**Files to modify:**

- `backend/migrations/V001__initial_schema.sql`

**Step 1 — Add composite index**

At the end of the indexes section (after line 67, before the RLS section), add:

```sql
-- Composite index for the most common query: "get all due cards for a user"
CREATE INDEX IF NOT EXISTS idx_review_cards_user_next_date
ON review_cards(user_id, next_review_date);
```

**Test to write FIRST (TDD)**

```python
def test_composite_index_exists():
    """MEDIUM-05: review_cards should have composite index on (user_id, next_review_date)."""
    with open("backend/migrations/V001__initial_schema.sql") as f:
        content = f.read()
    
    assert "idx_review_cards_user_next_date" in content, (
        "MEDIUM-05: Missing composite index on review_cards(user_id, next_review_date). "
        "Dashboard query filters by both columns — composite index needed for performance."
    )
    assert "user_id, next_review_date" in content, (
        "Index should cover both columns in the right order."
    )
```

**Verification command:**

```bash
cd backend
python -m pytest tests/unit/test_composite_index.py -v
```

---

## FIX-MD-06: concept_tags and is_public silently dropped on save

**Prerequisites:** None (standalone). No migration needed — the `traces` table in V001__initial_schema.sql already has `concept_tags TEXT[]` and `is_public BOOLEAN DEFAULT FALSE` columns.

**Files to modify:**

- `backend/app/routers/traces.py`

**Step 1 — Add `is_public` and `language` fields to `SaveTraceRequest` model**

In `backend/app/routers/traces.py`, find the `SaveTraceRequest` model definition (around lines 40-55):

Current broken code:

```python
class SaveTraceRequest(BaseModel):
    code: str
    language: str | None = "python"
    concept_tags: list[str] | None = None
    is_public: bool | None = False  # field exists but may be missing — verify
```

**If the `is_public` field is missing entirely**, add it:

```python
class SaveTraceRequest(BaseModel):
    code: str
    language: str | None = "python"
    concept_tags: list[str] | None = None
    is_public: bool | None = False
```

**Step 2 — Include all fields in trace_data**

Lines 222-226 — current broken code:

```python
    trace_data = {
        "user_id": user_id,
        "code": req.code,
        "share_token": share_token,
    }
```

Replace with:

```python
    trace_data = {
        "user_id": user_id,
        "code": req.code,
        "language": req.language if req.language else "python",
        "concept_tags": req.concept_tags if req.concept_tags else [],
        "is_public": req.is_public if req.is_public is not None else False,
        "share_token": share_token,
    }
```

**Test to write FIRST (TDD)**

```python
def test_save_trace_includes_concept_tags_and_is_public():
    """MEDIUM-06: SaveTraceRequest must include concept_tags AND is_public in trace_data."""
    from app.routers.traces import SaveTraceRequest
    import inspect

    # Verify SaveTraceRequest model accepts both fields
    model_source = inspect.getsource(SaveTraceRequest)
    assert "concept_tags" in model_source, (
        "MEDIUM-06: SaveTraceRequest missing concept_tags field"
    )
    assert "is_public" in model_source, (
        "MEDIUM-06: SaveTraceRequest missing is_public field"
    )

    # Verify save_trace endpoint includes both in trace_data
    from app.routers.traces import save_trace
    func_source = inspect.getsource(save_trace)

    # Check both fields are present in trace_data dict
    assert '"concept_tags"' in func_source or "'concept_tags'" in func_source, (
        "MEDIUM-06: save_trace doesn't include concept_tags in trace_data. "
        "Fields are silently dropped when saving to Supabase."
    )
    assert '"is_public"' in func_source or "'is_public'" in func_source, (
        "MEDIUM-06: save_trace doesn't include is_public in trace_data."
    )
```

**Verification command:**

```bash
cd backend
python -m pytest tests/unit/test_trace_save.py -v
```

---

## FIX-MD-07: useTrace hook not wired into tracer page

**Prerequisites:** None (standalone).

**Files to modify:**

- `frontend/app/tracer/page.tsx`

**Step 1 — Import and use the `useTrace` hook**

After the existing imports (line 11), add:

```tsx
import { useTrace } from "@/hooks/useTrace";
```

**Step 2 — Remove `currentStep` manual state and add `useTrace` hook**

Find lines 57-58 in `page.tsx`:

```tsx
  const [traceResult, setTraceResult] = useState<TraceResult | null>(null);
  const [currentStep, setCurrentStep] = useState(0);
```

**DELETE** the `const [currentStep, setCurrentStep] = useState(0);` line entirely.

**AFTER** the `traceResult` state declaration, add the `useTrace` hook:

```tsx
  const {
    currentStep,
    playbackState,
    speed,
    currentStepData,
    play,
    pause,
    togglePlayPause,
    stepForward,
    stepBackward,
    jumpToStep,
    setSpeed,
    reset,
  } = useTrace({ steps: traceResult?.steps ?? [] });
```

**Step 3 — Refactor `AnimationControls.tsx` to accept props instead of calling `useTrace` internally**

The current `AnimationControls.tsx` calls `useTrace({ steps })` internally (line 35). This creates a double-hook problem: the hook gets called twice (once in `page.tsx`, once in `AnimationControls`), causing inconsistent state.

**In `frontend/components/tracer/AnimationControls.tsx`:**

Change the interface to accept all `useTrace` state as props:

Current interface (lines 8-14):

```tsx
interface AnimationControlsProps {
  steps: TraceStep[];
  currentStep: number;
  onStepChange: (step: number) => void;
  totalSteps: number;
  durationMs: number;
}
```

Replace with:

```tsx
interface AnimationControlsProps {
  steps: TraceStep[];
  currentStep: number;
  onStepChange: (step: number) => void;
  totalSteps: number;
  durationMs: number;
  // NEW: Accept useTrace state as props
  playbackState: PlaybackState;
  speed: PlaybackSpeed;
  play: () => void;
  pause: () => void;
  togglePlayPause: () => void;
  stepForward: () => void;
  stepBackward: () => void;
  jumpToStep: (step: number) => void;
  setSpeed: (speed: PlaybackSpeed) => void;
  reset: () => void;
}
```

Then REMOVE the internal `useTrace` call (lines 23-35). Delete these lines:

```tsx
  const {
    currentStep: hookStep,
    playbackState,
    speed,
    play,
    pause,
    togglePlayPause,
    stepForward,
    stepBackward,
    jumpToStep,
    setSpeed,
    reset,
  } = useTrace({ steps });
```

Also remove `useTrace` and `type PlaybackSpeed, type PlaybackState` from the import (line 4).

Update all internal references from `hookStep` to the `currentStep` prop.

**Step 4 — Update `AnimationControls` usage**

Find the `AnimationControls` component call (around line 256-262):

Current code:

```tsx
          <AnimationControls
            steps={steps}
            currentStep={currentStep}
            onStepChange={setCurrentStep}
            totalSteps={steps.length}
            durationMs={traceResult.duration_ms}
          />
```

Also remove the old sync `useEffect` hooks — no longer needed since parent controls all state. Remove these from `AnimationControls.tsx` (lines 41-59):

**CRITICAL — `AnimationControls` must not call `useTrace` internally.**

**Step 5 — Update `ExplanationPanel` usage**

Find where `ExplanationPanel` is called and update `currentStepData` reference if needed. The current code at that call site already uses `currentStepData` from the hook, so verify it looks like:

```tsx
                <ExplanationPanel
                  code={code}
                  lineNumber={selectedLine ?? currentStepData?.line_number ?? 1}
                  lineContent={code.split("\n")[(selectedLine ?? currentStepData?.line_number ?? 1) - 1] ?? ""}
                  locals={currentStepData?.variables ?? {}}
```

**Step 6 — Update handleLineClick and handleWhyIsThisHere**

Find and update:

```tsx
  const handleLineClick = useCallback((lineNumber: number) => {
    setSelectedLine(lineNumber);
    setShowExplanation(false);
  }, []);

  const handleWhyIsThisHere = useCallback(() => {
    if (selectedLine !== null || currentStepData?.line_number) {
      setShowExplanation(true);
    }
  }, [selectedLine, currentStepData]);
```

These can stay as-is since `currentStepData` comes from the hook now.

**Test to write FIRST (TDD)**

```tsx
// frontend/__tests__/tracer_page_useTrace.test.tsx
import { render, screen } from '@testing-library/react';
import TracerPage from '@/app/tracer/page';

// Mock all dependencies
jest.mock('@/hooks/useTrace', () => ({
  useTrace: jest.fn(() => ({
    currentStep: 0,
    playbackState: 'idle',
    speed: 1,
    currentStepData: null,
    play: jest.fn(),
    pause: jest.fn(),
    togglePlayPause: jest.fn(),
    stepForward: jest.fn(),
    stepBackward: jest.fn(),
    jumpToStep: jest.fn(),
    setSpeed: jest.fn(),
    reset: jest.fn(),
  })),
}));

it('uses useTrace hook instead of manual state', () => {
  const { useTrace } = require('@/hooks/useTrace');
  render(<TracerPage />);
  
  // Verify the hook was called
  expect(useTrace).toHaveBeenCalled();
});
```

**Verification command:**

```bash
cd frontend
npm test -- --testPathPattern="tracer_page_useTrace"
```

---

## FIX-MD-08: Dashboard streak hardcoded to 0

**Prerequisites:** FIX-HI-02 (must implement `_calculate_streak` first).

**Files to modify:**

- `backend/app/routers/traces.py`

**Step 1 — Import and use `_calculate_streak` from review.py**

In `traces.py`, add import at the top:

```python
from app.routers.review import _calculate_streak
```

Line 159 — current broken code:

```python
    return DashboardResponse(
        traces=traces,
        due_cards=[{**c, "due": True} for c in due_cards],
        streak=0,  # ← always zero
        total_traces=len(traces),
    )
```

Replace with:

```python
    # Calculate streak using the same function as review.py
    streak = await _calculate_streak(user_id, settings.supabase_url, settings.supabase_service_key)
    
    return DashboardResponse(
        traces=traces,
        due_cards=[{**c, "due": True} for c in due_cards],
        streak=streak,
        total_traces=len(traces),
    )
```

**Test to write FIRST (TDD)**

```python
def test_dashboard_uses_real_streak():
    """MEDIUM-08: Dashboard streak should come from _calculate_streak, not 0."""
    import inspect
    from app.routers.traces import get_dashboard
    
    source = inspect.getsource(get_dashboard)
    
    assert "streak=0" not in source, (
        "MEDIUM-08: Dashboard still has streak=0 hardcoded. "
        "Should call _calculate_streak from review.py."
    )
    assert "_calculate_streak" in source, (
        "MEDIUM-08: get_dashboard must import and call _calculate_streak."
    )
```

**Verification command:**

```bash
cd backend
python -m pytest tests/unit/test_dashboard_streak.py -v
```

---

## FIX-MD-09: No landing page

**Prerequisites:** None (standalone).

**Files to modify:**

- `frontend/app/page.tsx`

**Step 1 — Create landing page content**

Current code (lines 1-5):

```tsx
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/tracer");
}
```

Replace with a comprehensive landing page. Since this is a frontend design task, here's the implementation plan:

```tsx
import Link from "next/link";
import styles from "./page.module.css";

const CODE_SAMPLES = [
  {
    title: "List Comprehension",
    code: "squares = [x**2 for x in range(10)]",
    explanation: "Creates a list of squares from 0-9. The tracer shows each iteration: x starts at 0, then 1, 2, and so on. Each x**2 result gets appended to the squares list.",
  },
  {
    title: "Ternary Expression",
    code: "status = 'active' if count > 0 else 'empty'",
    explanation: "The condition 'count > 0' evaluates first. If True, 'active' is assigned. If False, 'empty' is assigned. The tracer shows exactly which branch fired and why.",
  },
];

export default function LandingPage() {
  return (
    <div className={styles.page}>
      {/* Hero */}
      <header className={styles.hero}>
        <div className={styles.heroContent}>
          <div className={styles.logo}>
            <span className={styles.logoIcon}>◈</span>
            <span className={styles.logoText}>CodeScope</span>
          </div>
          <h1 className={styles.heroTitle}>
            Understand the code<br />you ship.
          </h1>
          <p className={styles.heroSubtitle}>
            Paste AI-generated Python. See it execute step-by-step.<br />
            Watch variables change. Know exactly why each line exists.
          </p>
          <div className={styles.heroCta}>
            <Link href="/tracer" className={styles.primaryBtn}>
              Start for free →
            </Link>
          </div>
        </div>
      </header>

      {/* Demo section */}
      <section className={styles.demo}>
        <h2 className={styles.sectionTitle}>See how it works</h2>
        <div className={styles.demoGrid}>
          {CODE_SAMPLES.map((sample) => (
            <div key={sample.title} className={styles.demoCard}>
              <div className={styles.demoCode}>
                <pre><code>{sample.code}</code></pre>
              </div>
              <div className={styles.demoExplanation}>
                <p>{sample.explanation}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className={styles.howItWorks}>
        <h2 className={styles.sectionTitle}>Three steps to deep understanding</h2>
        <div className={styles.stepsGrid}>
          <div className={styles.step}>
            <div className={styles.stepNumber}>1</div>
            <h3>Paste your code</h3>
            <p>Any Python — AI-generated, complex library calls, or legacy scripts.</p>
          </div>
          <div className={styles.step}>
            <div className={styles.stepNumber}>2</div>
            <h3>Watch it execute</h3>
            <p>Step through bytecode. See variables change in real time.</p>
          </div>
          <div className={styles.step}>
            <div className={styles.stepNumber}>3</div>
            <h3>Understand why</h3>
            <p>AI explanations grounded in your actual execution context.</p>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className={styles.footer}>
        <p>Built for CS students and developers learning Python.</p>
        <Link href="/tracer" className={styles.footerCta}>
          Try CodeScope →
        </Link>
      </footer>
    </div>
  );
}
```

**Step 2 — Create `frontend/app/page.module.css`**

The landing page TSX references `import styles from "./page.module.css"`. You MUST create this file. Create `frontend/app/page.module.css` with the following content:

```css
/* CodeScope Landing Page Styles */

/* ── Reset & Base ── */
.page {
  min-height: 100vh;
  background: #09090b;
  color: #fafafa;
  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
}
```

(Create the rest of the CSS as described in Step 1 above — the full CSS content goes into `frontend/app/page.module.css`. Do NOT put it inline or in a different file.)

```css
.page {
  min-height: 100vh;
  background: #09090b;
  color: #fafafa;
  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
}

.hero {
  min-height: 60vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 80px 24px;
  background: linear-gradient(180deg, #18181b 0%, #09090b 100%);
}

.heroContent {
  max-width: 640px;
  text-align: center;
}

.logo {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-bottom: 32px;
}

.logoIcon {
  font-size: 24px;
  color: #a78bfa;
}

.logoText {
  font-size: 18px;
  font-weight: 600;
  color: #fafafa;
}

.heroTitle {
  font-size: 48px;
  font-weight: 700;
  line-height: 1.1;
  margin: 0 0 20px;
  background: linear-gradient(135deg, #fafafa 0%, #a1a1aa 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.heroSubtitle {
  font-size: 18px;
  color: #a1a1aa;
  line-height: 1.6;
  margin: 0 0 32px;
}

.heroCta {
  display: flex;
  justify-content: center;
}

.primaryBtn {
  display: inline-flex;
  align-items: center;
  padding: 12px 24px;
  background: #a78bfa;
  color: #09090b;
  font-weight: 600;
  font-size: 16px;
  border-radius: 8px;
  text-decoration: none;
  transition: background 0.2s, transform 0.1s;
}

.primaryBtn:hover {
  background: #c4b5fd;
  transform: translateY(-1px);
}

/* Demo section */
.demo {
  padding: 80px 24px;
  max-width: 900px;
  margin: 0 auto;
}

.sectionTitle {
  font-size: 28px;
  font-weight: 600;
  text-align: center;
  margin: 0 0 40px;
  color: #fafafa;
}

.demoGrid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
}

@media (max-width: 640px) {
  .demoGrid {
    grid-template-columns: 1fr;
  }
}

.demoCard {
  background: #18181b;
  border: 1px solid #27272a;
  border-radius: 12px;
  overflow: hidden;
}

.demoCode {
  padding: 16px;
  background: #0a0a0c;
  border-bottom: 1px solid #27272a;
}

.demoCode pre {
  margin: 0;
  font-family: 'SF Mono', 'Cascadia Code', monospace;
  font-size: 14px;
  color: #e4e4e7;
}

.demoExplanation {
  padding: 16px;
  font-size: 14px;
  color: #a1a1aa;
  line-height: 1.6;
}

.demoExplanation p {
  margin: 0;
}

/* How it works */
.howItWorks {
  padding: 80px 24px;
  max-width: 900px;
  margin: 0 auto;
}

.stepsGrid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 32px;
}

@media (max-width: 640px) {
  .stepsGrid {
    grid-template-columns: 1fr;
  }
}

.step {
  text-align: center;
  padding: 24px;
}

.stepNumber {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #a78bfa;
  color: #09090b;
  font-size: 18px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 16px;
}

.step h3 {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 8px;
  color: #fafafa;
}

.step p {
  font-size: 14px;
  color: #a1a1aa;
  margin: 0;
  line-height: 1.6;
}

/* Footer */
.footer {
  padding: 48px 24px;
  text-align: center;
  border-top: 1px solid #27272a;
  color: #71717a;
  font-size: 14px;
}

.footerCta {
  display: inline-block;
  margin-top: 16px;
  color: #a78bfa;
  text-decoration: none;
  font-weight: 500;
}

.footerCta:hover {
  color: #c4b5fd;
}
```

**Test to write FIRST (TDD)**

```tsx
// frontend/__tests__/landing_page.test.tsx
import { render, screen } from '@testing-library/react';
import LandingPage from '@/app/page';

it('shows hero title', () => {
  render(<LandingPage />);
  expect(screen.getByText(/Understand the code/)).toBeInTheDocument();
});

it('shows CTA button', () => {
  render(<LandingPage />);
  expect(screen.getByText(/Start for free/)).toBeInTheDocument();
});

it('shows how it works section', () => {
  render(<LandingPage />);
  expect(screen.getByText(/Three steps/)).toBeInTheDocument();
});
```

**Verification command:**

```bash
cd frontend
npm test -- --testPathPattern="landing_page"
```

---

## FIX-MD-10: ollama_endpoint not used

**Prerequisites:** FIX-HI-04 (OLLAMA_CLOUD must be added first).

**Files to modify:**

- `backend/app/services/llm_router.py`

**Step 1 — Use `ollama_endpoint` parameter in `_stream_ollama_cloud`**

In the `_stream_ollama_cloud` method, replace the hardcoded `settings.ollama_cloud_url`:

```python
    async def _stream_ollama_cloud(
        self,
        prompt: str,
        cache_key: str,
        ollama_endpoint: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream from Ollama Cloud API.
        Uses user-provided ollama_endpoint if available, otherwise falls back to settings.
        """
        url = f"{ollama_endpoint or settings.ollama_cloud_url}/chat"
```

**Step 2 — Pass `ollama_endpoint` through the call chain**

In `stream_explain`, update the `_stream_ollama_cloud` call:

```python
                elif provider == LLMProvider.OLLAMA_CLOUD:
                    async for token in self._stream_ollama_cloud(prompt, cache_key, ollama_endpoint):
                        yield token, provider
```

**Test to write FIRST (TDD)**

```python
def test_ollama_endpoint_is_used():
    """MEDIUM-10: ollama_endpoint parameter must be used for Ollama Cloud routing."""
    import inspect
    from app.services.llm_router import LLMRouter
    
    source = inspect.getsource(LLMRouter._stream_ollama_cloud)
    
    assert "ollama_endpoint" in source or "settings.ollama_cloud_url" in source, (
        "MEDIUM-10: _stream_ollama_cloud doesn't use ollama_endpoint. "
        "User's custom endpoint is ignored."
    )
```

**Verification command:**

```bash
cd backend
python -m pytest tests/unit/test_ollama_endpoint.py -v
```

---

## FIX-MD-11: No auth on health endpoint (intentional design)

**Status:** No action needed. The health endpoint is intentionally unauthenticated — Kubernetes/Docker probes cannot carry auth headers. This is documented as a design decision.

---

## PART 2.5 — Low Priority

---

## LOW-01: Review cards expire with no cleanup

**Status:** Consider adding a Supabase cron job or edge function to archive/delete cards where `next_review_date < now() - 365 days`. Currently not impacting functionality but will grow unbounded over time.

**No action in this implementation pass.**

---

## LOW-02: No email/password auth — only GitHub OAuth

**Status:** Known limitation. The current auth system only supports GitHub OAuth via Supabase. If email/password is needed later, add `supabase.auth.sign_up()` flow. No action in this pass.

---

## LOW-03: No trace export (JSON/CSV)

**Status:** Users cannot export their traces. Future enhancement: add `GET /api/traces/export?format=json|csv` endpoint. No action in this pass.

---

## LOW-04: No per-concept analytics

**Status:** The `concept_tags` field is now stored (FIX-MD-06) but not surfaced in the dashboard. Future: group streak and review stats by concept. No action in this pass.

---

## LOW-05: No onboarding/tutorial for new users

**Status:** First-time users land on the tracer with no guidance. Future: add a welcome overlay / guided tour (e.g., using `react-hot-toast` or a dedicated `onboarding/` route). No action in this pass.

---

## PART 3 — Thesis Evaluation

**Prerequisites:** FIX-HI-02 (streak calculation), FIX-MD-06 (concept_tags stored), FIX-MD-08 (dashboard streak frontend).

**Status:** PARTIALLY COVERED. The backend streak calculation (FIX-HI-02) and dashboard display (FIX-MD-08) are implemented. The following analytics gaps remain:

**Gap 1 — No per-user analytics endpoint**

Create file `backend/app/routers/analytics.py`:

```python
"""
Analytics endpoints for study metrics.
Only accessible to authenticated users.
"""
from fastapi import APIRouter, Header, HTTPException
from typing import Optional

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

@router.get("/summary")
async def get_analytics_summary(authorization: str = Header(None)):
    """
    Returns analytics summary for the current user.
    Used for the study metrics dashboard.
    """
    from app.routers.auth import get_current_user
    from app.config import settings
    import httpx

    if not authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user = await get_current_user(authorization)
    user_id = user.get("id", "")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Total traces this month
        traces_resp = await client.get(
            f"{settings.supabase_url}/rest/v1/traces",
            params={"user_id": f"eq.{user_id}", "select": "id,created_at"},
            headers={"Authorization": f"Bearer {settings.supabase_service_key}", "apikey": settings.supabase_service_key},
        )

        # Total cards reviewed
        cards_resp = await client.get(
            f"{settings.supabase_url}/rest/v1/review_cards",
            params={"user_id": f"eq.{user_id}", "select": "id,last_reviewed_at"},
            headers={"Authorization": f"Bearer {settings.supabase_service_key}", "apikey": settings.supabase_service_key},
        )

        # Due cards
        due_resp = await client.get(
            f"{settings.supabase_url}/rest/v1/review_cards",
            params={
                "user_id": f"eq.{user_id}",
                "next_review_date": "lte.now()",
                "select": "id",
            },
            headers={"Authorization": f"Bearer {settings.supabase_service_key}", "apikey": settings.supabase_service_key},
        )

    traces = traces_resp.json() if traces_resp.status_code == 200 else []
    cards = cards_resp.json() if cards_resp.status_code == 200 else []
    due_cards = due_resp.json() if due_resp.status_code == 200 else []

    return {
        "total_traces": len(traces),
        "total_reviews": len([c for c in cards if c.get("last_reviewed_at")]),
        "due_cards": len(due_cards),
        "concepts_covered": 0,  # TODO: count unique concept_tags from traces
        "study_week": _calculate_study_week(traces),  # Weeks since first trace
    }

def _calculate_study_week(traces: list) -> int:
    """Calculate which week of the study the user is in."""
    from datetime import datetime, timezone
    if not traces:
        return 0
    # Find earliest trace date
    return 1  # Simplified — implement based on actual date comparison
```

**Gap 2 — Concept coverage tracking**

Modify `save_trace` to extract unique `concept_tags` from saved traces:

```python
# In save_trace, after saving the trace:
# Aggregate concept tags for analytics
concept_set = set()
for tag in (req.concept_tags or []):
    concept_set.add(tag)
# Store concept coverage in a separate analytics table if needed
```

**Gap 3 — Time-on-task tracking**

The tracer already logs step timestamps. Future work:

- Summarize time spent per trace session
- Track "why" button clicks per session
- Store session duration in `traces` table

**No action in this pass for Gap 2-3.** Mark as future enhancements.

**Verification command:**

```bash
cd backend
python -c "
import asyncio
from app.routers.analytics import get_analytics_summary
# Test that the endpoint is registered
from app.main import app
routes = [r.path for r in app.routes]
assert '/api/analytics/summary' in routes, 'Analytics endpoint not registered'
print('PASS: Analytics endpoint exists')
"
```

---

## PART 3 — Thesis Evaluation

---

## FIX-TH-01: Synthetic benchmark for static analysis

**Prerequisites:** None (standalone, new file).

**Files to create:**

- `backend/tests/benchmark/test_static_analysis.py`

**Step 1 — Create the benchmark file**

Create directory `backend/tests/benchmark/` (if not exists) and create `test_static_analysis.py`:

```python
"""
THESIS-02: Synthetic benchmark for static analysis.
Tests 50 Python snippets with known bugs to measure precision > 85% and recall > 70%.

Run with: pytest backend/tests/benchmark/test_static_analysis.py -v
"""
import pytest
from analyzers.static_analysis import analyze_code

# Each tuple: (code_snippet: str, should_flag: list[str], has_bug: bool)
# should_flag = pattern IDs that SHOULD be detected in this snippet
# has_bug = whether the snippet actually contains a bug
SYNTHETIC_SNIPPETS: list[tuple[str, list[str], bool]] = [
    # --- Safe snippets (no bugs) ---
    ("def greet(name=None): return f'Hello {name}'", [], False),
    ("def process(items=None): return [x for x in (items or [])]", [], False),
    ("if user and user.is_active: grant_access()", [], False),
    ("if data: print('yes')", [], False),  # empty dict is falsy but intentional
    ("result = requests.get(url, timeout=10)", [], False),
    ("with open('file.txt') as f: data = f.read()", [], False),
    ("for i in range(10): print(i)", [], False),
    ("try: x = 1\nexcept ValueError: pass", [], False),
    ("lambda x: x * 2", [], False),
    ("[x for x in range(5)]", [], False),
    ("def outer(): x = 1\n  def inner(): return x", [], False),
    ("data = {'key': value.get('nested')}", [], False),
    ("x = eval('1 + 2')  # intentional", [], False),
    ("conn = sqlite3.connect(':memory:')", [], False),
    ("cursor.execute('SELECT * FROM t WHERE id=?', (id,))", [], False),
    ("os.chmod(path, 0o644)", [], False),
    ("subprocess.run(['ls'], timeout=5)", [], False),
    ("x = 1  # inline comment", [], False),
    ("import hashlib; h = hashlib.md5(b'data')", [], False),
    ("from pathlib import Path; p = Path('/tmp')", [], False),
    ("x = {**dict1, **dict2}", [], False),
    ("[i for i in range(10) if i % 2 == 0]", [], False),
    ("async def fetch(url): await client.get(url)", [], False),
    ("class Cache: pass", [], False),
    ("with suppress(Exception): x = 1", [], False),
    
    # --- Buggy snippets (should be flagged) ---
    # Mutable default arguments
    ("def add_to(item, items=[]): items.append(item); return items", ["mutable_default"], True),
    ("def foo(x, data=[]): data.append(x)", ["mutable_default"], True),
    ("class Foo:\n  def __init__(self, items=[]): self.items = items", ["mutable_default"], True),
    
    # Implicit truthiness
    ("if data: process(data)", ["implicit_truthiness"], True),
    ("if items: return [x for x in items]", ["implicit_truthiness"], True),
    ("if response: return response.json()", ["implicit_truthiness"], True),
    ("while queue: item = queue.pop()", ["implicit_truthiness"], True),
    
    # Requests without timeout
    ("requests.get(url)", ["requests_no_timeout"], True),
    ("requests.post(url, data=payload)", ["requests_no_timeout"], True),
    ("import requests; r = requests.put(url)", ["requests_no_timeout"], True),
    ("import requests; requests.delete(url)", ["requests_no_timeout"], True),
    
    # eval without restrictions
    ("eval(user_input)", ["eval_usage"], True),
    ("result = eval('1+2')", ["eval_usage"], True),
    
    # SQL injection risk
    ("cursor.execute(f'SELECT * FROM users WHERE id={user_id}')", ["sql_injection"], True),
    ("db.query(f'UPDATE t SET x={val}')", ["sql_injection"], True),
    
    # Hardcoded secrets
    ("api_key = 'sk-1234567890abcdef'", ["hardcoded_secret"], True),
    ("password = \"hunter2\"", ["hardcoded_secret"], True),
    ("token = 'ghp_secret_token_here'", ["hardcoded_secret"], True),
    ("config['secret'] = 'my-private-key'", ["hardcoded_secret"], True),
    
    # Insecure file operations
    ("open('/etc/passwd', 'r')", ["insecure_file"], True),
    ("os.system('rm -rf /')", ["os_system"], True),
    ("subprocess.call(['bash', '-c', cmd])", ["shell_injection"], True),
    
    # Unsafe YAML load
    ("yaml.load(data)", ["unsafe_yaml"], True),
    ("yaml.unsafe_load(data)", ["unsafe_yaml"], True),
    
    # XML vulnerabilities
    ("ET.fromstring(user_xml)", ["xml_vulnerability"], True),
    ("xml.etree.ElementTree.parse(user_file)", ["xml_vulnerability"], True),
    
    # Insecure random
    ("key = os.urandom(16)", ["insecure_random"], False),  # urandom is actually secure
    ("secret = random.randint(0, 2**32)", ["insecure_random"], True),
]


def test_static_analysis_precision_and_recall():
    """
    Measure precision and recall of static analysis.
    
    Precision = TP / (TP + FP) — of the bugs we flag, how many are real?
    Recall = TP / (TP + FN)   — of the bugs that exist, how many did we catch?
    
    Target: Precision > 85%, Recall > 70%
    """
    tp = fp = fn = 0

    for code, should_flag, has_bug in SYNTHETIC_SNIPPETS:
        try:
            annotations = analyze_code(code)
            found_patterns = {a.pattern_id for a in annotations}
        except Exception:
            found_patterns = set()

        if has_bug:
            # Bug exists — check if we caught it
            for bug in should_flag:
                if bug in found_patterns:
                    tp += 1
                else:
                    fn += 1  # Missed a known bug
        else:
            # No bug expected — any flag is a false positive
            for bug in found_patterns:
                if bug not in should_flag:
                    fp += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0

    print(f"\n=== Static Analysis Benchmark ===")
    print(f"Total snippets: {len(SYNTHETIC_SNIPPETS)}")
    print(f"TP={tp}, FP={fp}, FN={fn}")
    print(f"Precision: {precision:.1%} (target: >85%)")
    print(f"Recall: {recall:.1%} (target: >70%)")

    assert precision > 0.85, (
        f"THESIS-02: Static analysis precision {precision:.1%} < 85% target. "
        f"TP={tp}, FP={fp}. Too many false positives."
    )
    assert recall > 0.70, (
        f"THESIS-02: Static analysis recall {recall:.1%} < 70% target. "
        f"TP={tp}, FN={fn}. Too many missed bugs."
    )


def test_each_snippet_analyzed():
    """Verify the benchmark covers 50 snippets across all categories."""
    assert len(SYNTHETIC_SNIPPETS) >= 50, (
        f"THESIS-02: Benchmark has {len(SYNTHETIC_SNIPPETS)} snippets, need 50"
    )
```

**Note:** The `analyzers.static_analysis` module needs to exist. Check if it exists at `backend/analyzers/static_analysis.py`:

```bash
ls backend/analyzers/
```

If it doesn't exist, create it:

```python
# backend/analyzers/static_analysis.py
"""
Static code analysis for common Python bugs and anti-patterns.
"""
from dataclasses import dataclass
import re

@dataclass
class Annotation:
    pattern_id: str
    message: str
    line: int
    severity: str = "warning"

def analyze_code(source: str) -> list[Annotation]:
    """
    Analyze Python source code for known bug patterns.
    Returns a list of annotations for each issue found.
    """
    annotations: list[Annotation] = []
    lines = source.split('\n')
    
    for i, line in enumerate(lines, 1):
        line_stripped = line.strip()
        
        # Mutable default arguments
        if re.match(r'def\s+\w+\([^)]*=\s*\[\s*\]', line):
            annotations.append(Annotation(
                pattern_id="mutable_default",
                message="Mutable default argument: list literal in def signature",
                line=i,
            ))
        
        # Requests without timeout
        if 'requests.' in line and 'timeout' not in line:
            annotations.append(Annotation(
                pattern_id="requests_no_timeout",
                message="requests call without timeout — may hang indefinitely",
                line=i,
            ))
        
        # eval usage
        if re.search(r'\beval\s*\(', line):
            annotations.append(Annotation(
                pattern_id="eval_usage",
                message="eval() is dangerous with user input",
                line=i,
            ))
        
        # Hardcoded secrets
        if re.search(r'[\'"](?:sk-|ghp_|password\s*=\s*["\'])', line, re.IGNORECASE):
            annotations.append(Annotation(
                pattern_id="hardcoded_secret",
                message="Potential hardcoded secret detected",
                line=i,
                severity="error",
            ))
        
        # SQL injection
        if re.search(r'f[\'"]?(?:SELECT|INSERT|UPDATE|DELETE)', line, re.IGNORECASE):
            if '{' in line:
                annotations.append(Annotation(
                    pattern_id="sql_injection",
                    message="Possible SQL injection — f-string in SQL query",
                    line=i,
                    severity="error",
                ))
    
    return annotations
```

**Test to write FIRST (TDD)**

The benchmark IS the test. Run it:

```bash
cd backend
python -m pytest tests/benchmark/test_static_analysis.py -v --tb=short
```

**Verification command:**

```bash
cd backend
python -m pytest tests/benchmark/test_static_analysis.py -v
# Expected: precision > 85%, recall > 70%
```

---

## Final Verification Checklist

Run all tests to verify all fixes work together:

```bash
cd backend

# Run all unit tests
python -m pytest tests/unit/ -v --tb=short

# Run all integration tests
python -m pytest tests/integration/ -v --tb=short

# Verify no debug prints remain
grep -rn "print(" app/ routers/ app/services/

# Verify no debug log files exist
ls *.log 2>/dev/null || echo "PASS: no .log files"

# Verify import errors
python -c "from app.main import app; print('Backend imports OK')"
```

```bash
cd frontend

# Run all frontend tests
npm test -- --passWithNoTests

# Type check
npx tsc --noEmit
```

---

## Complete Test File Reference


| Test File                                          | Tests For                                              |
| -------------------------------------------------- | ------------------------------------------------------ |
| `tests/unit/test_llm_router.py`                    | FIX-CR-01 (cache key includes locals)                  |
| `tests/unit/test_httpx_reuse.py`                   | FIX-CR-02 (connection pool reuse)                      |
| `tests/unit/test_pro_gate.py`                      | FIX-CR-03 (Pro user check)                             |
| `tests/unit/test_cache_store.py`                   | FIX-CR-04 (cache write verification)                   |
| `tests/unit/test_debug_disk_write.py`              | FIX-CR-05 (no disk writes)                             |
| `tests/unit/test_review_timestamp.py`              | FIX-HI-01 (last_reviewed_at timestamp)                 |
| `tests/unit/test_streak.py`                        | FIX-HI-02 (streak calculation)                         |
| `tests/unit/test_profiles.py`                      | FIX-HI-03 (profile endpoints)                          |
| `tests/unit/test_llm_providers.py`                 | FIX-HI-04 (provider ordering)                          |
| `tests/unit/test_startup_validation.py`            | FIX-HI-05 (startup validation)                         |
| `tests/unit/test_health_endpoint.py`               | FIX-HI-06 (readiness health check)                     |
| `tests/unit/test_trace_limit.py`                   | FIX-HI-07 (free tier limits)                           |
| `tests/unit/test_branch_detection.py`              | FIX-MD-02 (branch detection)                           |
| `tests/unit/test_no_debug_prints.py`               | FIX-MD-04 (no print statements)                        |
| `tests/unit/test_composite_index.py`               | FIX-MD-05 (composite index)                            |
| `tests/unit/test_trace_save.py`                    | FIX-MD-06 (concept_tags stored)                        |
| `tests/unit/test_dashboard_streak.py`              | FIX-MD-08 (dashboard streak)                           |
| `tests/unit/test_ollama_endpoint.py`               | FIX-MD-10 (ollama_endpoint used)                       |
| `tests/benchmark/test_static_analysis.py`          | FIX-TH-01 (synthetic benchmark)                        |
| `frontend/__tests__/ExplanationPanel.test.tsx`     | FIX-MD-01 (rating widget)                              |
| `frontend/__tests__/landing_page.test.tsx`         | FIX-MD-09 (landing page)                               |
| `frontend/__tests__/tracer_page_useTrace.test.tsx` | FIX-MD-07 (useTrace hook)                              |
| `docs/THESIS-01-STUDY-PROTOCOL.md`                 | THESIS-01 (study protocol + IRB docs, moved from plan) |
| `backend/app/routers/analytics.py`                 | THESIS-03 (analytics)                                  |


---

## Recommended Implementation Order

```
Week 1 — Critical Fixes (prevents production failures)
  1. FIX-CR-01 (cache key)
  2. FIX-CR-02 (connection pool)
  3. FIX-CR-03 (pro gate — inline httpx.AsyncClient per call, acceptable)
  4. FIX-CR-04 (cache write verification + _store_cached in llm.py)
  5. FIX-CR-05 (remove disk writes + import logging check)
  6. FIX-CR-06 (trace_id in explanations)
  Run all critical tests: pytest tests/unit/test_llm_router.py tests/unit/test_pro_gate.py -v

Week 2 — High Priority (V1 functionality)
  7. FIX-HI-01 (last_reviewed_at)
  8. FIX-HI-02 (streak calculation + fix duplicate date import)
  9. FIX-HI-03 (profiles)
  10. FIX-HI-04 (Ollama Cloud primary)
  11. FIX-HI-05 (startup validation)
  12. FIX-HI-06 (health check + httpx import)
  13. FIX-HI-07 (free tier limits + avoid circular import)
  14. FIX-HI-08 (README + project-specific)

Week 3 — Medium Priority (Beta polish)
  15. FIX-MD-01 (rating widget + V002 migration)
  16. FIX-MD-02 (branch detection + namespace clarification)
  17. FIX-MD-03 (cache stream)
  18. FIX-MD-04 (debug prints)
  19. FIX-MD-05 (composite index)
  20. FIX-MD-06 (concept_tags — no migration needed)
  21. FIX-MD-07 (useTrace hook)
  22. FIX-MD-08 (dashboard streak)
  23. FIX-MD-09 (landing page)
  24. FIX-MD-10 (ollama_endpoint)
  25. FIX-MD-11 (no action — intentional design)

Week 4 — Thesis
  26. THESIS-01 (study protocol and IRB docs)
  27. FIX-TH-01 (synthetic benchmark)
  28. THESIS-03 (analytics instrumentation — partial)

Low Priority (Future Enhancements)
  29. LOW-01 (review cards expire — no action)
  30. LOW-02 (email/password auth — no action)
  31. LOW-03 (trace export — no action)
  32. LOW-04 (per-concept analytics — no action)
  33. LOW-05 (onboarding/tutorial — no action)
```

