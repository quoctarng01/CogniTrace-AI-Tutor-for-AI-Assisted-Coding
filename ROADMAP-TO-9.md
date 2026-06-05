# CodeScope — Roadmap to 9/10

> Honest assessment against current score: **6.5/10**
> Target: **9/10**
> Generated via structured feedback loop

---

## Score Gap Analysis

| Dimension | Current | Target | Gap | Primary Blocker |
|---|---|---|---|---|
| Backend Security & DevOps | 5.6 | 9.0 | +3.4 | Hardcoded secrets, CORS, no rate limit on traces/run |
| Product Strategy | 5.9 | 9.0 | +3.1 | Landing page messaging, pricing page, i18n not wired |
| Frontend UI/UX | 7.0 | 9.0 | +2.0 | Light theme on examples, emoji icons, no focus styles |
| Testing & Reliability | 7.5 | 9.0 | +1.5 | Frontend unit tests absent from CI, E2E fragile |
| Architecture & Code Quality | 7.0 | 9.0 | +2.0 | No Supabase repository layer, 526-line page.tsx |
| Documentation | 8.0 | 9.0 | +1.0 | No API docs, no contributing guide |
| **Overall** | **6.5** | **9.0** | **+2.5** | |

**Reality check:** Going from 6.5 → 9.0 requires ~60-80 hours of focused work across security hardening, product messaging, test coverage, and architecture refactoring. The current codebase has strong fundamentals — this is polish and completeness work.

---

## Phase 1 — Security & DevOps Hardening
**Effort: ~15 hours | Impact: +1.5 to overall score | Risk: Low**

These are non-negotiable before any deployment. The hardcoded secrets in `docker-compose.yml` alone make the project unsafe to deploy.

### 1.1 Remove All Hardcoded Secrets from docker-compose.yml
**File:** `docker-compose.yml`
**Time:** 1 hour

```yaml
# BEFORE (INSECURE):
environment:
  SUPABASE_ANON_KEY: ${SUPABASE_ANON_KEY:-eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24ifQ.fake}

# AFTER (SAFE):
environment:
  SUPABASE_ANON_KEY: ${SUPABASE_ANON_KEY:?SUPABASE_ANON_KEY is required}
```

Every secret-bearing environment variable must:
1. Use `${VAR:?error message}` syntax — fails fast if unset
2. Have no default value that looks like a real secret
3. Document required vars in `.env.example`

### 1.2 Fix CORS for Production
**File:** `backend/app/main.py`
**Time:** 1 hour

The current CORS config is hardcoded to `localhost:*`. This breaks immediately on Vercel.

```python
# Read allowed origins from environment
# VERCEL_URL is set automatically by Vercel: https://your-app.vercel.app
# Add localhost for local dev
_allowed = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173")
origins = [o.strip() for o in _allowed.split(",") if o.strip()]

# Add Vercel preview/production URL if VERCEL_URL is set
vercel_url = os.getenv("VERCEL_URL")
if vercel_url:
    origins.append(f"https://{vercel_url}")
    # Also add preview URLs pattern
    origins.append(f"https://*.vercel.app")

app.add_middleware(
    CORSMustomOrigin,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
```

Add to `.env.example`:
```
# Comma-separated list of allowed CORS origins
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
# Vercel sets this automatically
VERCEL_URL=
```

### 1.3 Fix `get_profile_id` Auth Bug
**File:** `backend/app/routers/auth.py`
**Time:** 30 minutes

Line 73 passes the full `Bearer <token>` header instead of just the token:

```python
# BROKEN (current):
params={"user_id": f"eq.{authorization[7:]}", ...}
headers={"Authorization": f"Bearer {authorization}", ...}  # ← passes "Bearer <token>"

# FIXED:
token = authorization[7:] if authorization.startswith("Bearer ") else authorization
params={"user_id": f"eq.{token}", ...}
headers={"Authorization": f"Bearer {token}", ...}
```

### 1.4 Add Rate Limiting to `/api/traces/run`
**Files:** `backend/app/main.py`, `backend/app/routers/traces.py`
**Time:** 2 hours

