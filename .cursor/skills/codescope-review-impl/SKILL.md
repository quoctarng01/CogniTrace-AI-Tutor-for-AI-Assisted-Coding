---
name: codescope-review-impl
description: Implements all phases from FEATURE-REVIEW.md (security fixes, acquisition, foundation, tests, features, polish, reliability). Use when implementing or continuing FEATURE-REVIEW.md. Assumes Phase 1-4 codebase already exists.
---

# CodeScope Review Implementation Skill

Implements the full 7-week roadmap from `FEATURE-REVIEW.md`. Follow each phase in order. Complete every task in a phase before moving to the next.

## Golden Rules

1. **Never skip tasks.** Every task exists because something broke or was missing before.
2. **Never combine tasks.** One task = one exact file change.
3. **Always run verification** after each phase before proceeding.
4. **Always read a file before editing it.** Use the Read tool first.
5. **If a search string does not match**, stop and report — do not guess. The file may have changed.

## Project Paths

| Item | Path |
|------|------|
| Project root | `C:\Users\quoct\codescope\` |
| Backend | `C:\Users\quoct\codescope\backend\` |
| Frontend | `C:\Users\quoct\codescope\frontend\` |
| Feature spec | `C:\Users\quoct\codescope\FEATURE-REVIEW.md` |
| docker-compose | `C:\Users\quoct\codescope\docker-compose.yml` |
| CI workflow | `C:\Users\quoct\codescope\.github\workflows\ci.yml` |

## How to Read This Skill

Each task has this structure:

```
### TASK X-Y: Short Description

**File:** `relative/path/to/file.ext`

**Find** (copy-paste this exact block — must match file byte-for-byte):
```python
code that exists in the file right now
```

**Replace with:**
```python
code that should replace it
```

**Verification command:** `curl ...` or `npm run build` etc.
```

- If **Find** block does not match, STOP and re-read the file.
- If a file has NO matching block, the task may already be done — check and skip if so.
- After completing all tasks in a phase, run the **Phase Verification** at the bottom of that phase section.

---

## PHASE 0 — Critical Security Fixes

> Complete ALL Phase 0 P0 tasks before any other work. They are grouped into one PR for speed.

### TASK 0.1.1: Replace hardcoded secrets in docker-compose.yml

**File:** `docker-compose.yml`

**Find:**

```yaml
environment:
  SUPABASE_ANON_KEY: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  SUPABASE_SERVICE_KEY: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  POSTGRES_PASSWORD: postgres
```

**Replace with:**

```yaml
environment:
  SUPABASE_ANON_KEY: "${SUPABASE_ANON_KEY}"
  SUPABASE_SERVICE_KEY: "${SUPABASE_SERVICE_KEY}"
  POSTGRES_PASSWORD: "${POSTGRES_PASSWORD}"
```

---

### TASK 0.1.2: Add health check to backend service

**File:** `docker-compose.yml`

**Find the `backend` service definition and add after the existing config (before the next service):**

```yaml
services:
  backend:
    # ... existing config ...
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
```

> **Note:** If `restart: unless-stopped` already exists, skip adding it again.

---

### TASK 0.1.3: Add resource limits to all services

**File:** `docker-compose.yml`

**Find each service block (backend, frontend, redis) and add this inside each:**

```yaml
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
```

> Add to ALL 4 services: backend, frontend, redis, postgres. If a service already has `deploy.resources.limits`, skip it.

---

### TASK 0.1.4: Add .env to .gitignore

**File:** `.gitignore` (root of project)

**Find:**

```gitignore
node_modules/
```

**Replace with:**

```gitignore
.env
node_modules/
```

> If `.env` is already in `.gitignore`, skip this task.

---

### TASK 0.2.1: Fix `get_profile_id` function signature

**File:** `backend/app/routers/auth.py`

**Find:**

```python
async def get_profile_id(authorization: str) -> str:
    """
    token: Full Authorization header value (e.g. "Bearer eyJhbG...").
    Returns profile ID or empty string if not found.
    """
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/profiles",
            params={"id": f"eq.{authorization}"},
```

**Replace with:**

```python
async def get_profile_id(token: str) -> str:
    """
    token: JWT string AFTER 'Bearer ' prefix has been stripped.
    Returns profile ID or empty string if not found.
    """
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/profiles",
            params={"id": f"eq.{token}"},
```

---

### TASK 0.2.2: Update traces.py to strip Bearer before calling `get_profile_id`

**File:** `backend/app/routers/traces.py`

**Find:**

```python
profile_id = await get_profile_id(authorization)
```

**Replace with:**

```python
token = authorization.replace("Bearer ", "") if authorization else None
profile_id = await get_profile_id(token) if token else None
```

---

### TASK 0.2.3: Update llm.py to strip Bearer before calling `get_profile_id`

**File:** `backend/app/routers/llm.py`

**Find:**

```python
profile_id = await get_profile_id(authorization)
```

**Replace with:**

```python
token = authorization.replace("Bearer ", "") if authorization else None
profile_id = await get_profile_id(token) if token else None
```

> If this exact pattern does not exist in llm.py, search for `get_profile_id(authorization)` and replace it.

---

### TASK 0.3.1: Fix shared trace authorization bypass

**File:** `backend/app/routers/traces.py`

**Find the `get_shared_trace` endpoint function. Look for the existing implementation that only checks `is_public=true`. Replace the entire function with:**

```python
@router.get("/traces/shared/{share_token}")
async def get_shared_trace(
    share_token: str,
    authorization: str | None = Header(None),
):
    """
    Fetch a trace by share_token.

    If authenticated (owner), returns the trace if:
      - is_public=true  OR
      - user_id matches the authenticated user's profile

    If anonymous, returns only is_public=true traces.
    """
    owner_id = None
    if authorization:
        token = authorization.replace("Bearer ", "")
        owner_id = await get_profile_id(token)

    settings = Settings()

    if owner_id:
        params = {
            "share_token": f"eq.{share_token}",
            "or": f"(is_public.eq.true,user_id.eq.{owner_id})",
            "select": "*",
            "limit": "1",
        }
        headers = {
            "apikey": settings.supabase_service_key,
            "Authorization": f"Bearer {settings.supabase_service_key}",
        }
    else:
        params = {
            "share_token": f"eq.{share_token}",
            "is_public": "eq.true",
            "select": "*",
            "limit": "1",
        }
        headers = {
            "apikey": settings.supabase_service_key,
            "Authorization": f"Bearer {settings.supabase_service_key}",
        }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/traces",
            params=params,
            headers=headers,
        )

    if resp.status_code != 200 or not resp.json():
        raise HTTPException(status_code=404, detail="Trace not found")

    return resp.json()[0]
