# CodeScope — Action Roadmap

**Generated:** 2026-05-12  
**Status:** All findings synthesized from SPEC.md, codescope_prd.md, and full codebase audit  
**Quality target:** 9/10 — every critical and high finding addressed before launch

---

## How to Read This Document

- **Critical** = will break in production or expose users to harm. Fix before any launch.
- **High** = functional gaps that break core user stories. Fix before calling it V1.
- **Medium** = polish and UX quality. Fix before public beta.
- **Low** = nice-to-have. Fix before V2.

Each item has:

- **What it is** — one sentence
- **Where it is** — exact file + line reference
- **Why it matters** — consequence of not fixing
- **How to fix it** — specific, actionable

---

## PART 0 — Critical Bugs (Fix Before Any Launch)

These are not features. These are things that will fail in production.

---

### [CRITICAL-01] Cache key ignores runtime variables — explanation cache returns wrong answer

**What:** The explanation cache key is built from `code[:200] + line_number + line_content[:50]` but ignores `locals_json` (the actual variable state). Two identical lines with different variable states return the same cached explanation.

**Where:** `backend/app/services/llm_router.py` lines 57–67

```python
# CURRENT (BROKEN) — locals_dict is accepted but never used in the key
def make_cache_key(code: str, line_number: int, line_content: str) -> str:
    payload = json.dumps({
        "code": code[:200],
        "ln": line_number,
        "lc": line_content[:50],
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()
```

**Why it matters:** User A runs a list comprehension. At step 4, variables are `{items: [1,2,3], result: [2,4]}`. User B runs the same code with `{items: [], result: []}`. Both see the same cached explanation because the cache key is the same. The explanation will be wrong for one of them.

**How to fix it:** Include locals in the cache key, but hash it to avoid key bloat:

```python
def make_cache_key(code: str, line_number: int, line_content: str, locals_dict: dict) -> str:
    locals_hash = hashlib.sha256(
        json.dumps(locals_dict, sort_keys=True).encode()
    ).hexdigest()[:16]  # first 16 chars is enough for dedup
    payload = json.dumps({
        "code": code[:200],
        "ln": line_number,
        "lc": line_content[:50],
        "lv": locals_hash,  # variable-state fingerprint
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()
```

Also update the `stream_explain` signature to use locals in the key:

```python
# line 102 — also pass locals_dict
cache_key = make_cache_key(code, line_number, line_content, locals_dict)
```

And update the call at line 86:

```python
async for token, provider in llm_router.stream_explain(
    code=code,
    line_number=line_number,
    line_content=line_content,
    locals_dict=locals_dict,  # already here, just use it in the key
    ollama_endpoint=ollama_endpoint,
):
```

---

### [CRITICAL-02] New httpx AsyncClient per request — connection pool exhaustion under load

**What:** Every call to `stream_explain`, `_get_cached`, and `_store_cached` creates a new `httpx.AsyncClient` with `async with httpx.AsyncClient()`. Each client opens new HTTP connections to Supabase and GitHub. Under concurrent load, this exhausts OS socket limits and causes "Too many open files" errors.

**Where:** `backend/app/services/llm_router.py`

- Line 172: `_stream_github_models` creates a new client per call
- Lines 212–221: `_get_cached` creates a new client per cache lookup
- Lines 243–260: `_store_cached` creates a new client per cache store

**Why it matters:** At 50+ concurrent users, the backend starts failing with connection errors. Every explanation request opens 2 new TCP connections (one to GitHub, one to Supabase). At 100 concurrent users making explanation requests = 200 new connections/second = instant failure.

**How to fix it:** Reuse a single client across all requests. The `LLMRouter.__init__` already creates `self._http = httpx.AsyncClient(timeout=30.0)` at line 79. Use it:

```python
# In _stream_github_models — replace the "async with httpx.AsyncClient()" block
# with self._http (the client already initialized in __init__)
response = await self._http.post(
    url,
    json={...},
    headers=headers,
)

# In _get_cached — replace with self._http
resp = await self._http.post(
    f"{settings.supabase_url}/rest/v1/rpc/get_explanation",
    headers={...},
    json={"p_cache_key": cache_key},
)

# In _store_cached — replace with self._http
await self._http.post(
    f"{settings.supabase_url}/rest/v1/explanations",
    headers={...},
    json={...},
)
```

Also fix `llm.py` line 135 — same pattern in `get_dashboard`:

```python
# CURRENT (BROKEN)
async with httpx.AsyncClient(timeout=10.0) as client:
    traces_resp = await client.get(...)

# FIXED — reuse client
async with httpx.AsyncClient(timeout=10.0) as client:
    # Both calls share one connection pool
    traces_resp = await client.get(...)
    cards_resp = await client.get(...)
```

And `review.py` lines 123, 161, 230, 248 — same pattern. Consolidate into single client:

```python
# In get_due_reviews — use one client for both requests
async with httpx.AsyncClient(timeout=10.0) as client:
    cards_resp = await client.get(...)
    # If you need a second call, add it here before the client closes
```

---

### [CRITICAL-03] Pro gate always returns False — anyone can access Pro features for free

**What:** The `_is_pro_user` function in `llm.py` line 130 always returns `False`. The comment even says `# Placeholder — real implementation checks Supabase`. This means the rate limit bypass for Pro users is never active, and the entire Pro tier gating is a no-op.

**Where:** `backend/app/routers/llm.py` lines 127–130

```python
def _is_pro_user(user_id: str | None) -> bool:
    """Check if user is on Pro plan. TODO: integrate with Supabase."""
    # Placeholder — real implementation checks Supabase profiles table
    return False  # ← always false — Pro gating doesn't work
```

**Why it matters:** No one pays $15/month if they get the same features for free. The entire business model depends on this check working.

**How to fix it:** Query the Supabase profiles table:

```python
async def _is_pro_user(user_id: str | None) -> bool:
    if not user_id:
        return False
    from app.config import settings
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
    return False
```