Currently `/api/traces/run` has **no SlowAPI rate limit**. A single user can exhaust the subprocess concurrency pool.

```python
# In main.py, after creating app:
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={
            "detail": {
                "error": "RATE_LIMITED",
                "message": "Too many trace requests. Please wait a moment.",
                "upgrade_url": "/auth/signup",
            }
        }
    )

# In traces.py:
from slowapi import Limiter
from slowapi.util import get_remote_address
limiter = Limiter(key_func=get_remote_address)

@router.post("/traces/run")
@limiter.limit("30/minute")  # 30 traces/minute max
async def run_trace(req: TraceRequest, request: Request, ...):
    ...
```

### 1.5 Add Rate Limiting to Auth Endpoints
**File:** `backend/app/routers/auth.py`
**Time:** 1 hour

No rate limiting on auth endpoints → brute force vulnerability.

```python
@router.post("/auth/callback")
@limiter.limit("10/minute")  # 10 auth attempts/minute
async def auth_callback(req: AuthCallbackRequest, request: Request, ...):
    ...
```

### 1.6 Add Supabase Repository Layer
**File:** `backend/app/services/supabase_client.py` (new)
**Time:** 4 hours

Every router duplicates the same Supabase HTTP client pattern. Extract it:

```python
# backend/app/services/supabase_client.py
class SupabaseClient:
    """
    Centralized Supabase REST API client.
    All database access goes through here — single place to change.
    """
    def __init__(self, settings: Settings):
        self.url = settings.supabase_url
        self.service_key = settings.supabase_service_key
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=10.0,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()

    def _headers(self, token: str | None = None) -> dict:
        h = {"apikey": self.service_key, "Content-Type": "application/json"}
        if token:
            h["Authorization"] = f"Bearer {token}"
        return h

    async def get_one(self, table: str, params: dict, token: str | None = None) -> dict | None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self.url}/rest/v1/{table}",
                params=params,
                headers=self._headers(token),
            )
            if resp.status_code == 200:
                data = resp.json()
                return data[0] if data else None
            return None

    async def get_many(self, table: str, params: dict, token: str | None = None) -> list:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self.url}/rest/v1/{table}",
                params=params,
                headers=self._headers(token),
            )
            return resp.json() if resp.status_code == 200 else []

    async def insert(self, table: str, data: dict, token: str | None = None) -> dict | None:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{self.url}/rest/v1/{table}",
                json=data,
                headers={**self._headers(token), "Prefer": "return=representation"},
            )
            return resp.json() if resp.status_code in (200, 201) else None

    async def patch(self, table: str, params: dict, data: dict, token: str | None = None) -> bool:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"{self.url}/rest/v1/{table}",
                params=params,
                json=data,
                headers={**self._headers(token), "Prefer": "return=minimal"},
            )
            return resp.status_code in (200, 204, 404)  # 404 is ok — idempotent
```

Then refactor `traces.py` to use it:

```python
# Before: 15 lines of duplicated httpx boilerplate per function
# After:
from app.services.supabase_client import SupabaseClient

async def save_trace(...):
    async with SupabaseClient(settings) as db:
        trace = await db.insert("traces", trace_data, authorization)
```

**Impact:** Eliminates ~200 lines of duplicated Supabase code across all routers. Makes it trivial to swap the database layer.

### 1.7 Docker Compose Production Hardening
**File:** `docker-compose.yml`
**Time:** 3 hours

| Issue | Fix |
|---|---|
| No `restart:` policy | Add `restart: unless-stopped` to all services |
| No resource limits | Add `deploy: {resources: {limits: {cpus: '0.5', memory: 512M}}}` |
| No health check for Redis | Already has one — verify it works |
| Hardcoded `DEBUG: "true"` | Change to `${DEBUG:-false}`, never default to true |
| No `.dockerignore` | Create one excluding `node_modules`, `.git`, `__pycache__` |
| Frontend uses `volumes` for dev | Add a separate `Dockerfile.production` with multi-stage build |