```

---

### TASK 0.4.1: Remove spoofable `user_id` query param from LLM endpoint

**File:** `backend/app/routers/llm.py`

**Find the `explain_stream` endpoint signature:**

```python
@router.get("/explain/stream")
async def explain_stream(
    code: str = Query(...),
    line: int = Query(...),
    user_id: Optional[str] = Query(None),  # ← REMOVE THIS
    authorization: Optional[str] = Header(None),
):
```

**Replace with:**

```python
@router.get("/explain/stream")
async def explain_stream(
    code: str = Query(...),
    line: int = Query(...),
    authorization: Optional[str] = Header(None),
):
```

Then find:

```python
effective_user_id = user_id  # ← BUG: uses spoofable value
```

**Replace with:**

```python
    # Extract user_id ONLY from auth header — never from query params
    effective_user_id = None
    if authorization:
        token = authorization.replace("Bearer ", "")
        effective_user_id = await get_profile_id(token)
```

---

### TASK 0.5.1: Add configurable CORS origins

**File:** `backend/app/config.py`

**Find the Settings class and add this field:**

```python
    allowed_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:3001"],
    )
```

**Add a comment above it:**

```python
    # Load from env: ALLOWED_ORIGINS=http://localhost:3000,https://codescope.vercel.app
```

> If `allowed_origins` already exists in config.py, skip this task.

---

### TASK 0.5.2: Update CORS in main.py

**File:** `backend/app/main.py`

**Find:**

```python
allow_origins=settings.allowed_origins,
```

> If this line already exists and matches, skip. If it uses a hardcoded list, replace the hardcoded list with `settings.allowed_origins`.

---

### TASK 0.6.1: Add rate limiting to `/api/traces/run`

**File:** `backend/app/routers/traces.py`

**Find the imports at the top of the file:**

```python
from fastapi import APIRouter, HTTPException, Header, Query, Body
```

**Replace with:**

```python
from fastapi import APIRouter, HTTPException, Header, Query, Body, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
```

Then find the `POST /traces/run` endpoint decorator:

```python
@router.post("/traces/run")
async def run_trace(req: TraceRequest):
```

**Replace with:**

```python
@router.post("/traces/run", dependencies=[Depends(limiter.limit("30/minute"))])
async def run_trace(req: TraceRequest):
```

> If `dependencies` already has a `[Depends(...)]`, ADD to the list instead of replacing.

---

### TASK 0.7.1: Add rate limiting to auth routes

**File:** `backend/app/routers/auth.py`

**Find the imports at the top of the file:**

```python
from fastapi import APIRouter, HTTPException, Body
```

**Replace with:**

```python
from fastapi import APIRouter, HTTPException, Body, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
```

Then add `dependencies=[Depends(limiter.limit("5/minute"))]` to each auth route decorator. For example:

```python
@router.post("/login", dependencies=[Depends(limiter.limit("5/minute"))])
async def login(...):
```

> Add this to ALL routes in auth.py (login, signup, etc.).

---

### TASK 0.8.1: Create migrations directory

**File:** `backend/migrations/001_initial_schema.sql` ⊕ (new file)

**Create this file with this content:**

```sql
-- CodeScope Database Migrations
-- All schema changes must be done via migration files.
-- Run: supabase db push --project-ref YOUR_PROJECT_REF
-- NEVER alter tables directly in production.
```

> The actual schema SQL will be added in Phase 1.1 when the repository layer is built.

---

### TASK 0.8.2: Add migration CI gate

**File:** `.github/workflows/ci.yml`

**Find the `e2e-tests` job or a similar CI job. Add this step:**

```yaml
- name: Run migrations
  run: npx supabase db push --project-ref ${{ secrets.SUPABASE_PROJECT_REF }}
  env:
    SUPABASE_DB_PASSWORD: ${{ secrets.SUPABASE_DB_PASSWORD }}
```

> Add this as the first step of the CI pipeline (before tests run).

---

## Phase 0 Verification

After completing all Phase 0 tasks, run these commands:

```bash
# 1. No hardcoded secrets
grep -E "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" docker-compose.yml
# Expected: nothing (0 matches)

# 2. Backend starts
cd backend && python -m uvicorn app.main:app --port 8000 &
sleep 3
curl -s http://localhost:8000/health
# Expected: {"status": "ok"}

# 3. Auth rate limiting is applied
# (Manual test: send 6 login requests in 60s, 6th should return 429)
```

---

## PHASE W0 — Acquisition Setup (Week 0, parallel with P0)

### TASK W0.1.1: Create early-access page

**File:** `frontend/app/early-access/page.tsx` ⊕ (new file)

```typescript
export default function EarlyAccess() {
  return (
    <main className={styles.container}>
      <h1>Understand AI-generated code — before it ships.</h1>
      <p>
        CodeScope traces how Cursor, Copilot, and ChatGPT write Python,
        then schedules spaced reviews so you remember what you shipped.
      </p>
      <form action="/api/early-access" method="POST">
        <input
          name="email"
          type="email"
          placeholder="your@university.edu"
          required
        />
        <button type="submit">Get Early Access</button>
      </form>
    </main>
  );
}
```

> Also create a corresponding CSS module at `frontend/app/early-access/page.module.css`.

---

### TASK W0.3.1: Rewrite landing page hero

**File:** `frontend/app/page.tsx`

**Find the hero `<h1>` line:**

```tsx
<h1>CodeScope visualizes Python execution step-by-step...</h1>
```

**Replace with:**

```tsx
<h1>Pasted AI-generated code. No idea why it is breaking.</h1>
```

Then find the hero `<p>` tag immediately after and replace it with:

```tsx
<p>
  CodeScope traces how Cursor, Copilot, and ChatGPT write Python —
  variable by variable, branch by branch — then schedules spaced reviews
  so you actually remember what you shipped.
</p>
```

> Only change the hero section (h1 + first p). Keep everything below the fold.

---

### TASK W0.4.1: Create analytics library

**File:** `frontend/lib/analytics.ts` ⊕ (new file)

```typescript
const ANON_ID_KEY = 'codescope_anon_id';

export function getAnonId(): string {
  if (typeof window === 'undefined') return '';
  let id = localStorage.getItem(ANON_ID_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(ANON_ID_KEY, id);
  }
  return id;
}

export function trackEvent(type: string, metadata?: Record<string, unknown>) {
  fetch('/api/analytics/track', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      anon_id: getAnonId(),
      event_type: type,
      metadata,
      occurred_at: new Date().toISOString(),
    }),
  }).catch(() => {}); // Never block UX
}
```

---

### TASK W0.4.2: Create analytics backend endpoint

**File:** `backend/app/routers/analytics.py` ⊕ (new file)

```python
from fastapi import APIRouter, Request
from datetime import datetime, timezone

router = APIRouter()