Then update the endpoint to await it (the function is currently sync):

```python
# line 58 — the endpoint is already async, so just await the call
if not await _is_pro_user(user_id):  # add await
```

---

### [CRITICAL-04] Cache write has no RETURNING — silently fails, no error signal

**What:** `_store_cached` sends a POST to Supabase with `Prefer: return=minimal`. This means Supabase inserts the row but returns an empty body. If the insert fails (e.g., column doesn't exist, RLS blocks it), the error is swallowed by the except block at line 261.

**Where:** `backend/app/services/llm_router.py` lines 243–260

```python
# CURRENT — no verification that insert succeeded
await client.post(
    f"{settings.supabase_url}/rest/v1/explanations",
    headers={
        ...
        "Prefer": "return=minimal",  # returns empty body on success
    },
    json={...},
)
# except: logs warning but does nothing — user gets explanation with no error
```

**Why it matters:** If the insert fails silently, explanations are never cached. Every subsequent request hits the LLM again. At scale, this means unlimited free explanations because the cache is never written.

**How to fix it:** Use `Prefer: return=representation` and verify:

```python
resp = await self._http.post(
    f"{settings.supabase_url}/rest/v1/explanations",
    headers={
        "Authorization": f"Bearer {settings.supabase_service_key}",
        "apikey": settings.supabase_service_key,
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
    logger.warning("cache_store_failed", extra={
        "error": f"status={resp.status_code}, body={resp.text[:200]}"
    })
```

Also: the stored explanation is missing `trace_id` and `line_number`. This needs to be added to the call:

```python
# Get trace_id from the current trace context if available
json={
    "cache_key": cache_key,
    "explanation_text": text,
    "model_used": provider_used,
    "model_name": model_name,
    "cached": True,
    # These fields exist in the schema but aren't being stored:
    # "trace_id": trace_id,       # ← add when context is available
    # "line_number": line_number,  # ← add when context is available
},
```

Note: For anonymous cache hits (where there's no trace_id), `trace_id` should be nullable. Verify the schema allows this, or store with a placeholder UUID.

---

### [CRITICAL-05] Debug log writes to disk in production — data leak + crash risk

**What:** `traces.py` and `auth.py` write structured debug logs to `.log` files on disk. These files accumulate indefinitely, grow without bound, and contain sensitive data (user IDs, authorization tokens).

**Where:**

- `backend/app/routers/traces.py` lines 179–198 (save_trace) and lines 264–286 (list_traces)
- `backend/app/routers/auth.py` lines 12–28

```python
# Example from traces.py save_trace:
DEBUG_LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "debug-save.log")
def write_debug_log(hid, msg, data):
    with open(DEBUG_LOG_PATH, "a") as f:  # ← appends forever, no rotation
        f.write(json.dumps(log_entry) + "\n")
```

The auth debug log writes token prefixes (`token_prefix: token[:20]`) to disk — a data handling risk.

**Why it matters:** Tokens written to disk logs can be recovered. Log files growing unbounded can fill the disk and crash the server. These are debug tools left in production code.

**How to fix it:** Remove all `write_debug_log` calls and the `DEBUG_LOG_PATH` constants. Replace with structured logging only:

```python
# Remove all write_debug_log() calls entirely
# Replace with logger.info / logger.warning / logger.error

logger.info("save_trace_called", extra={
    "location": "traces.py:save_trace",
    "has_auth": authorization is not None,
})
```

Do the same for auth.py. Delete all `debug-*.log` files in `backend/`.

---

### [CRITICAL-06] Explanations stored without trace_id — orphaned from their context

**What:** `_store_cached` stores explanations with only `cache_key`, `explanation_text`, `model_used`, `model_name`, and `cached`. It does not store `trace_id` or `line_number`. The `explanations` table has these columns, but the store call omits them.

**Where:** `backend/app/services/llm_router.py` lines 243–260

**Why it matters:** Cannot associate explanations with specific traces. Cannot show users "your past explanations" in the dashboard. Cannot analyze which lines/users generate the most confusion. Cannot delete explanations when a trace is deleted (CASCADE won't work).

**How to fix it:** Pass trace context through the call chain and store it:

```python
# In llm_router.py — update stream_explain signature
async def stream_explain(
    self,
    code: str,
    line_number: int,
    line_content: str,
    locals_dict: dict,
    ollama_endpoint: str | None = None,
    trace_id: str | None = None,  # ← add
) -> AsyncGenerator[tuple[str, LLMProvider], None]:

# In _store_cached — add trace_id
await self._http.post(
    f"{settings.supabase_url}/rest/v1/explanations",
    headers={...},
    json={
        "cache_key": cache_key,
        "explanation_text": text,
        "model_used": provider_used,
        "model_name": model_name,
        "cached": True,
        "trace_id": trace_id,        # ← add
        "line_number": line_number, # ← add
    },
)

# In llm.py — pass trace_id from the request context
async for token, provider in llm_router.stream_explain(
    code=code,
    line_number=line_number,
    line_content=line_content,
    locals_dict=locals_dict,
    ollama_endpoint=ollama_endpoint,
    trace_id=request_state.trace_id,  # ← add (extract from auth/session)
):
```

For anonymous users, `trace_id` should be nullable (handled by the schema since it's UUID — can be NULL).

---

## PART 0.5 — Test Coverage (Write Alongside Each Fix)

> For every Critical and High item, write a test BEFORE fixing the code. The test should fail on the broken code and pass on the fix. This prevents regressions and verifies the fix actually works.


| Fix           | Test to write first                                                                          |
| ------------- | -------------------------------------------------------------------------------------------- |
| [CRITICAL-01] | Assert `make_cache_key(a, 1, "x=1", {"x": 1})` ≠ `make_cache_key(a, 1, "x=1", {"x": 2})`     |
| [CRITICAL-02] | Load test: 100 concurrent explanation requests. Assert zero "Too many open files" errors     |
| [CRITICAL-03] | Mock Supabase returning `plan='pro'`. Assert `_is_pro_user` returns `True`                   |
| [CRITICAL-04] | Mock Supabase returning 500 on insert. Assert error is logged, not swallowed                 |
| [HIGH-01]     | Send `"now()"` string. Verify `last_reviewed_at` is an ISO timestamp, not the literal string |
| [HIGH-02]     | Seed 3 cards reviewed on 3 consecutive days. Assert streak = 3                               |
| [HIGH-07]     | Free user at 50 traces. Assert 402 response with `FREE_LIMIT_REACHED` code                   |


Add to `backend/tests/unit/` and `backend/tests/integration/`. Run `pytest` in CI before any merge.

---

## PART 1 — High-Priority (Fix Before V1 Launch)

---

### [HIGH-01] `last_reviewed_at` uses string `"now()"` instead of SQL `now()`

**What:** `review.py` line 263 sends `"now()"` as a string literal in the JSON body. Supabase interprets this as the string "now()", not the SQL function `now()`.

**Where:** `backend/app/routers/review.py` line 263

```python
"last_reviewed_at": "now()",  # ← wrong: Supabase sees string "now()", not timestamp
```

**Why it matters:** The `last_reviewed_at` field is always the string "now()" instead of the actual timestamp. Streak calculations that rely on this field will be wrong.

**How to fix it:** Either use the  `Prefer: return=representation` + `now()` in a computed column, or send the actual timestamp from Python:

```python
from datetime import datetime, timezone
"last_reviewed_at": datetime.now(timezone.utc).isoformat(),
```

---

### [HIGH-02] Streak calculation is wrong — returns card count, not streak

**What:** `review.py` line 141 sets `streak = len(cards)` (number of due cards). This is not a streak — it's the number of reviews due today. A user with 0 due cards has streak 0, even if they reviewed every day for 30 days.

**Where:** `backend/app/routers/review.py` line 141

```python
streak = len(cards)  # ← wrong: this is card count, not consecutive days
```

**Why it matters:** The streak counter is a core retention mechanic (US-07). If it's always wrong, users don't see their progress and the gamification fails.

**How to fix it:** Calculate streak by counting consecutive days with at least one completed review, working backwards from today:

```python
async def _calculate_streak(user_id: str, settings) -> int:
    """Count consecutive days with at least 1 completed review."""
    import httpx
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/review_cards",
            params={
                "user_id": f"eq.{user_id}",
                "select": "last_reviewed_at",
                "order": "last_reviewed_at.desc",
                "limit": "100",
            },
            headers={
                "Authorization": f"Bearer {settings.supabase_service_key}",
                "apikey": settings.supabase_service_key,
            },
        )
    
    if resp.status_code != 200:
        return 0
    
    cards = resp.json()
    from datetime import date, timedelta
    
    streak = 0
    check_date = date.today()
    
    # Group by date
    reviewed_dates = set()
    for card in cards:
        if card.get("last_reviewed_at"):
            d = card["last_reviewed_at"][:10]  # YYYY-MM-DD
            reviewed_dates.add(d)
    
    while True:
        date_str = check_date.isoformat()
        if date_str in reviewed_dates:
            streak += 1
            check_date -= timedelta(days=1)
        else:
            break
    
    return streak
```

Then replace `streak = len(cards)` in `get_due_reviews` with `streak = await _calculate_streak(user_id, settings)`.

---

### [HIGH-03] Profiles endpoints return placeholders — never read from Supabase

**What:** Both `get_profile` (line 25) and `update_profile` (line 69) return hardcoded placeholders. The comments say `# TODO: Fetch from Supabase using token`.

**Where:** `backend/app/routers/profiles.py` lines 24–31 and lines 69–74

**Why it matters:** User experience level, AI tool usage, and plan status are all hardcoded. Pro users see themselves as "free" in the dashboard. Profile settings never persist.

**How to fix it:** Implement real Supabase reads/writes. This is the same pattern used in `traces.py` and `review.py`:

```python
# In get_profile:
async with httpx.AsyncClient(timeout=10.0) as client:
    resp = await client.get(
        f"{settings.supabase_url}/rest/v1/profiles",
        params={"user_id": f"eq.{user_id}", "select": "*"},
        headers={
            "Authorization": f"Bearer {settings.supabase_service_key}",
            "apikey": settings.supabase_service_key,
        },
    )
    profiles = resp.json() if resp.status_code == 200 else []
    if not profiles:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profiles[0]
```

---

### [HIGH-04] LLM provider order is wrong — GitHub Models is primary, should be Ollama Cloud

**What:** The SPEC says Ollama Cloud is primary (free, zero setup), GitHub Models is fallback. The PRD says "Ollama Cloud primary / Claude fallback." The code has GitHub Models as the only provider.

**Where:** `backend/app/services/llm_router.py` lines 122–123 and line 27

```python
# CURRENT — GitHub is the only provider
if settings.github_models_pat:
    providers_to_try.append((LLMProvider.GITHUB_MODELS, "github-github_models", cache_key))

# Line 27 — only GITHUB_MODELS enum exists
class LLMProvider(Enum):
    GITHUB_MODELS = "github_models"
```

**Why it matters:** Ollama Cloud is free and designed for this use case. GitHub Models requires a PAT. If GitHub changes their free tier (which they just restructured), explanations stop working for all users.

**How to fix it:** Add Ollama Cloud as the primary provider, GitHub as fallback:

```python
class LLMProvider(Enum):
    OLLAMA_CLOUD = "ollama_cloud"
    GITHUB_MODELS = "github_models"

# In stream_explain — try Ollama Cloud first:
providers_to_try = []

# 1. Ollama Cloud (primary, free)
if settings.ollama_cloud_url:
    providers_to_try.append((LLMProvider.OLLAMA_CLOUD, settings.ollama_cloud_url, cache_key))

# 2. GitHub Models (fallback)
if settings.github_models_pat:
    providers_to_try.append((LLMProvider.GITHUB_MODELS, "github_models", cache_key))

# Add _stream_ollama_cloud method:
async def _stream_ollama_cloud(self, prompt: str, cache_key: str) -> AsyncGenerator[str, None]:
    """Stream from Ollama Cloud API."""
    url = f"{settings.ollama_cloud_url}/chat"
    async with self._http.post(url, json={...}) as resp:  # reuse self._http
        async for line in resp.aiter_lines():
            if line:
                data = json.loads(line)
                if "content" in data.get("message", {}):
                    yield data["message"]["content"]
```

Note: The config.py already has `ollama_cloud_url` (line 21) but it's not used anywhere.

---

### [HIGH-05] No GitHub PAT validation at startup — silent failure on missing credentials

**What:** `main.py` checks if `github_models_pat` is set and logs a warning. But Ollama Cloud (the primary provider) has no such check. If all providers fail, users get an unhelpful "No AI provider is available" message with no actionable guidance.

**Where:** `backend/app/main.py` lines 14–18

**Why it matters:** New users deploy CodeScope and get broken explanations with no idea why. The error message tells them to set GITHUB_PAT, but if Ollama Cloud is primary, they should set the Ollama endpoint instead.

**How to fix it:** Validate at least one provider is configured at startup:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.config import settings
    
    # Check at least one provider is configured
    has_ollama = bool(settings.ollama_cloud_url)
    has_github = bool(settings.github_models_pat)
    
    if not has_ollama and not has_github:
        import logging
        logging.error(
            "No LLM provider configured. Set OLLAMA_CLOUD_URL or GITHUB_MODELS_PAT. "
            "AI explanations will not work."
        )
    
    yield
```

---

### [HIGH-06] Health endpoint is liveness-only — no readiness check

**What:** `/health` returns `{"status": "ok"}` unconditionally. It doesn't verify database connectivity, Redis availability, or LLM provider reachability.

**Where:** `backend/app/main.py` lines 61–64

**Why it matters:** Railway's liveness probe will say "healthy" even if Supabase is down. Traffic will be routed to a dead backend. Users will get confusing 500 errors instead of a fast 503 from the load balancer.

**How to fix it:**

```python
@app.get("/health")
async def health():
    """Liveness + readiness check."""
    from app.config import settings
    import httpx
    
    checks = {"status": "ok", "checks": {}}
    healthy = True
    
    # Check Supabase
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
        checks["checks"]["supabase"] = f"error:{e}"
        healthy = False
    
    checks["status"] = "ok" if healthy else "degraded"
    status_code = 200 if healthy else 503
    from fastapi.responses import JSONResponse
    return JSONResponse(content=checks, status_code=status_code)
```

---

### [HIGH-07] Rate limit enforcement doesn't distinguish free vs Pro tier limits

**What:** The PRD specifies 20 "why" questions per hour on the free tier, and unlimited for Pro. The code at `llm.py` lines 57–76 checks rate limits only for unauthenticated or non-Pro users — but since `_is_pro_user` always returns False, ALL users are rate-limited. Meanwhile, the `rate_limit_per_hour` config is 20 (line 28 of config.py), but the PRD spec says 20/hour for free tier, not 50/month.

**Where:** `backend/app/routers/llm.py` lines 57–76; `backend/app/config.py` line 28

**Also:** The PRD freemium gate says 50 traces/month for free (soft limit, prompts upgrade), but the code has no trace-count enforcement anywhere. Users get unlimited free traces.

**Why it matters:** The freemium model is not enforced. Users get all features for free indefinitely. Conversion to Pro never happens organically.

**How to fix it:** Implement trace-count tracking:

```python
# In traces.py — check user's trace count before allowing trace
async def _get_trace_count(user_id: str) -> int:
    settings = Settings()
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/traces",
            params={
                "user_id": f"eq.{user_id}",
                "select": "id",
                # Filter by current month (created_at >= first of month)
            },
            headers={...},
        )
        return len(resp.json()) if resp.status_code == 200 else 0

# In run_trace endpoint — check count before proceeding
user = await get_current_user(authorization) if authorization else None
is_pro = await _is_pro_user(user.get("id")) if user else False

if not is_pro:
    count = await _get_trace_count(user["id"])
    FREE_TRACE_LIMIT = 50
    if count >= FREE_TRACE_LIMIT:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "FREE_LIMIT_REACHED",
                "message": f"You've used your {FREE_TRACE_LIMIT} free traces this month.",
                "upgrade_url": "/upgrade",
            }
        )
```

Note: The PRD specifies 50 traces/month soft limit (not server-blocked), so the above should probably return a warning modal rather than blocking. But at minimum, the count should be tracked.

---

### [HIGH-08] Missing README — no setup instructions for new contributors

**What:** There is no `README.md` in the project root or `backend/` directory. A new developer cannot set up CodeScope without asking the original author.

**Why it matters:** If the thesis author gets hit by a bus, no one can continue the project. For a thesis that should demonstrate engineering rigor, this is a significant gap.

**How to fix it:** Create `README.md` in the project root covering:

1. What CodeScope is (one paragraph)
2. Architecture overview (2-3 sentences)
3. Prerequisites (Python 3.10+, Node 18+, Supabase account, Railway account)
4. Local setup (step-by-step with `.env` template)
5. Running the backend (`cd backend && .venv\Scripts\activate && uvicorn app.main:app --reload`)
6. Running the frontend (`cd frontend && npm run dev`)
7. Running tests (`pytest`)
8. Deployment (Railway + Vercel)
9. Key environment variables
10. Common issues and solutions

Create `backend/.env.example`:

```bash
# Required for AI explanations (GitHub Models)
GITHUB_MODELS_PAT=your_github_pat_here

# Supabase (get from supabase.com project settings)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key_here

# Optional: Redis for distributed rate limiting
REDIS_ENABLED=false
REDIS_URL=redis://localhost:6379

# Logging
LOG_LEVEL=INFO

# Rate limiting
RATE_LIMIT_PER_HOUR=20
RATE_LIMIT_WINDOW_SECONDS=3600
```

---

## PART 2 — Medium Priority (Fix Before Public Beta)

---

### [MEDIUM-01] Explanation rating is implemented in backend but never shown in frontend

**What:** The `explanations.human_rating` column exists, the backend stores ratings (REQ-AI-02), and the schema supports 1–5 ratings. But the frontend `ExplanationPanel` has no rating widget.

**Where:** `frontend/components/llm/ExplanationPanel.tsx` — needs a 5-star or Thumbs up/down widget after streaming completes.

**Why it matters:** The evaluation criteria for the thesis includes "mean helpfulness rating by pattern category." Without the frontend widget, there's no data to evaluate explanation quality. This is a thesis evaluation requirement, not just a nice-to-have.

**How to fix it:** Add rating widget to `ExplanationPanel`:

```tsx
// After SSE stream completes, show rating widget:
const [rating, setRating] = useState<number | null>(null);

if (isComplete && !rating) {
  return (
    <div className="rating-widget">
      <p>Was this explanation helpful?</p>
      {[1,2,3,4,5].map(n => (
        <button key={n} onClick={() => submitRating(n)}>★</button>
      ))}
    </div>
  );
}
```

Then `POST /api/explanations/{id}/rate` with `{rating: number}`. Store in `explanations.human_rating`.

---

### [MEDIUM-02] Branch detection is incomplete — all branches marked as "taken"

**What:** `tracer.py` line 154 marks ALL if statements as `{"taken": True}` regardless of which branch actually fired. The logic doesn't check the actual condition result.

**Where:** `backend/tracer/tracer.py` lines 151–155

```python
# CURRENT — always True, doesn't check actual condition result
if isinstance(node, ast.If):
    branches_taken["if"] = {"taken": True, "line": line_no, "iteration": 0}
```

**Why it matters:** The spec says "branch detection is implemented in v1" (REQ-CORE-02). The "aha moment" for learners is seeing which branch fired and why. If all branches always show as taken, the feature provides no value.

**How to fix it:** Evaluate the condition at runtime to determine which branch fired. At the point where `if` is about to execute, evaluate the test expression:

```python
# In tracer_callback — before executing the branch body, detect which branch fires
# This requires evaluating the condition in the current namespace
if line_no in jump_map:
    for node in jump_map[line_no]:
        if isinstance(node, ast.If):
            # Evaluate the condition in the namespace
            try:
                import ast
                # Reconstruct the condition expression
                condition_expr = ast.unparse(node.test)
                # Evaluate in the current frame's namespace
                result = eval(condition_expr, namespace)
                branches_taken["if"] = {
                    "taken": bool(result),
                    "line": line_no,
                    "branch": "then" if result else "else",
                    "condition": condition_expr,
                }
            except Exception:
                branches_taken["if"] = {"taken": None, "line": line_no}
```

Note: `ast.unparse()` requires Python 3.9+. Add a version guard before using it:

```python
import sys
if sys.version_info >= (3, 9):
    condition_expr = ast.unparse(node.test)
else:
    # Fallback: use a string representation of the AST node
    condition_expr = f"<condition on line {node.test.lineno}>"
```

---

### [MEDIUM-03] Cache hit returns explanation text but never stores it back to the caller correctly

**What:** When a cache hit occurs (line 104–108), the code yields the cached text as tokens. But the response format mixes raw text with SSE tokens — the frontend gets a stream where the first "token" is the entire cached explanation as one blob.

**Where:** `backend/app/services/llm_router.py` lines 104–108

```python
# CURRENT — yields entire cached text as single token
if cached_text:
    logger.info("explanation_cache_hit", extra={"cache_key": cache_key})
    yield cached_text, LLMProvider.GITHUB_MODELS  # ← whole string as one token
    yield "__done__", LLMProvider.GITHUB_MODELS
    return
```

**Why it matters:** The frontend SSE parser expects individual tokens streamed word-by-word for the streaming animation. A cache hit delivers the entire explanation as one giant token, causing a visual glitch (the explanation appears instantly instead of streaming).

**How to fix it:** Stream the cached text word-by-word like the non-cached path:

```python
if cached_text:
    logger.info("explanation_cache_hit", extra={"cache_key": cache_key})
    for word in cached_text.split():
        yield word + " ", LLMProvider.GITHUB_MODELS
    yield "__done__", LLMProvider.GITHUB_MODELS
    return
```

---

### [MEDIUM-04] 14 debug print statements in llm_router.py — leaks to production logs

**What:** `llm_router.py` has `print("DEBUG: ...")` calls at lines 99, 119 that write to stdout. These will appear in Railway logs.

**Where:** `backend/app/services/llm_router.py` lines 99, 119

```python
print("DEBUG: stream_explain called!", flush=True)
print(f"DEBUG: settings.github_models_pat = ...", flush=True)
```

**Why it matters:** Debug output in production logs makes debugging real issues harder. If Railway log retention is enabled, these messages accumulate and cost money.

**How to fix it:** Replace with `logger.debug()` calls:

```python
logger.debug("stream_explain_called")
logger.debug("github_pat_available", extra={"has_pat": bool(settings.github_models_pat)})
```

---

### [MEDIUM-05] No `review_cards` index on `user_id + next_review_date` — slow dashboard at scale

**What:** The `review_cards` table has separate indexes on `user_id` (line 66) and `next_review_date` (line 67), but no composite index on `(user_id, next_review_date)`. The `get_due_reviews` query filters by both simultaneously.

**Where:** `backend/migrations/V001__initial_schema.sql` — indexes section

**Why it matters:** With 10K+ users and 100K+ review cards, the dashboard query will do a full table scan filtered by user_id, then another filter by date. At 1,000 concurrent users on the dashboard, this will be slow.

**How to fix it:** Add composite index:

```sql
CREATE INDEX IF NOT EXISTS idx_review_cards_user_next
ON review_cards(user_id, next_review_date);
```

---

### [MEDIUM-06] `/api/traces` (save) silently drops `language`, `concept_tags`, `is_public` fields

**What:** `SaveTraceRequest` accepts `language`, `concept_tags`, and `is_public` (lines 167–171), but `traces.py` lines 222–226 only sends `user_id`, `code`, and `share_token` to Supabase. The other fields are accepted and ignored.

**Where:** `backend/app/routers/traces.py` lines 222–226

```python
trace_data = {
    "user_id": user_id,
    "code": req.code,
    "share_token": share_token,
    # language, concept_tags, is_public — silently dropped
}
```

**Why it matters:** `concept_tags` are needed for SR categorization (REQ-TRACK-04). `is_public` is needed for shared traces. Without these, users can't filter their review queue by concept or share traces publicly.

**How to fix it:**

```python
trace_data = {
    "user_id": user_id,
    "code": req.code,
    "language": req.language,
    "concept_tags": req.concept_tags if req.concept_tags else [],
    "is_public": req.is_public,
    "share_token": share_token,
}
```

---

### [MEDIUM-07] Frontend has `useTrace.ts` import in tracer page but file doesn't exist

**What:** The tracer page (`frontend/app/tracer/page.tsx`) uses local state for step management instead of the `useTrace` hook. The hook file `frontend/hooks/useTrace.ts` exists but is not actually imported or used by the page.

**Where:** `frontend/app/tracer/page.tsx` — manages step state manually with `useState` (lines 58, 128–147)

**Why it matters:** The `useTrace` hook is well-implemented (rAF animation, tab visibility handling, keyboard shortcuts). The page doesn't use it, meaning:

- Tab visibility handling (pause when tab is backgrounded) doesn't work
- Keyboard shortcuts (Space, Arrow keys) don't work
- The animation quality depends on the manual `setInterval`-style logic in `handleTrace`

**How to fix it:** Replace the manual step management in `page.tsx` with the `useTrace` hook:

```tsx
// In page.tsx, replace useState-based step management:
const [currentStep, setCurrentStep] = useState(0);
const [isLoading, setIsLoading] = useState(false);

// With:
const {
  currentStep,
  playbackState,
  speed,
  play, pause, togglePlayPause,
  stepForward, stepBackward,
  jumpToStep, setSpeed, reset,
} = useTrace({ steps: traceResult?.steps ?? [] });
```

Pass `playbackState` and `speed` to `AnimationControls`. Pass `play`, `pause`, `stepForward`, `stepBackward`, `jumpToStep`, `setSpeed` to control the hook.

---

### [MEDIUM-08] Dashboard streak is hardcoded to 0

**What:** `traces.py` line 159 hardcodes `streak: 0`. Even after fixing the streak calculation in `review.py`, the dashboard won't show correct streaks.

**Where:** `backend/app/routers/traces.py` line 159

```python
return DashboardResponse(
    traces=traces,
    due_cards=[{**c, "due": True} for c in due_cards],
    streak=0,  # ← always zero
    total_traces=len(traces),
)
```

**How to fix it:** After implementing `_calculate_streak` in `review.py`, import and reuse it:

```python
from app.routers.review import _calculate_streak

# In get_dashboard:
streak = await _calculate_streak(user_id, settings)
```

---

### [MEDIUM-09] No landing page — direct to `/tracer` with no context

**What:** The root `page.tsx` (`frontend/app/page.tsx`) is nearly empty. Users who visit the root URL see nothing that explains what CodeScope is or why they should use it.

**Where:** `frontend/app/page.tsx`

**Why it matters:** Users who find CodeScope from a search result or shared link need to understand the value proposition in < 30 seconds. Without a landing page, they'll bounce immediately.

**How to fix it:** Create a compelling landing page at `/` covering:

1. Hero: "Understand the code you ship" + 30-second demo video (or animated GIF of the tracer)
2. Problem: The AI comprehension gap (cite the 17% statistic)
3. How it works: 3-step visual (paste → trace → understand)
4. Social proof: "Used by X learners" or testimonials
5. CTA: "Start for free" → `/tracer`
6. Pricing: Free vs Pro comparison table

This is also a thesis showcase opportunity — the landing page should feel like a real product, not a student project.

---

### [MEDIUM-10] `ollama_endpoint` in profiles is never actually used

**What:** The `profiles` table has `ollama_endpoint` (V001__initial_schema.sql line 13). The `update_profile` endpoint accepts it. But `llm_router.py` never reads this field to route requests.

**Where:** `llm_router.py` line 90 — `ollama_endpoint` parameter is accepted but ignored

```python
async def stream_explain(
    ...
    ollama_endpoint: str | None = None,  # ← accepted
):
    # Never used — all requests go to the configured URL
```

**Why it matters:** The SPEC says users can set `localhost:11434` for full local inference. This feature doesn't work. Users who want privacy-respecting local explanations can't use it.

**How to fix it:** Use `ollama_endpoint` if provided:

```python
# In stream_explain — if user provided a custom endpoint, use it for Ollama Cloud
endpoint = ollama_endpoint or settings.ollama_cloud_url
```

---

### [MEDIUM-11] Confirmed safe — no action required

**What:** The shared trace endpoint (`traces.py` line 327) checks `is_public=true` in the Supabase query. This is not a security risk because the RLS policy on `traces` enforces `is_public=true` at the database level — the query param is defense-in-depth, not the primary gate.

**Where:** `backend/app/routers/traces.py` lines 332–340

**Why it matters:** Not a risk. The RLS policy (`backend/migrations/V001__initial_schema.sql` line 84) reads: `CREATE POLICY "public_traces" ON traces FOR SELECT USING (is_public = true)` — non-public traces cannot be returned regardless of query parameters.

**How to fix it:** No change needed. This item is informational only.

---

## PART 3 — Thesis Evaluation (Must-Have for Defense)

---

### [THESIS-01] Comprehension retention study — not yet conducted

**What:** SPEC.md Section 6 requires a comprehension retention study comparing CodeScope users vs. control group. This is the primary empirical evaluation for the thesis committee.

**Where:** Not started

**Why it matters:** An engineering thesis requires "something evaluated empirically." Without this study, the thesis is a product demo, not an evaluated system.

**How to fix it:** Per SPEC.md guidance, this does not require formal IRB. Implement as:

1. Create 10 Python code patterns (5 simple, 5 complex AI-generated)
2. Recruit 20-30 participants (CS students, split into test/control)
3. Test group: use CodeScope tracer + explanation on patterns
4. Control group: read the same code explanations from ChatGPT
5. 2-week follow-up quiz: "Explain what this code does" — score each response
6. Target: +30% comprehension vs. control

Track via a lightweight study flag in the database (anonymous, consent-required).

---

### [THESIS-02] Synthetic benchmark for static analysis — not yet run

**What:** SPEC.md Section 6 requires a synthetic benchmark of 50 Python snippets with known bugs to measure static analysis precision (>85% target).

**Where:** Not started

**Why it matters:** Without this, the static analysis quality is anecdotal. The benchmark proves the analysis layer works.

**How to fix it:** Create `backend/tests/benchmark/test_static_analysis.py`:

```python
import pytest
from analyzers.static_analysis import analyze_code

# Each snippet: (code: str, expected_patterns: list[str], has_bug: bool)
# expected_patterns = bug patterns that SHOULD be detected
# has_bug = whether this snippet actually contains a bug
SYNTHETIC_SNIPPETS = [
    # (code, patterns_that_should_be_flagged, snippet_has_bug)
    ("def foo(x=None): pass", [], False),  # None is safe for mutable default
    ("def bar(items=[]): pass", ["mutable_default"], True),
    ("if data:", ["implicit_truthiness"], True),
    ("requests.get(url)", ["requests_no_timeout"], True),
    # ... 45 more, mix of buggy and clean snippets
]

def test_precision_and_recall():
    """
    Precision = TP / (TP + FP)  — of the bugs we flag, how many are real?
    Recall = TP / (TP + FN)      — of the bugs that exist, how many did we catch?
    """
    tp = fp = fn = 0

    for code, expected_patterns, has_bug in SYNTHETIC_SNIPPETS:
        found_patterns = {a.pattern_id for a in analyze_code(code)}

        if has_bug:
            # Bug exists in this snippet
            for bug in expected_patterns:
                if bug in found_patterns:
                    tp += 1
                else:
                    fn += 1  # missed a known bug
        else:
            # No bug expected — any flag is a false positive
            for bug in found_patterns:
                fp += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0

    assert precision > 0.85, f"Static analysis precision {precision:.1%} < 85% target"
    assert recall > 0.70, f"Static analysis recall {recall:.1%} < 70% target"
```

---

### [THESIS-03] Success metrics not tracked — no analytics instrumentation

**What:** The PRD defines success metrics (trace completion rate ≥ 80%, review queue retention ≥ 30%, return visit rate ≥ 40%), but there's no code to actually track these.

**Where:** No analytics instrumentation anywhere

**Why it matters:** Without tracking, there's no evidence the product is working. For a thesis, this is a gap. For a real product, it's a launch blind.

**How to fix it:** Add lightweight Supabase event tracking (no PII):

```python
# In traces.py — log trace completion
logger.info("trace_completed", extra={
    "trace_id": trace_id,
    "user_id": user_id,
    "total_steps": total_steps,
    "duration_ms": duration_ms,
})

# In review.py — log review submission
logger.info("review_completed", extra={
    "card_id": card_id,
    "rating": rating,
    "interval_before": interval_before,
    "interval_after": new_interval,
})
```

Then build a lightweight dashboard query to compute metrics from logs.

---

## PART 4 — Low Priority (Fix Before V2)

---

### [LOW-01] `openapi_url` in spec says "localhost" — breaks in production

**What:** `main.py` doesn't set `openapi_url` explicitly. FastAPI defaults to `/openapi.json`. This is fine, but the API docs at `/docs` might show the wrong server URL in production.

**Where:** `backend/app/main.py`

**Impact:** Minor. API docs just show wrong base URL. Doesn't affect functionality.

---

### [LOW-02] Concept tagging uses regex — should use LLM or AST-based detection

**What:** `frontend/app/tracer/page.tsx` lines 41–52 uses simple regex to detect concept tags:

```python
if (/def\s+\w+\(/.test(code)) tags.push("FUNCTION")
if (/for\s/.test(code)) tags.push("LOOP")
```

**Where:** `frontend/app/tracer/page.tsx` lines 41–52

**Impact:** Noisy tags (a function with a loop inside gets both tags, even if the confusion is about the function's closure). Also missed in backend — the `concept_tags` field is accepted but never stored.

**How to fix it:** Use AST-based detection in `backend/analyzers/static_analysis.py`:

```python
def detect_concept_tags(code: str) -> list[str]:
    """Detect AI code pattern categories from AST."""
    tags = []
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.ListComp): tags.append("COMPREHENSION")
        if isinstance(node, (ast.For, ast.While)): tags.append("LOOP")
        if isinstance(node, ast.If): tags.append("CONDITIONAL")
        if isinstance(node, ast.AsyncFunctionDef): tags.append("ASYNC")
        if isinstance(node, ast.Lambda): tags.append("LAMBDA")
        if isinstance(node, ast.Try): tags.append("EXCEPTION")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if len(node.decorator_list) > 0: tags.append("DECORATOR")
    return list(set(tags))  # deduplicate
```

Then call this in `traces.py save_trace` and store the result.

---

### [LOW-03] No dark/light mode — dark-only is fine for MVP but limits accessibility

**What:** No theme toggle exists. Dark-only is standard for developer tools but reduces accessibility for users who prefer light themes.

**Where:** Not implemented

**Impact:** Minor. Out of scope for V1 per PRD.

---

### [LOW-04] No Stripe integration — Pro tier has no payment processing

**What:** The `profiles.stripe_customer_id` column exists but is never populated. There's no `/api/billing/webhook`, no checkout flow, no subscription management.

**Where:** Not implemented anywhere

**Impact:** Product cannot charge money. No business model.

**⚠️ Prerequisite — deploy frontend before Stripe:** Stripe requires HTTPS + a real domain. If CodeScope is still on `localhost:3000`, Stripe checkout will fail. This item depends on [MEDIUM-09] (landing page + frontend deploy). Do not attempt until the frontend is live at a real URL.

**How to fix it:** Full Stripe integration — budget 2-3 days. Requires:

1. Stripe account + API keys
2. `/api/billing/create-checkout-session` endpoint
3. Stripe webhook handler for `checkout.session.completed` and `customer.subscription.deleted`
4. Frontend checkout button that calls the endpoint and redirects to Stripe
5. Update `profiles.stripe_customer_id` and `profiles.plan` on webhook events

Do not attempt before all Critical and High items are resolved.

---

### [LOW-05] No mobile responsiveness — desktop only

**What:** The tracer requires Monaco editor (desktop), but there's no graceful degradation for mobile. The layout breaks on screens < 1024px.

**Where:** CSS in `frontend/app/tracer/page.module.css`

**Impact:** Mobile users get broken experience. Out of scope for V1 per PRD.

---

## Summary: Execute in This Order

```
WEEK 1 — Critical Fixes + Tests (prevents production failures)
  Before fixing anything: write tests for all 6 Critical items (see PART 0.5)
  Verify all 6 tests fail on current code
  [CRITICAL-01] Fix cache key to include locals_dict
  [CRITICAL-02] Reuse httpx AsyncClient across requests (connection pooling)
  [CRITICAL-03] Implement _is_pro_user with real Supabase query
  [CRITICAL-04] Add RETURNING check to cache writes
  [CRITICAL-05] Remove all debug log writes to disk files
  [CRITICAL-06] Store trace_id and line_number in explanations table
  Verify all 6 tests pass on fixed code

WEEK 2 — High-Priority Features (makes V1 actually work)
  [HIGH-01] Fix last_reviewed_at to use real timestamp
  [HIGH-02] Implement real streak calculation
  [HIGH-03] Connect profiles endpoints to Supabase
  [HIGH-04] Add Ollama Cloud as primary LLM provider (GitHub as fallback)
  [HIGH-05] Validate at startup that at least one LLM provider is configured
  [HIGH-06] Implement proper readiness health check endpoint
  [HIGH-07] Track trace counts and enforce free tier limits

WEEK 3 — Beta Polish (usable by real users)
  [MEDIUM-01] Add explanation rating widget to frontend
  [MEDIUM-02] Fix branch detection to show which branch actually fired
  [MEDIUM-03] Fix cache hit to stream tokens word-by-word
  [MEDIUM-04] Remove debug print statements
  [MEDIUM-05] Add composite index on (user_id, next_review_date)
  [MEDIUM-06] Store concept_tags and is_public when saving traces
  [MEDIUM-07] Wire useTrace hook into tracer page
  [MEDIUM-08] Fix dashboard streak to use real calculation
  [MEDIUM-09] Build landing page
  [MEDIUM-10] Use ollama_endpoint from user profile

WEEK 4 — Thesis Evaluation (required for defense)
  [THESIS-01] Run synthetic static analysis benchmark (50 snippets, >85% precision)
  [THESIS-02] Design comprehension retention study protocol
  [THESIS-03] Add lightweight analytics instrumentation

WEEK 5+ — Nice-to-have
  [LOW-01] Stripe integration
  [LOW-02] LLM-based concept tagging
  [LOW-04] Mobile responsiveness
  [LOW-05] Dark/light mode toggle
```

---

## Quality Gate: 9/10 Criteria

This roadmap reaches 9/10 quality when all of the following are true:

**Critical & High (must pass before any deploy)**

1. All 6 Critical items are deployed to production — verified by running the load test (100 concurrent explanation requests, zero "Too many open files" errors)
2. All 8 High-priority items are confirmed working:
  - `_is_pro_user` returns `True` when Supabase has `plan='pro'`
  - Streak calculation returns correct consecutive-day count (not card count)
  - `ollama_endpoint` from user profile is actually used when routing LLM requests
  - Health endpoint returns 503 when Supabase is unreachable
3. Free tier trace limit is enforced — free user at 50 traces receives a 402 response with `FREE_LIMIT_REACHED`
4. `last_reviewed_at` stores an ISO timestamp, not the string `"now()"`
5. No debug print statements or disk writes in the running service (verified by `grep -r "print(" backend/app/)` returning empty)

**Beta & Medium (must pass before public beta)**

1. Landing page exists at `/` with clear value proposition (even if simple)
2. Synthetic benchmark runs and shows >85% precision AND >70% recall on static analysis
3. Explanation rating widget is in the frontend and collects data in `explanations.human_rating`
4. Branch detection shows which branch fired (not all branches) — verified with a test `if True: x=1 else: x=2` snippet
5. `useTrace` hook is wired into the tracer page — keyboard shortcuts (Space, Arrow keys) work during playback

**Thesis (must be complete before defense)**

1. Comprehension retention study protocol is documented (participants, methodology, target +30% improvement)
2. Analytics instrumentation is logging trace completion, review submission, and explanation ratings to Supabase
3. README.md exists in project root and backend/ with complete setup instructions

**Staging gate (run before every deploy)**

1. `pytest` passes in CI (all unit + integration tests green)
2. Load test passes (100 concurrent users, no connection errors)
3. No `debug-*.log` files in the repository (`git ls-files "debug-*.log"` returns empty)