Create `Dockerfile.production` for frontend:

```dockerfile
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

Enable standalone output in `next.config.js`:

```javascript
output: 'standalone',
```

---

## Phase 2 — Product Messaging & Landing Page Rewrite
**Effort: ~10 hours | Impact: +1.2 to overall score | Risk: Medium**

The #1 reason users won't convert is that the landing page doesn't explain what the problem is. "Visualizes Python execution step-by-step" sounds like Python Tutor. The actual value is: **"Understand the code your AI just wrote for you."**

### 2.1 Rewrite the Landing Page Hero
**File:** `frontend/app/page.tsx`
**Time:** 3 hours

The current hero is generic. Replace with problem-first messaging:

```tsx
// BEFORE (generic):
<h1>See exactly what your AI-generated code does</h1>
<p>Paste code. Watch it run. Understand why it works.</p>

// AFTER (problem-first):
<h1>Pasted Copilot code. No idea why it's not working.</h1>
<p>
  CodeScope shows you exactly how AI-generated Python executes —
  which branches fire, which variables change, and why.
  Then it schedules reviews so you actually remember.
</p>
```

Key changes:
- Lead with the PROBLEM (AI code is opaque) not the FEATURE (visualization)
- Mention the specific audience: "AI-generated" not just "code"
- Include the three-pillar hook: execution + explanation + retention
- The `SAMPLE_CODE` on the page should be AI-generated code (not a fibonacci function)
- Add a "How it works" section with the three-step flow

### 2.2 Wire i18n Throughout the UI
**Files:** `frontend/app/page.tsx`, `frontend/app/tracer/page.tsx`, `frontend/app/dashboard/page.tsx`
**Time:** 4 hours

The i18n files exist but the UI has hardcoded strings. This is a differentiator — Vietnamese CS students are a real market.

```tsx
// BEFORE:
<h1>See exactly what your AI-generated code does</h1>
<button>Try CodeScope free</button>

// AFTER:
import { useTranslation } from 'react-i18next';
const { t } = useTranslation();

<h1>{t('landing.hero.title')}</h1>
<button>{t('landing.hero.cta')}</button>
```

Ensure `i18n.ts` is configured to detect browser language and fall back to `en`.

### 2.3 Build a Pricing Page
**File:** `frontend/app/pricing/page.tsx` (new)
**Time:** 2 hours

Pricing tiers are defined in `en.json` but there's no actual pricing page. Users need to understand the value before hitting limits.

```
/pricing
├── Free Plan (0$/mo)
│   ├── Unlimited static analysis
│   ├── 50 traces/month
│   └── 5 reviews/month
│
└── Pro Plan (15$/mo)
    ├── Everything in Free
    ├── Unlimited traces
    ├── Unlimited LLM explanations
    ├── Unlimited review queue
    └── Priority support
```

The upgrade trigger should NOT be a dead end — it should point to `/pricing`.

### 2.4 Add Usage Indicator to Dashboard
**File:** `frontend/app/dashboard/page.tsx`
**Time:** 1 hour

Users don't know how many traces they've used. Show a progress bar:

```
Traces this month: 23 / 50
███████░░░░░░░░░░░░░ 46%
```

This makes the conversion trigger visible and natural, not a wall.

---

## Phase 3 — Frontend Quality Polish
**Effort: ~12 hours | Impact: +0.8 to overall score | Risk: Low**

### 3.1 Fix Examples Page Dark Theme
**File:** `frontend/app/examples/page.module.css`
**Time:** 1 hour

Examples page uses a light theme that breaks immersion. The examples page should match the dark tracer aesthetic.

### 3.2 Replace Emoji Icons with Lucide
**Files:** `frontend/components/tracer/VariablePanel.tsx`, `frontend/components/tracer/AnimationControls.tsx`, `frontend/app/tracer/page.tsx`
**Time:** 2 hours

Emoji is not accessible (not all screen readers announce them correctly). Lucide React is already a dependency. Replace:

```tsx
// BEFORE:
<span>🔀</span> Branch
<span>📦</span> List