@router.post("/analytics/track")
async def track_event(request: Request):
    """
    Saves an anonymous event to Supabase anonymous_events table.
    No auth required — anonymous by design.
    """
    body = await request.json()
    anon_id = body.get("anon_id", "")
    event_type = body.get("event_type", "")
    metadata = body.get("metadata", {})
    occurred_at = body.get("occurred_at", datetime.now(timezone.utc).isoformat())

    settings = Settings()
    import httpx
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post(
            f"{settings.supabase_url}/rest/v1/anonymous_events",
            headers={
                "apikey": settings.supabase_service_key,
                "Authorization": f"Bearer {settings.supabase_service_key}",
                "Content-Type": "application/json",
            },
            json={
                "anon_id": anon_id,
                "event_type": event_type,
                "metadata": metadata,
                "occurred_at": occurred_at,
            },
        )

    return {"ok": True}
```

---

### TASK W0.4.3: Register analytics router in main.py

**File:** `backend/app/main.py`

**Find the existing router includes:**

```python
app.include_router(auth_router, prefix="/api")
app.include_router(traces_router, prefix="/api")
```

**Add after them:**

```python
app.include_router(analytics_router, prefix="/api")
```

> Also add `from app.routers.analytics import router as analytics_router` to the imports at the top.

---

### TASK W0.4.4: Create Supabase anonymous_events table

**File:** `backend/migrations/002_analytics_events.sql` ⊕ (new file)

```sql
-- Anonymous event tracking for churn analysis

CREATE TABLE IF NOT EXISTS anonymous_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  anon_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  metadata JSONB,
  occurred_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE anonymous_events ENABLE ROW LEVEL SECURITY;

-- Policy: anyone can INSERT (fire-and-forget)
CREATE POLICY "public_insert" ON anonymous_events FOR INSERT TO anon WITH CHECK (true);

-- Policy: authenticated users can SELECT
CREATE POLICY "authenticated_read" ON anonymous_events FOR SELECT TO authenticated USING (true);
```

---

## Phase W0 Verification

```bash
# Early access page exists
ls frontend/app/early-access/page.tsx
# Expected: file exists

# Hero leads with AI angle
grep -E "AI-generated|Cursor|Copilot|ChatGPT" frontend/app/page.tsx | head -1
# Expected: matches the hero text from TASK W0.3.1

# Analytics endpoint responds
curl -s -X POST http://localhost:8000/api/analytics/track \
  -H "Content-Type: application/json" \
  -d '{"anon_id": "test-user", "event_type": "trace_run", "metadata": {}}'
# Expected: {"ok": true}
```

---

## PHASE 1 — Engineering Foundation (Week 1)

> **Prerequisite:** Phase 0.2 must be merged first.
> **Risk:** High — architectural foundation. Slip here cascades to everything.

### Phase 1.1 — Supabase Repository Layer

The repository layer consolidates all Supabase REST API calls into one class. Do these tasks in order — each one unlocks the next.

---

### TASK 1.1.1: Create dependencies.py

**File:** `backend/app/dependencies.py` ⊕ (new file)

```python
from functools import lru_cache
from app.config import get_settings
from app.repositories.supabase import SupabaseRepository

@lru_cache
def get_settings():
    return Settings()

async def get_supabase_repo() -> SupabaseRepository:
    settings = get_settings()
    repo = SupabaseRepository(settings)
    yield repo
    await repo.close()