// AFTER:
import { GitBranch, List } from 'lucide-react';
<GitBranch size={14} /> Branch
<List size={14} /> List
```

### 3.3 Add Keyboard Focus Styles
**Files:** `frontend/app/globals.css`
**Time:** 1 hour

Zero `focus-visible` styles = invisible keyboard navigation.

```css
/* Global focus ring — WCAG 2.1 AA requirement */
:focus-visible {
  outline: 2px solid #6366f1;
  outline-offset: 2px;
  border-radius: 4px;
}

/* Remove default outline, apply only on keyboard nav */
:focus:not(:focus-visible) {
  outline: none;
}
```

### 3.4 Break Up tracer/page.tsx (526 lines → ~8 components)
**Files:** `frontend/app/tracer/page.tsx` split into smaller components
**Time:** 5 hours

The tracer page is too large. Extract:

| Component | Lines | File |
|---|---|---|
| `Toolbar` | ~80 | `frontend/components/tracer/Toolbar.tsx` |
| `ShareModal` | ~80 | `frontend/components/tracer/ShareModal.tsx` |
| `SaveModal` | ~60 | `frontend/components/tracer/SaveModal.tsx` |
| `TraceLayout` | ~60 | `frontend/components/tracer/TraceLayout.tsx` |
| `StatusBar` | ~30 | `frontend/components/tracer/StatusBar.tsx` |

The main `page.tsx` should be ~100 lines — just state management and composition.

### 3.5 Add Loading Skeletons
**Files:** `frontend/app/tracer/page.tsx`, `frontend/app/examples/page.tsx`
**Time:** 2 hours

Replace "Loading editor..." plain text with a proper skeleton:

```tsx
// Replace:
loading: () => <div>Loading editor...</div>,

// With:
loading: () => <CodeEditorSkeleton />,
```

Create `frontend/components/editor/CodeEditorSkeleton.tsx` with animated shimmer.

### 3.6 Responsive Layout for Tracer Page
**File:** `frontend/app/tracer/page.module.css`
**Time:** 1 hour

The 6:4 split doesn't work on tablet/mobile.

```css
/* Tablet */
@media (max-width: 1024px) {
  .main { flex-direction: column; }
  .editorPanel { flex: none; height: 50vh; }
  .sidePanel { flex: none; height: 50vh; }
}

/* Mobile */
@media (max-width: 768px) {
  .topBar { flex-wrap: wrap; gap: 8px; }
  .topBar > :last-child { width: 100%; justify-content: flex-end; }
  .editorPanel { height: 40vh; }
  .sidePanel { height: 60vh; }
}
```

---

## Phase 4 — Testing & CI/CD
**Effort: ~15 hours | Impact: +0.8 to overall score | Risk: Low**

### 4.1 Add Frontend Unit Tests to CI
**File:** `.github/workflows/ci.yml`
**Time:** 2 hours

Currently `npm test` (vitest) is absent from CI. Add it:

```yaml
frontend-test:
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-node@v4
      with:
        node-version: '22'
        cache: 'npm'
        cache-dependency-path: frontend/package-lock.json
    - run: cd frontend && npm ci
    - run: cd frontend && npm run type-check
    - run: cd frontend && npm test -- --coverage  # ← ADD THIS
    - run: cd frontend && npm run build
```

### 4.2 Add Component Unit Tests
**Files:** `frontend/__tests__/VariablePanel.test.tsx`, `frontend/__tests__/AnimationControls.test.tsx`, `frontend/__tests__/ExplanationPanel.test.tsx` (replace)
**Time:** 6 hours

Each component needs at minimum:
- Renders correctly with given props
- Loading state renders
- Error state renders
- Empty state renders (where applicable)

The existing `ExplanationPanel.test.tsx` uses shallow mocks — replace with proper testing:

```tsx
// Test that explanation streams correctly
// Test that rating buttons appear after explanation completes
// Test that errors are displayed gracefully
```

### 4.3 Fix E2E Test Environment
**Files:** `frontend/e2e/examples.spec.ts`, `frontend/e2e/review.spec.ts`
**Time:** 3 hours

4 tests failing because backend isn't running in test environment. Fix by:

1. Starting backend service in Playwright CI setup
2. Using `webServer` config in `playwright.config.ts`
3. Adding `baseURL` to ensure tests hit the right backend

```typescript
// playwright.config.ts
webServer: {
  command: 'cd ../backend && uvicorn app.main:app --port 8000',
  url: 'http://localhost:8000/health',
  reuseExistingServer: !process.env.CI,
  timeout: 120 * 1000,
},
```

### 4.4 Add Backend Integration Tests
**Files:** `backend/tests/integration/test_traces_api.py` (new)
**Time:** 4 hours

Current backend tests are unit tests. Add integration tests that test the full HTTP round-trip:

```python
# Test: POST /traces/run with valid code returns 200
# Test: POST /traces/run with timeout code returns 408
# Test: POST /traces/run with side-effect code returns 422
# Test: GET /traces/shared/{token} with password returns 401 without password
# Test: GET /traces/shared/{token} with wrong password returns 401
# Test: POST /traces/{id}/share creates share_token
# Test: POST /traces/shared/{token}/fork copies trace to authenticated user
```

Use `pytest-asyncio` with a test Supabase instance or mock the httpx calls.

---

## Phase 5 — Feature Completion
**Effort: ~20 hours | Impact: +0.7 to overall score | Risk: Medium**

### 5.1 Verify & Wire LLM Explanation Backend
**Files:** `backend/app/routers/llm.py`, `frontend/components/llm/ExplanationPanel.tsx`
**Time:** 4 hours

The ExplanationPanel exists in the UI but the backend streaming endpoint may not be fully wired. Verify and fix:

1. `POST /llm/explain/stream` endpoint exists and returns SSE
2. Frontend `useStreamingExplanation` hook connects to it
3. The "Why is this here?" button actually produces streaming explanations
4. LLM explanations are grounded in execution state (line + variables + branch)

### 5.2 Wire What-If Sandbox End-to-End
**Files:** `backend/app/routers/traces.py`, `backend/tracer/tracer.py`, `backend/tracer/runner.py`, `frontend/components/tracer/WhatIfModal.tsx`
**Time:** 6 hours

The `FEATURE-IMPLEMENTATION-PLAN.md` already has the implementation plan for this. The backend needs:

1. `TraceRequest` model accepts `initial_namespace`
2. `run_trace()` in tracer.py accepts `initial_namespace`
3. `runner.py` passes it through subprocess
4. Frontend `WhatIfModal` wires to `runTrace(code, { initialNamespace })`

### 5.3 Complete Shared Trace Links Features
**Files:** `backend/app/routers/traces.py`, `frontend/app/trace/[share_token]/page.tsx`
**Time:** 5 hours

1. Add password protection (bcrypt hash check on GET)
2. Add expiration (410 Gone response for expired links)
3. Add Fork button for authenticated users on shared page
4. Add analytics logging for shared views
5. Add Open Graph meta tags for social sharing

### 5.4 Static Analysis Pattern Completeness
**File:** `backend/analyzers/static_analysis.py`
**Time:** 3 hours

Currently 5 of 10 planned patterns. Add the remaining 5:

```python
# Add these 5 patterns:
"float_equality": {"severity": "error", "message": "Direct == comparison on floats may fail due to precision. Use math.isclose()."},
"chain_comparison": {"severity": "warning", "message": "Chain comparison needs parentheses for clarity."},
"unguarded_open": {"severity": "warning", "message": "open() without a context manager or explicit close() may leak file descriptors."},
"missing_timeout": {"severity": "info", "message": "No timeout set on potentially slow operation."},
"implicit_dict_iteration": {"severity": "info", "message": "Implicit iteration over dict values — consider explicit .values() for clarity."},
```

### 5.5 Seed Curated Example Library
**Files:** `backend/app/routers/examples.py`, Supabase database
**Time:** 2 hours

The examples page exists but needs real content. Seed 20-30 examples across categories:

| Category | Count | Examples |
|---|---|---|
| List Comprehensions | 5 | `[(x, y) for x in ... for y in ...]` nested, conditional comps, etc. |
| None Handling | 4 | `if x:` vs `if x is not None:`, chained comparisons |
| Async/Await | 4 | missing `await`, fire-and-forget, concurrent.gather patterns |
| Decorators | 3 | @staticmethod vs @classmethod, functools.wraps, stacking |
| OOP | 4 | `__init__` vs class variables, mutable defaults, `super()` |

---

## Phase 6 — Observability & Production Readiness
**Effort: ~8 hours | Impact: +0.5 to overall score | Risk: Low**

### 6.1 Add Request IDs / Correlation IDs
**Files:** `backend/app/main.py`, all routers
**Time:** 2 hours

Every request should have a correlation ID for distributed tracing:

```python
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
```

Log with request_id: `logger.info("trace_saved", extra={"request_id": request.state.request_id, ...})`

### 6.2 Add Health Check for All Dependencies
**File:** `backend/app/main.py`
**Time:** 2 hours

Expand `/health` to check Redis and Supabase:

```python
@app.get("/health")
async def health_check():
    checks = {
        "api": "ok",
        "redis": await check_redis(),
        "supabase": await check_supabase(),
    }
    status = 200 if all(v == "ok" for v in checks.values()) else 503
    return JSONResponse({"status": "ok" if status == 200 else "degraded", "checks": checks})