```

> Note: Add `from app.config import Settings` import at the top.

---

### TASK 1.1.2: Create SupabaseRepository class

**File:** `backend/app/repositories/supabase.py` ⊕ (new file)

Create this complete file. This is the single source of truth for all Supabase REST API calls:

```python
"""
Single source of truth for all Supabase REST API calls.
Replaces duplicated httpx.AsyncClient patterns across all routers.

Lifecycle:
  - Registered in app/dependencies.py as a FastAPI dependency
  - Injected into routers via Annotated[..., Depends(get_supabase_repo)]
  - Closed in lifespan shutdown: await repo.close()
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
import time
import datetime
import httpx
import structlog
from app.config import Settings

logger = structlog.get_logger(__name__)

# ── Result Types ───────────────────────────────────────────────────────────
@dataclass
class ProfileResult:
    id: str
    is_pro: bool
    email: str | None

@dataclass
class TraceResult:
    id: str
    code: str
    steps: list[dict]
    share_token: str | None
    is_public: bool
    user_id: str
    created_at: str

@dataclass
class ReviewResult:
    id: str
    code: str
    explanation: str
    steps: list[dict]
    due_date: str
    interval: int
    ease_factor: float
    streak: int

# ── Repository ─────────────────────────────────────────────────────────────
class SupabaseRepository:
    """
    All Supabase REST API calls go through this class.
    Includes circuit breaker for resilience.
    """

    def __init__(self, settings: Settings):
        self.base_url = settings.supabase_url
        self.service_key = settings.supabase_service_key
        self._client = httpx.AsyncClient(timeout=10.0)
        self._circuit_open = False
        self._circuit_opened_at: float | None = None
        self._cache: dict[str, tuple[Any, float]] = {}
        self._cache_ttl = 300

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
        }

    def _user_headers(self, token: str) -> dict[str, str]:
        return {
            "apikey": self.service_key,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _cache_key(self, method: str, path: str, params: dict | None) -> str:
        return f"{method}:{path}:{str(sorted(params.items()) if params else [])}"

    async def _get_cached(
        self,
        path: str,
        params: dict | None = None,
        headers: dict | None = None,
        ttl: int = 300,
    ) -> list[dict]:
        key = self._cache_key("GET", path, params)
        now = time.time()
        if key in self._cache:
            value, expires_at = self._cache[key]
            if now < expires_at:
                return value
        result = await self._get(path, params, headers)
        self._cache[key] = (result, now + ttl)
        return result

    async def _get(
        self,
        path: str,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> list[dict]:
        if self._is_circuit_open():
            logger.warning("supabase_circuit_open", path=path)
            return []
        try:
            resp = await self._client.get(
                f"{self.base_url}{path}",
                params=params,
                headers=headers or self._headers(),
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                self._trip_circuit()
            logger.error("supabase_get_failed", path=path,
                         status=e.response.status_code, detail=e.response.text[:200])
            return []
        except Exception as e:
            self._trip_circuit()
            logger.error("supabase_get_failed", path=path, error=str(e))
            return []

    async def _post(
        self,
        path: str,
        json: dict,
        headers: dict | None = None,
    ) -> dict | None:
        try:
            resp = await self._client.post(
                f"{self.base_url}{path}",
                json=json,
                headers=headers or self._headers(),
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error("supabase_post_failed", path=path, error=str(e))
            return None

    def _is_circuit_open(self) -> bool:
        if not self._circuit_open:
            return False
        if self._circuit_opened_at and (time.time() - self._circuit_opened_at) > 30:
            logger.info("supabase_circuit_recovering")
            self._circuit_open = False
            return False
        return True

    def _trip_circuit(self):
        self._circuit_open = True
        self._circuit_opened_at = time.time()
        logger.warning("supabase_circuit_tripped")

    async def close(self):
        await self._client.aclose()

    # ── Profile ─────────────────────────────────────────────────────────
    async def get_profile_by_token(self, token: str) -> ProfileResult | None:
        rows = await self._get(
            "/rest/v1/profiles",
            params={"id": f"eq.{token}", "select": "*"},
            headers=self._user_headers(token),
        )
        if not rows:
            return None
        p = rows[0]
        return ProfileResult(id=p["id"], is_pro=p.get("is_pro", False), email=p.get("email"))

    # ── Traces ─────────────────────────────────────────────────────────
    async def get_user_traces(
        self, user_id: str, limit: int = 20
    ) -> list[TraceResult]:
        rows = await self._get(
            "/rest/v1/traces",
            params={
                "user_id": f"eq.{user_id}",
                "limit": str(limit),
                "order": "created_at.desc",
                "select": "*",
            },
        )
        return [TraceResult(**r) for r in rows]

    async def save_trace(self, trace: dict, token: str) -> TraceResult | None:
        result = await self._post(
            "/rest/v1/traces",
            json=trace,
            headers=self._user_headers(token),
        )
        return TraceResult(**result) if result else None

    async def get_shared_trace(
        self, share_token: str, owner_token: str | None = None
    ) -> TraceResult | None:
        if owner_token:
            owner_id = await get_profile_id(owner_token)
            params = {
                "share_token": f"eq.{share_token}",
                "or": f"(is_public.eq.true,user_id.eq.{owner_id})",
                "select": "*",
                "limit": "1",
            }
            headers = self._user_headers(owner_token)
        else:
            params = {
                "share_token": f"eq.{share_token}",
                "is_public": "eq.true",
                "select": "*",
                "limit": "1",
            }
            headers = self._headers()

        rows = await self._get("/rest/v1/traces", params=params, headers=headers)
        return TraceResult(**rows[0]) if rows else None

    # ── Reviews ────────────────────────────────────────────────────────
    async def get_due_reviews(self, user_id: str) -> list[ReviewResult]:
        rows = await self._get_cached(
            "/rest/v1/review_cards",
            params={
                "user_id": f"eq.{user_id}",
                "due_date": f"lte.{datetime.datetime.utcnow().isoformat()}",
                "order": "due_date.asc",
                "select": "*",
            },
            ttl=60,
        )
        return [ReviewResult(**r) for r in rows]
```

---

### TASK 1.1.3: Add repository to app lifespan

**File:** `backend/app/main.py`

**Find the lifespan context manager or `on_event("startup")`. Add repository cleanup:**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    repo = SupabaseRepository(get_settings())
    app.state.supabase_repo = repo
    yield
    # shutdown
    await repo.close()
```

> If lifespan already exists, add `app.state.supabase_repo = repo` to startup and `await repo.close()` to shutdown.

---

### TASK 1.1.4: Refactor profiles.py to use repository

**File:** `backend/app/routers/profiles.py`

**Find:**

```python
async with httpx.AsyncClient(timeout=10.0) as client:
    resp = await client.get(...)
```

**Replace ALL httpx calls in this file with calls to the injected repository:**

```python
from typing import Annotated
from fastapi import Depends
from app.dependencies import get_supabase_repo
from app.repositories.supabase import SupabaseRepository

# In each endpoint:
repo: Annotated[SupabaseRepository, Depends(get_supabase_repo)]
```

> Keep the endpoint signatures, auth checks, and return values exactly the same. Only replace the httpx calls.

---

### TASK 1.1.5: Refactor traces.py to use repository

**File:** `backend/app/routers/traces.py`

**Find all `httpx.AsyncClient` usage and replace with repository calls.**

Key conversions:
- `httpx.get(.../rest/v1/traces...)` → `repo.get_user_traces(user_id)`
- `httpx.post(.../rest/v1/traces...)` → `repo.save_trace(trace_data, token)`
- `httpx.get(.../rest/v1/traces?share_token=...)` → `repo.get_shared_trace(share_token, token)`

> Keep all endpoint signatures, auth checks, and return values exactly the same.

---

### TASK 1.1.6: Refactor llm.py to use repository

**File:** `backend/app/routers/llm.py`

**Find all httpx calls and replace with repository calls.**

> Keep the SSE streaming logic and error handling exactly the same.

---

### TASK 1.1.7: Refactor examples.py and ratings.py

**File:** `backend/app/routers/examples.py` and `backend/app/routers/ratings.py`

**Find all httpx calls and replace with repository calls.**

---

### TASK 1.1.8: Refactor review.py

**File:** `backend/app/routers/review.py`

**Find all httpx calls and replace with repository calls.**

---

### TASK 1.1.9: Create initial schema migration

**File:** `backend/migrations/003_initial_schema.sql` ⊕ (new file)

```sql
-- Initial schema for CodeScope
-- Run in Supabase SQL editor: supabase.com → SQL Editor

-- Profiles table (may already exist from Supabase Auth)
-- ALTER TABLE profiles ADD COLUMN IF NOT EXISTS is_pro BOOLEAN DEFAULT false;

-- Traces table
CREATE TABLE IF NOT EXISTS traces (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  code TEXT NOT NULL,
  language TEXT DEFAULT 'python',
  steps JSONB NOT NULL DEFAULT '[]'::jsonb,
  share_token TEXT UNIQUE,
  is_public BOOLEAN DEFAULT false,
  expires_at TIMESTAMPTZ,
  password_hash TEXT,
  concept_tags TEXT[] DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Review cards table
CREATE TABLE IF NOT EXISTS review_cards (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  trace_id UUID NOT NULL REFERENCES traces(id) ON DELETE CASCADE,
  concept_tag TEXT,
  due_date TIMESTAMPTZ NOT NULL,
  interval INT DEFAULT 1,
  ease_factor FLOAT DEFAULT 2.5,
  streak INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Share analytics table
CREATE TABLE IF NOT EXISTS share_analytics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  share_token TEXT NOT NULL,
  viewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  viewer_ip_hash TEXT,
  referrer TEXT,
  is_authenticated BOOLEAN DEFAULT false,
  forked BOOLEAN DEFAULT false,
  user_agent TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_traces_user_id ON traces(user_id);
CREATE INDEX IF NOT EXISTS idx_traces_share_token ON traces(share_token);
CREATE INDEX IF NOT EXISTS idx_review_cards_user_due ON review_cards(user_id, due_date);
CREATE INDEX IF NOT EXISTS idx_share_analytics_token ON share_analytics(share_token);
```

---

## Phase 1 Verification

```bash
# Day 2 checkpoint: Profile repo works
curl -s http://localhost:8000/api/profiles/me -H "Authorization: Bearer <test_token>"
# Expected: returns profile data

# Day 4 checkpoint: No httpx in routers
grep -r "httpx.AsyncClient" backend/app/routers/
# Expected: nothing (0 matches)

# All routers import and use SupabaseRepository
grep -l "SupabaseRepository" backend/app/routers/*.py
# Expected: lists all refactored router files

# Import check (no circular imports)
cd backend && python -c "from app.main import app; print('OK')"
# Expected: OK
```

---

## PHASE 1B — Additional Foundation Tasks

### TASK 1.2.1: Remove debug logging from api.ts

**File:** `frontend/lib/api.ts`

**Find all occurrences of `console.log('[DEBUG', ` and `console.log('[API', ` and replace with:**

```typescript
const logger = {
  debug: (...args: unknown[]) => {
    if (process.env.NODE_ENV === 'development') console.log(...args);
  },
};
```

> If `console.log` is used for actual errors (not debug), keep those.

---

### TASK 1.3.1: Add Docker Compose webServer to Playwright config

**File:** `frontend/playwright.config.ts`

**Find the existing `webServer` config (or the config object). Add or update:**

```typescript
webServer: {
  command: 'cd .. && docker compose up backend redis -d',
  url: 'http://localhost:8000/health',
  reuseExistingServer: !process.env.CI,
  timeout: 120 * 1000,
},
```

---

## PHASE 2A — Test Infrastructure (Week 2)

### TASK 2a.1.1: Add frontend tests to CI

**File:** `.github/workflows/ci.yml`

**Find the jobs section and add:**

```yaml
frontend-test:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version: '22'
        cache: 'npm'
        cache-dependency-path: frontend/package-lock.json
    - run: npm ci
    - run: npm run test -- --coverage --reporter=junit --outputFile=test-results/junit.xml
    - uses: actions/upload-artifact@v4
      with:
        name: frontend-test-results
        path: frontend/test-results/
    - uses: codecov/codecov-action@v4
```

---

### TASK 2a.2.1: Create VariablePanel.test.tsx

**File:** `frontend/__tests__/VariablePanel.test.tsx` ⊕ (new file)

```typescript
import { render, screen } from '@testing-library/react';
import { VariablePanel } from '@/components/tracer/VariablePanel';

describe('VariablePanel', () => {
  it('renders variables with type badges', () => {
    const variables = {
      x: { type: 'int', value: '5', changed: false },
      name: { type: 'str', value: '"hello"', changed: false },
    };
    render(<VariablePanel variables={variables} />);
    expect(screen.getByText('x')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('int')).toBeInTheDocument();
  });

  it('highlights changed variables', () => {
    const variables = {
      x: { type: 'int', value: '5', changed: true },
    };
    render(<VariablePanel variables={variables} />);
    const xEl = screen.getByText('x');
    expect(xEl.closest('[class*="variable"]')).toHaveClass('changed');
  });

  it('shows branch decision icon for bool variables', () => {
    const variables = {
      flag: { type: 'bool', value: 'True', changed: false },
    };
    render(<VariablePanel variables={variables} />);
    expect(screen.getByText('flag')).toBeInTheDocument();
    expect(screen.getByText('bool')).toBeInTheDocument();
  });

  it('shows empty state when no variables', () => {
    render(<VariablePanel variables={{}} />);
    expect(screen.getByText(/no variables/i)).toBeInTheDocument();
  });
});
```

---

### TASK 2a.2.2: Create ExplanationPanel.test.tsx

**File:** `frontend/__tests__/ExplanationPanel.test.tsx` ⊕ (new file)

```typescript
import { render, screen } from '@testing-library/react';
import { ExplanationPanel } from '@/components/llm/ExplanationPanel';

describe('ExplanationPanel', () => {
  it('renders generating skeleton when state is generating', () => {
    render(<ExplanationPanel code="x = 1" line={1} />);
    expect(screen.getByTestId('explanation-skeleton')).toBeInTheDocument();
  });

  it('renders error state after retries exhausted', () => {
    render(<ExplanationPanel code="x = 1" line={1} retryCount={3} />);
    expect(screen.getByText(/error|failed/i)).toBeInTheDocument();
  });

  it('renders streamed text when done', () => {
    render(<ExplanationPanel code="x = 1" line={1} explanation="This assigns 1 to x." />);
    expect(screen.getByText('This assigns 1 to x.')).toBeInTheDocument();
  });

  it('has close button', () => {
    const onClose = jest.fn();
    render(<ExplanationPanel code="x = 1" line={1} onClose={onClose} />);
    const closeBtn = screen.getByRole('button', { name: /close/i });
    closeBtn.click();
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
```

---

### TASK 2a.2.3: Create AnimationControls.test.tsx

**File:** `frontend/__tests__/AnimationControls.test.tsx` ⊕ (new file)

```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { AnimationControls } from '@/components/tracer/AnimationControls';

describe('AnimationControls', () => {
  it('shows play button when paused', () => {
    render(<AnimationControls isPlaying={false} onTogglePlay={jest.fn()} />);
    expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
  });

  it('shows pause button when playing', () => {
    render(<AnimationControls isPlaying={true} onTogglePlay={jest.fn()} />);
    expect(screen.getByRole('button', { name: /pause/i })).toBeInTheDocument();
  });

  it('step back is disabled at step 0', () => {
    render(
      <AnimationControls
        isPlaying={false}
        onTogglePlay={jest.fn()}
        currentStep={0}
        totalSteps={10}
        onStepBack={jest.fn()}
        onStepForward={jest.fn()}
      />
    );
    expect(screen.getByRole('button', { name: /back/i })).toBeDisabled();
  });

  it('step forward is disabled at last step', () => {
    render(
      <AnimationControls
        isPlaying={false}
        onTogglePlay={jest.fn()}
        currentStep={9}
        totalSteps={10}
        onStepBack={jest.fn()}
        onStepForward={jest.fn()}
      />
    );
    expect(screen.getByRole('button', { name: /forward/i })).toBeDisabled();
  });

  it('Space key toggles play when not in text input', () => {
    const onTogglePlay = jest.fn();
    render(<AnimationControls isPlaying={false} onTogglePlay={onTogglePlay} />);
    fireEvent.keyDown(document, { key: ' ' });
    expect(onTogglePlay).toHaveBeenCalledTimes(1);
  });
});
```

---

### TASK 2a.2.4: Create ErrorBoundary.test.tsx

**File:** `frontend/__tests__/ErrorBoundary.test.tsx` ⊕ (new file)

```typescript
import { render, screen } from '@testing-library/react';
import { ErrorBoundary } from '@/components/errors/ErrorBoundary';

function ThrowError({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error('Test error');
  return <div>Content</div>;
}

describe('ErrorBoundary', () => {
  it('renders children when no error', () => {
    render(
      <ErrorBoundary>
        <div>Content</div>
      </ErrorBoundary>
    );
    expect(screen.getByText('Content')).toBeInTheDocument();
  });

  it('shows fallback UI when error occurs', () => {
    const { container } = render(
      <ErrorBoundary fallback={<div>Something went wrong</div>}>
        <ThrowError shouldThrow />
      </ErrorBoundary>
    );
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('reset() method allows retry', () => {
    const { getByText } = render(
      <ErrorBoundary fallback={<button onClick={() => window.location.reload()}>Reset</button>}>
        <ThrowError shouldThrow />
      </ErrorBoundary>
    );
    expect(getByText('Reset')).toBeInTheDocument();
  });
});
```

---

### TASK 2a.4.1: Create integration test conftest

**File:** `backend/tests/integration/conftest.py` ⊕ (new file)

```python
import pytest
from unittest.mock import AsyncMock
from app.repositories.supabase import (
    SupabaseRepository,
    ProfileResult,
    TraceResult,
)

@pytest.fixture
def mock_supabase_repo():
    repo = AsyncMock(spec=SupabaseRepository)
    repo.get_profile_by_token = AsyncMock(return_value=ProfileResult(
        id="user-123", is_pro=False, email="test@example.com"
    ))
    repo.get_shared_trace = AsyncMock(return_value=TraceResult(
        id="trace-456",
        code="x = 1",
        steps=[{"step_number": 0, "line_number": 1, "variables": {}}],
        share_token="abc123",
        is_public=True,
        user_id="user-123",
        created_at="2025-01-01T00:00:00Z",
    ))
    repo.get_user_traces = AsyncMock(return_value=[])
    return repo
```

---

### TASK 2a.4.2: Create test_traces.py

**File:** `backend/tests/integration/test_traces.py` ⊕ (new file)

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_run_trace_returns_steps_and_trace_id():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/traces/run",
            json={"code": "x = 1\nprint(x)", "language": "python"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert "steps" in data
    assert "trace_id" in data

@pytest.mark.asyncio
async def test_run_trace_blocks_side_effects():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/traces/run",
            json={"code": "import os\nprint(os.getcwd())"},
        )
    assert resp.status_code == 422
    assert resp.json()["error_code"] == "SIDE_EFFECT_BLOCKED"
```

---

### TASK 2a.4.3: Create test_rate_limits.py

**File:** `backend/tests/integration/test_rate_limits.py` ⊕ (new file)

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_trace_endpoint_rate_limited():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Send 31 requests in 60 seconds
        results = []
        for _ in range(31):
            resp = await client.post(
                "/api/traces/run",
                json={"code": "x = 1"},
            )
            results.append(resp.status_code)

        # First 30 should succeed, 31st should be rate limited
        assert results[-1] == 429
```

---

## PHASE 2B — Engineering Hygiene (Week 2)

### TASK 2b.1.1: Extract ShareTraceModal from tracer page

**File:** `frontend/components/tracer/ShareTraceModal.tsx` ⊕ (new file)

Extract the Share Modal JSX from `frontend/app/tracer/page.tsx` into this new component. The component should accept:
- `isOpen`, `onClose` — modal visibility
- `traceId` — the trace to share
- `onSuccess(shareUrl)` — callback when link is generated

> Import `shareTrace` from `@/lib/api`. Use the same CSS classes as the modal section in the existing tracer page.

---

### TASK 2b.1.2: Extract TraceStatusBar component

**File:** `frontend/components/tracer/TraceStatusBar.tsx` ⊕ (new file)

Extract the "Step N of M · Xms" display from `tracer/page.tsx`. Props: `currentStep: number`, `totalSteps: number`, `durationMs: number`.

---

### TASK 2b.1.3: Reduce tracer/page.tsx to ≤200 lines

**File:** `frontend/app/tracer/page.tsx`

After extracting ShareTraceModal (TASK 2b.1.1) and TraceStatusBar (TASK 2b.1.2), the tracer page should be ≤200 lines.

Verification:

```bash
wc -l frontend/app/tracer/page.tsx
# Expected: ≤ 200
```

---

### TASK 2b.2.1: Create i18n hook

**File:** `frontend/hooks/useI18n.ts` ⊕ (new file)

```typescript
import { useTranslation } from 'react-i18next';

export function useI18n() {
  const { t, i18n } = useTranslation();
  return { t, i18n, changeLanguage: i18n.changeLanguage };
}
```

---

### TASK 2b.2.2: Wire i18n to landing page

**File:** `frontend/app/page.tsx`

**Find hardcoded strings and replace with `t()` calls:**

```typescript
import { useI18n } from '@/hooks/useI18n';

// Inside component:
const { t } = useI18n();

// Replace hardcoded strings:
<h1>{t('landing.hero.title')}</h1>
<p>{t('landing.hero.subtitle')}</p>
```

---

### TASK 2b.3.1: Apply dark theme to examples page

**File:** `frontend/app/examples/page.module.css`

**Find the root CSS variable block (`.container` or `body`) and set:**

```css
background: var(--bg-primary, #0f172a);
color: var(--text-primary, #f8fafc);
```

> Copy the `background` and `color` values from `tracer/page.module.css`.

---

### TASK 2b.4.1: Add data-testid to examples page

**File:** `frontend/app/examples/page.tsx`

**Find the example card rendering (inside `.map()`) and add `data-testid`:**

```tsx
<div
  data-testid={`example-card-${example.id}`}
  className={styles.card}
  onClick={() => router.push(`/examples/${example.id}`)}
>
```

---

### TASK 2b.4.2: Add data-testid to dashboard page

**File:** `frontend/app/dashboard/page.tsx`

**Find trace card elements and add:**

```tsx
<div data-testid={`trace-card-${trace.id}`}>
```

---

### TASK 2b.4.3: Add data-testid to review page

**File:** `frontend/app/review/[card_id]/page.tsx`

**Find the card container and add:**

```tsx
<div data-testid={`review-card-${card.id}`}>
```

---

## Phase 2 Verification

```bash
# Frontend tests pass
cd frontend && npm run test -- --coverage 2>&1 | tail -20
# Expected: ≥80% coverage, 0 failures

# No debug console.log remaining
grep -n "console.log" frontend/lib/api.ts
# Expected: 0 matches (or only inside logger.debug)

# All E2E tests use data-testid (no class* selectors)
grep -c "class\*=" frontend/e2e/*.spec.ts
# Expected: 0 matches

# Tracer page is ≤200 lines
wc -l frontend/app/tracer/page.tsx
# Expected: ≤ 200
```

---

## PHASE 3A — Feature Build + Verify (Week 3)

### TASK 3a.1.1: Verify LLM streaming works end-to-end

**File:** `frontend/__tests__/ExplanationPanel.test.tsx` (enhance existing)

**Add this test:**

```typescript
it('streams explanation within 3 seconds', async () => {
  render(<ExplanationPanel code="x = 1" line={1} />);
  const button = screen.getByRole('button', { name: /why/i });
  await button.click();
  // Simulate SSE event
  const panel = await screen.findByTestId('explanation-text', {}, { timeout: 3000 });
  expect(panel.textContent).toHaveLengthGreaterThan(0);
});
```

> Manual test: Open tracer at http://localhost:3000/tracer, paste `x = 1`, click Trace, click "Why is this here?" on line 1. Explanation should appear within 3 seconds.

---

### TASK 3a.2.1: Verify What-If modal is connected end-to-end

**File:** `frontend/components/tracer/WhatIfModal.tsx`

**Verify these connections exist:**
1. `onSubmit` receives `(initialNamespace: Record<string, string>, changedVars: string[])`
2. `runTrace(code, { initialNamespace })` is called on submit
3. The new trace result replaces the current trace in state

> If these connections exist, no changes needed. If broken, trace the chain from modal → parent page → api.ts and fix each step.

---

### TASK 3a.3.1: Verify fork button on shared trace page

**File:** `frontend/app/trace/[share_token]/page.tsx`

**Find the fork button:**

```tsx
<button
  data-testid="fork-trace-button"
  onClick={handleFork}
```

**Verify `handleFork` calls:**

```typescript
const res = await authFetch(`${getApiBase()}/traces/shared/${shareToken}/fork`, {
  method: 'POST'
});
const data = await res.json();
router.push(data.share_url);
```

> If the button or handler is missing, add the fork button and handler per the TASK 1E-4 in this skill.

---

## Phase 3A Verification

```bash
# Backend fork endpoint exists
curl -s -X POST http://localhost:8000/api/traces/shared/test_token/fork \
  -H "Authorization: Bearer <test_token>"
# Expected: 404 (not found) or proper response

# What-If replay works end-to-end
# Manual: tracer page → click "What If?" → change x to 10 → click "Replay"
# Expected: trace replays with x=10

# Fork button visible on shared trace page
# Manual: save private trace → share → open share link (as owner)
# Expected: "Fork This Trace" button visible
```

---

## PHASE 3B — UX Polish + Pricing (Week 4)

### TASK 3b.1.1: Complete landing page rewrite

**File:** `frontend/app/page.tsx`

**Add these sections below the hero (after TASK W0.3.1):**

1. **How it works** — 3-step visual: Paste → Trace → Understand → Review
2. **Feature highlights** — Tracer, LLM explanations, spaced repetition (3 cards)
3. **Social proof** — One testimonial quote
4. **Pricing preview** — "Free 50 traces/month. Pro: unlimited. [See pricing]"

---

### TASK 3b.2.1: Create pricing page

**File:** `frontend/app/pricing/page.tsx` ⊕ (new file)

```typescript
export default function Pricing() {
  return (
    <main className={styles.container}>
      <h1>Simple, transparent pricing</h1>
      <div className={styles.tiers}>
        <div className={styles.freeTier}>
          <h2>Free</h2>
          <p className={styles.price}>$0<span>/month</span></p>
          <ul>
            <li>50 traces per month</li>
            <li>AI explanations</li>
            <li>Spaced repetition review</li>
          </ul>
          <a href="/auth/signup" className={styles.cta}>Get Started</a>
        </div>
        <div className={styles.proTier}>
          <h2>Pro</h2>
          <p className={styles.price}>$15<span>/month</span></p>
          <ul>
            <li>Unlimited traces</li>
            <li>AI explanations</li>
            <li>Spaced repetition review</li>
            <li>Shared trace links</li>
            <li>Priority support</li>
          </ul>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const email = e.currentTarget.email.value;
              await fetch('/api/upgrade-request', {
                method: 'POST',
                body: JSON.stringify({ email, tier: 'pro' }),
              });
              alert("We'll send you a payment link within 24 hours.");
            }}
          >
            <input name="email" type="email" placeholder="your@email.com" required />
            <button type="submit">Get Pro Access</button>
          </form>
        </div>
      </div>
    </main>
  );
}
```

---

### TASK 3b.2.2: Add usage bar to dashboard

**File:** `frontend/app/dashboard/page.tsx`

**Find the dashboard stats section and add:**

```tsx
<div className={styles.usageBar}>
  <span>{used}/50 traces used</span>
  <progress value={used} max={50} />
  {used >= 50 && (
    <Link href="/pricing" className={styles.upgradeLink}>
      Upgrade to Pro
    </Link>
  )}
</div>
```

---

### TASK 3b.3.1: Add responsive CSS to tracer page

**File:** `frontend/app/tracer/page.module.css`

**Add at the bottom:**

```css
@media (max-width: 1024px) {
  .tracer-layout { flex-direction: column; }
  .editor-pane { height: 45vh; }
  .side-pane { height: 55vh; }
}

@media (max-width: 640px) {
  .editor-pane { height: 35vh; }
  .side-pane { height: 65vh; }
  .toolbar { flex-wrap: wrap; gap: 8px; }
}
```

---

### TASK 3b.4.1: Add focus-visible styles for accessibility

**File:** `frontend/app/globals.css`

**Find or add:**

```css
:focus-visible {
  outline: 2px solid var(--accent, #6366f1);
  outline-offset: 2px;
}
```

---

### TASK 3b.5.1: Lazy-load ExplanationPanel

**File:** `frontend/app/tracer/page.tsx`

**Find the ExplanationPanel import and replace with dynamic import:**

```typescript
const ExplanationPanel = dynamic(
  () => import('@/components/llm/ExplanationPanel').then(mod => mod.ExplanationPanel),
  {
    loading: () => <ExplanationPanelSkeleton />,
    ssr: false,
  }
);
```

---

## Phase 3B Verification

```bash
# Lighthouse accessibility
npx lighthouse http://localhost:3000 --output=json | jq '.categories.accessibility.score'
# Expected: ≥ 0.90

# Pricing page renders
curl -s http://localhost:3000/pricing | grep -E "Free|Pro|pricing"
# Expected: pricing content found

# Responsive layout check
# Manual: Chrome DevTools → 390px viewport → both panels scroll independently
```

---

## PHASE 4A — Production Reliability (Week 5)

### TASK 4a.1.1: Install and configure Sentry for frontend

**File:** `frontend/next.config.js`

**Add Sentry config:**

```javascript
const withSentryConfig = require('@sentry/nextjs/config')();

module.exports = withSentryConfig({
  // existing config
});
```

> Also add `SENTRY_DSN` to Vercel environment variables.

---

### TASK 4a.1.2: Install and configure Sentry for backend

**File:** `backend/app/main.py`

**Find the imports and add:**

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastAPIIntegration

sentry_sdk.init(
    dsn=os.environ.get("SENTRY_DSN"),
    integrations=[FastAPIIntegration()],
    traces_sample_rate=0.1,
    ignore_errors=[KeyboardInterrupt],
)
```

---

### TASK 4a.2.1: Enhance health check endpoint

**File:** `backend/app/main.py`

**Find the existing `/health` endpoint and replace with:**

```python
@router.get("/health")
async def health_check():
    checks = {
        "supabase": await check_supabase(),
        "redis": await check_redis(),
        "llm": await check_llm_cloud(),
    }
    all_ok = all(c["ok"] for c in checks.values())
    return JSONResponse(
        {"status": "healthy" if all_ok else "degraded", "checks": checks},
        status_code=200 if all_ok else 503,
    )
```

> Implement `check_supabase()`, `check_redis()`, `check_llm_cloud()` helper functions that return `{"ok": True/False, "detail": "..."}`.

---

### TASK 4a.3.1: Add request correlation IDs

**File:** `backend/app/main.py`

**Find the app definition and add:**

```python
from uuid import uuid4

@app.middleware
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid4()))
    structlog.contextvars.clear()
    structlog.contextvars.bind_contextvars(request_id=request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
```

---

## PHASE 4B — Observability + Docker (Week 5)

### TASK 4b.1.1: Add Prometheus metrics endpoint

**File:** `backend/app/main.py`

**Find the imports and add:**

```python
from prometheus_fastapi_instrumentator import instrument_app, metrics

instrument_app(app, metrics=[
    metrics.request_size(histogram_buckets=[256, 1024, 65536]),
    metrics.response_size(histogram_buckets=[256, 1024, 65536]),
    metrics.latency(buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)),
    metrics.default(namespace="codescope", subsystem="api"),
])
```

---

### TASK 4b.2.1: Create production Dockerfile

**File:** `backend/Dockerfile.production` ⊕ (new file)

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /install /usr/local
COPY ./app ./app
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### TASK 4b.2.2: Create .dockerignore

**File:** `.dockerignore` ⊕ (new file)

```
__pycache__ *.pyc .git .env .coverage .pytest_cache
frontend/node_modules frontend/.next *.md tests/
```

---

## Phase 4 Verification

```bash
# Health check returns all 4 checks
curl -s http://localhost:8000/health | jq '.checks'
# Expected: supabase, redis, llm all ok: true

# Prometheus metrics endpoint
curl -s http://localhost:8000/metrics | head -10
# Expected: Prometheus-formatted metrics

# Production Docker image builds
docker build -f backend/Dockerfile.production . -t codescope-backend
docker run --rm codescope-backend &
sleep 5
curl -s http://localhost:8000/health
# Expected: {"status": "healthy"}
docker stop codescope-backend

# Sentry receives errors
# Manual: raise Exception("test") in a route → appears in Sentry dashboard within 5 min
```

---

## PHASE 5 — Credibility Sprint + Soft Launch (Week 6)

### TASK 5.1.1: Create before/after example asset

**File:** `frontend/public/demo-copilot-failure.md` ⊕ (new file)

Document one real Copilot failure case with step-by-step trace:

```markdown
# Copilot Suggestion: List Comprehension Filter

Copilot suggested: `results = [x for x in items if x > 0]`

CodeScope shows:
  x=3: added to results
  x=-5: filtered out
  x=0: filtered out (implicit falsy)

Key insight: x=0 gets silently dropped. Copilot often writes this
without explaining the implicit truthiness behavior.
```

---

### TASK 5.2.1: Add SEO meta tags and structured data

**File:** `frontend/app/layout.tsx`

**Find the `<head>` section and add:**

```tsx
<link rel="canonical" href="https://codescope.app" />
<meta name="robots" content="index, follow" />
```

**Add structured data in the page component:**

```tsx
<script
  type="application/ld+json"
  dangerouslySetInnerHTML={{
    __html: JSON.stringify({
      "@context": "https://schema.org",
      "@type": "WebApplication",
      "name": "CodeScope",
      "description": "Understand AI-generated Python code through step-by-step tracing and spaced repetition.",
      "url": "https://codescope.app",
      "applicationCategory": "EducationApplication",
      "operatingSystem": "Any",
    }),
  }}
/>
```

---

## Final Soft Launch Verification

Run the full soft launch checklist from FEATURE-REVIEW.md:

```bash
# 1. Phase 0 P0 security fixes merged
grep -E "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" docker-compose.yml
# Expected: 0 matches

# 2. Landing page leads with AI angle
grep -E "AI-generated|AI assistant" frontend/app/page.tsx
# Expected: matches hero text

# 3. /pricing page live
curl -s http://localhost:3000/pricing | grep -c "Free"
# Expected: ≥ 2

# 4. Health check returns green
curl -s http://localhost:8000/health
# Expected: status: "healthy"

# 5. All Phase 2a tests passing
cd frontend && npm run test -- --coverage 2>&1 | grep "TOTAL"
# Expected: ≥80%

# 6. Frontend build succeeds
cd frontend && npm run build 2>&1 | tail -5
# Expected: success, 0 errors
```

---

## Troubleshooting Guide

### A task's "Find" block does not match the file

**Reason:** The file may have been modified since this skill was written.

**Action:**
1. Re-read the file with the Read tool
2. Find the closest matching section
3. Make the minimal change to achieve the same goal
4. Note the discrepancy and continue

### A task says "file not found" for a new file

**Action:** The file needs to be created. Use the Write tool to create it with the provided content.

### Circular import errors after Phase 1.1

**Reason:** `dependencies.py` imports `SupabaseRepository` which imports `get_profile_id` from `auth.py`.

**Action:** Move `get_profile_id` into `app/repositories/supabase.py` OR create `app/repositories/_helpers.py` that both files import from.

### pytest fails with missing Supabase

**Reason:** Integration tests require mock fixtures.

**Action:** Use the `mock_supabase_repo` fixture from TASK 2a.4.1. Override the repository in your test client app state:

```python
app.dependency_overrides[get_supabase_repo] = lambda: mock_supabase_repo
```

### Next.js build fails after adding new pages

**Reason:** New pages need CSS modules or are missing required exports.

**Action:**
1. Create a corresponding `page.module.css` for new pages
2. Verify all exports (including `metadata` if needed) are present
3. Run `npm run build` again

### Rate limiting returns 500 instead of 429

**Reason:** SlowAPI not properly registered in main.py.

**Action:** Add to `main.py`:

```python
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```