```

### 6.3 Remove Debug Logging from Production
**Files:** `frontend/lib/api.ts`, `backend/app/routers/auth.py`, `backend/app/routers/traces.py`
**Time:** 1 hour

```typescript
// frontend/lib/api.ts — remove all console.log
// BEFORE:
console.log('[DEBUG] authFetch token:', token ? `${token.substring(0, 30)}...` : 'NULL');

// AFTER: (nothing — debug logs should use a debug flag)
if (process.env.NODE_ENV === 'development') {
  console.log('[DEBUG] ...');
}
```

### 6.4 Add API Documentation
**Files:** `backend/app/docs/API.md` (new)
**Time:** 3 hours

Document all API endpoints with:
- Method, path, description
- Request body schema
- Response schema
- Error codes
- Authentication requirements
- Rate limits

Use OpenAPI/Swagger at `/docs` as the primary reference, but create a `API.md` for non-technical stakeholders.

---

## Phase 7 — Documentation & Onboarding
**Effort: ~6 hours | Impact: +0.3 to overall score | Risk: Low**

### 7.1 Create CONTRIBUTING.md
**File:** `CONTRIBUTING.md` (new)
**Time:** 2 hours

```markdown
# Contributing to CodeScope

## Dev Setup
1. Clone the repo
2. Copy `.env.example` to `.env` and fill in values
3. Run `docker compose up --build`
4. Frontend: http://localhost:3000
5. Backend: http://localhost:8000/docs

## Running Tests
- Backend: `cd backend && pytest tests/ -v`
- Frontend unit: `cd frontend && npm test`
- Frontend E2E: `cd frontend && npx playwright test`

## Code Style
- Python: `ruff check . && ruff format .`
- TypeScript: `cd frontend && npm run lint`

## Submitting Changes
1. Create a branch: `git checkout -b feature/my-feature`
2. Run all tests
3. Open a PR with description
```

### 7.2 Create .env.example
**File:** `backend/.env.example`, `frontend/.env.example` (new)
**Time:** 1 hour

Both are missing. Document every required and optional variable.

### 7.3 Create Deployment Guide
**File:** `DEPLOYMENT.md` (new)
**Time:** 3 hours

Step-by-step deployment to:
- Vercel (frontend)
- Railway (backend)
- Supabase (database)
- Redis (Upstash for production)

Include:
- Environment variables for each service
- Health check endpoint verification
- Database migration process
- Rollback procedure

---

## Effort Summary & Ordering

| Phase | Hours | Score Impact | Risk | Priority |
|---|---|---|---|---|
| Phase 1: Security & DevOps | 15 | +1.5 | Low | 🔴 P0 |
| Phase 4: Testing & CI | 15 | +0.8 | Low | 🔴 P0 |
| Phase 2: Product Messaging | 10 | +1.2 | Medium | 🟠 P1 |
| Phase 5: Feature Completion | 20 | +0.7 | Medium | 🟠 P1 |
| Phase 3: Frontend Polish | 12 | +0.8 | Low | 🟡 P2 |
| Phase 6: Observability | 8 | +0.5 | Low | 🟡 P2 |
| Phase 7: Documentation | 6 | +0.3 | Low | 🟡 P3 |
| **Total** | **86 hours** | **+5.8** | | |

**Total theoretical score: 6.5 + 5.8 = 12.3** — impossible because some dimensions max at 10. Realistic ceiling after all phases: **9.0-9.2**

---

## Dependency Graph

```
Phase 1 (Security)  ──► Phase 6 (Observability)
      │
      ▼
Phase 4 (Testing CI) ──► Phase 5 (Feature Completion)
      │                        │
      │                        │
      ▼                        ▼
Phase 3 (Frontend)  ◄─────────┘
      │
      ▼
Phase 2 (Product Messaging)
      │
      ▼
Phase 7 (Documentation)
```

**Parallel tracks (can run concurrently):**
- Phase 1 (Security) + Phase 4 (Testing CI)
- Phase 3 (Frontend Polish) can start immediately — no dependencies
- Phase 5 (Feature Completion) needs Phase 1 done first (clean codebase)

---

## Weekly Execution Plan

### Week 1 — Security Foundation
- Days 1-2: Fix docker-compose secrets, CORS, `get_profile_id` bug
- Days 3-4: Add rate limiting to traces/run + auth endpoints
- Days 5: Docker production hardening (restart policies, .dockerignore)

### Week 2 — Testing + Observability
- Days 1-2: Add `npm test` to CI, fix E2E test environment
- Days 3-4: Write VariablePanel + AnimationControls unit tests
- Day 5: Add request IDs, expand health check, remove debug logs

### Week 3 — Feature Completion
- Days 1-2: Verify + wire LLM explanation backend end-to-end
- Days 3-4: Wire What-If sandbox (backend + frontend)
- Day 5: Complete shared trace links (password, expiry, fork)

### Week 4 — Frontend Polish
- Days 1-2: Break up tracer/page.tsx into 5 components
- Days 3: Fix examples page dark theme, add loading skeletons
- Days 4-5: Add keyboard focus styles, responsive layout

### Week 5 — Product & Docs
- Days 1-2: Rewrite landing page hero, wire i18n
- Days 3: Build pricing page + usage indicator
- Days 4: Add 5 missing static analysis patterns, seed examples
- Days 5: Write CONTRIBUTING.md, .env.example, DEPLOYMENT.md

### Buffer Week (Week 6) — Integration & Polish
- Fix any broken integrations discovered during E2E testing
- Run full test suite across all platforms
- Do a final security audit pass
- Performance audit: lighthouse score check
- Cross-browser testing (Chrome, Firefox, Safari)

---

## Success Criteria

After completing all phases, the project should:

| Check | Target |
|---|---|
| Lighthouse Performance | ≥ 90 |
| Lighthouse Accessibility | ≥ 90 |
| Frontend test coverage | ≥ 60% |
| Backend test coverage | ≥ 85% |
| E2E test pass rate | 100% |
| Security: no hardcoded secrets | ✅ |
| Security: CORS configured for prod | ✅ |
| Security: rate limits on all endpoints | ✅ |
| Product: landing page problem-first | ✅ |
| Product: pricing page exists | ✅ |
| Product: i18n wired | ✅ |
| Product: What-If fully functional | ✅ |
| Product: shared trace links complete | ✅ |
| **Overall score** | **≥ 9.0** |
