---
name: codescope-round4-impl
description: Implements CodeScope Round 4 features (Shared Trace Links, What-If Sandbox, Trace Replay from Saved State). Extends the existing codescope-impl skill. Use when building Feature 1 (Shared Trace Links), Feature 3 (What-If Sandbox), or Feature 5 (Trace Replay) from FEATURE-IMPLEMENTATION-PLAN.md. Requires the Phase 1-4 codebase to already exist.
---

# CodeScope Round 4 — Implementation Skill

## Prerequisites

**This skill MUST be used after `codescope-impl` is complete.**
Run `codescope-impl` first if the tracer, frontend, and AI explanation layers do not yet exist.

Before starting, verify the existing codebase:

```bash
# Backend should be runnable
cd C:\Users\quoct\codescope\backend
python -m uvicorn app.main:app --port 8000 &
# Then: curl -s -X POST http://localhost:8000/api/traces/run -H "Content-Type: application/json" -d "{\"code\": \"x = 1\"}"

# Frontend should build
cd C:\Users\quoct\codescope\frontend
npm run build
```

If either fails, complete the `codescope-impl` skill first.

## Golden Rule

**Never skip steps. Never combine steps. Complete each phase before the next.**
Tasks within a phase can be done in parallel, but phases must be completed in order.

## Quick Reference

| Item | Value |
|------|-------|
| Project root | `C:\Users\quoct\codescope\` |
| Backend | `C:\Users\quoct\codescope\backend\` |
| Frontend | `C:\Users\quoct\codescope\frontend\` |
| Feature spec | `C:\Users\quoct\codescope\FEATURE-IMPLEMENTATION-PLAN.md` |

## Phase Dependency Graph

```
Phase DB (DB-1 → DB-2)         ← Run these first, in order
    ↓
Phase 1C (backend: save steps) ← DB-1 must be complete
    ↓
Phase 1B (backend: share API)  ← DB-2 + 1C must be complete
    ↓
Phase 3A (backend: initial_ns) ← Can start anytime (independent)
Phase 3B (backend: runner ns)  ← Depends on 3A
Phase 3C (backend: API ns)     ← Depends on 3B
Phase 5B (backend: review ret)  ← DB-1 must be complete
    ↓
Phase 1D (frontend: share btn) ← 1B must be complete
    ↓
Phase 1E (frontend: shared pg) ← 1B + 1D must be complete
Phase 1F (frontend: OG tags)  ← 1E must be complete
Phase 3D (frontend: modal)     ← 3C must be complete
    ↓
Phase 3E (frontend: wire WhatIf) ← 3D must be complete
Phase 5A (frontend: useTrace in review) ← DB-1 must be complete
```

---

## Phase DB: Database Migrations

### TASK DB-1: Apply Supabase Migrations

**Run these SQL statements in your Supabase SQL editor (supabase.com → project → SQL Editor).**

**IMPORTANT:** Run migration DB-1 and DB-2 as separate statements. Each must succeed before proceeding.

```sql
-- MIGRATION DB-1: Save full trace steps in traces table
-- Required by: Shared Trace Links (Feature 1) and Trace Replay (Feature 5)

ALTER TABLE traces ADD COLUMN IF NOT EXISTS steps JSONB NOT NULL DEFAULT '[]'::jsonb;
```

```sql
-- MIGRATION DB-2: Shared Trace Link Enhancements
-- Adds: expiration, password, analytics tracking

-- 1. Add columns to traces table
ALTER TABLE traces ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE traces ADD COLUMN IF NOT EXISTS password_hash TEXT;

-- 2. Share analytics table
CREATE TABLE IF NOT EXISTS share_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    share_token TEXT NOT NULL,
    viewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    viewer_ip_hash TEXT,
    referrer TEXT,
    is_authenticated BOOLEAN NOT NULL DEFAULT false,
    forked BOOLEAN NOT NULL DEFAULT false,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for fast lookups by share_token
CREATE INDEX IF NOT EXISTS idx_share_analytics_token ON share_analytics(share_token);
CREATE INDEX IF NOT EXISTS idx_share_analytics_viewed ON share_analytics(share_token, viewed_at DESC);
```

**Verification:** After running both migrations, run this query:

```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'traces'
ORDER BY column_name;
```

Expected columns must include: `steps` (jsonb), `expires_at` (timestamptz), `password_hash` (text).

---

## Phase 1C: Backend — Save Steps in DB

### TASK 1C-1: Update `SaveTraceRequest` to include `steps`

**File:** `backend/app/routers/traces.py`

**Find this class definition (around line 254):**

```python
class SaveTraceRequest(BaseModel):
    code: str
    language: str = "python"
    steps: list[dict] = []
    concept_tags: list[str] = []
    is_public: bool = False
```

**Replace the entire `steps` field with:**

```python
    steps: list[dict] = Field(
        default_factory=list,
        description="Full trace steps array for replay. Stored in DB so saved traces can be replayed without re-execution.",
    )
```

**Find the `trace_data` dict (around line 289) and add `steps`:**

```python
    trace_data = {
        "user_id": user_id,
        "code": req.code,
        "language": req.language if req.language else "python",
        "concept_tags": req.concept_tags if req.concept_tags else [],
        "is_public": req.is_public if req.is_public is not None else False,
        "share_token": share_token,
        "steps": req.steps if req.steps else [],  # ← SAVE FULL STEPS for replay
    }
```

**Verification:** Trace the backend (`python -m uvicorn app.main:app --port 8000`) and run:

```bash
curl -s -X POST http://localhost:8000/api/traces \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <your_token>" \
  -d '{"code": "x = 1", "steps": [{"step_number": 0, "line_number": 1}]}'
```

The response must include `"steps"` in the stored trace. (You can verify by checking the traces table directly in Supabase.)

---

## Phase 1B: Backend — Share Endpoint with Expiry and Password

### TASK 1B-1: Add bcrypt import

**File:** `backend/app/routers/traces.py`

**Find the existing imports at the top of the file and add `bcrypt`:**

```python
import bcrypt
```

### TASK 1B-2: Add `ShareTraceRequest` model

**Find `class SaveTraceRequest(BaseModel):` and add the following class AFTER it (before the next class or route):**

```python
class ShareTraceRequest(BaseModel):
    """Request body for POST /traces/{id}/share."""
    expiration_days: int | None = Field(
        default=None,
        ge=0,
        le=365,
        description="Days until link expires. null/0 = never.",
    )
    password: str | None = Field(
        default=None,
        max_length=128,
        description="Optional password to protect the shared link.",
    )
```

### TASK 1B-3: Replace `POST /traces/{trace_id}/share` endpoint

**Find and replace the entire `share_trace` endpoint function (starts around `@router.post("/traces/{trace_id}/share")`):**

```python
@router.post("/traces/{trace_id}/share")
async def share_trace(
    trace_id: str,
    req: ShareTraceRequest | None = None,
    authorization: str = Header(None),
):
    """
    Generate or update a share link for a trace.
    Sets is_public=true and generates a new share_token.

    Body (optional):
      - expiration_days: int | null — days until expiry (null/0 = never)
      - password: str | null — optional protection password
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")

    settings = Settings()
    share_token = secrets.token_hex(16)

    # Build update payload
    update_payload: dict = {
        "share_token": share_token,
        "is_public": True,
    }

    # Handle expiration
    if req and req.expiration_days and req.expiration_days > 0:
        from datetime import datetime, timedelta, timezone
        expires = datetime.now(timezone.utc) + timedelta(days=req.expiration_days)
        update_payload["expires_at"] = expires.isoformat()
    else:
        update_payload["expires_at"] = None

    # Handle password protection
    if req and req.password:
        hashed = bcrypt.hashpw(req.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        update_payload["password_hash"] = hashed
    else:
        update_payload["password_hash"] = None

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Verify the trace belongs to this user first
        user = await get_current_user(authorization)
        user_id = user.get("id", "")

        check_resp = await client.get(
            f"{settings.supabase_url}/rest/v1/traces",
            params={"id": f"eq.{trace_id}", "user_id": f"eq.{user_id}", "select": "id"},
            headers={
                "Authorization": f"Bearer {authorization[7:]}",
                "apikey": settings.supabase_service_key,
            },
        )
        if check_resp.status_code != 200 or not check_resp.json():
            raise HTTPException(status_code=404, detail="Trace not found")

        resp = await client.patch(
            f"{settings.supabase_url}/rest/v1/traces",
            params={"id": f"eq.{trace_id}"},
            headers={
                "Authorization": f"Bearer {authorization[7:]}",
                "apikey": settings.supabase_service_key,
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json=update_payload,
        )

    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail="Trace not found")

    return {
        "share_token": share_token,
        "share_url": f"/trace/{share_token}",
        "expires_at": update_payload.get("expires_at"),
        "has_password": bool(req and req.password),
    }
```

### TASK 1B-4: Update `GET /traces/shared/{share_token}` for expiry + password + analytics

**Find and replace the `get_shared_trace` endpoint (starts around `@router.get("/traces/shared/{share_token}")`):**

```python
@router.get("/traces/shared/{share_token}")
async def get_shared_trace(
    share_token: str,
    password: str | None = None,
):
    """
    Get a trace by its share token. Public endpoint.

    Returns:
      - 200: trace data (or 401 if password required)
      - 404: trace not found
      - 410: link has expired

    Query params:
      - password: str | null — required if link is password-protected
    """
    settings = Settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/traces",
            params={
                "share_token": f"eq.{share_token}",
                "is_public": "eq.true",
                "select": "*",
            },
            headers={"apikey": settings.supabase_service_key},
        )

    traces = resp.json() if resp.status_code == 200 else []
    if not traces:
        raise HTTPException(status_code=404, detail="Trace not found")

    trace = traces[0]

    # Check expiration
    expires_at = trace.get("expires_at")
    if expires_at:
        from datetime import datetime, timezone
        try:
            exp_date = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > exp_date:
                raise HTTPException(
                    status_code=410,
                    detail={
                        "error": "EXPIRED",
                        "message": "This trace has expired. Sign in to CodeScope to view it.",
                        "login_url": "/auth/login",
                    },
                )
        except ValueError:
            pass  # Invalid date format — treat as not expired

    # Check password
    password_hash = trace.get("password_hash")
    if password_hash:
        if not password:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "PASSWORD_REQUIRED",
                    "message": "This trace is password-protected. Pass ?password=... to verify.",
                },
            )
        if not bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8")):
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "WRONG_PASSWORD",
                    "message": "Incorrect password.",
                },
            )

    # Log analytics (non-blocking — don't fail the request if this errors)
    try:
        from datetime import datetime, timezone
        async with httpx.AsyncClient(timeout=3.0) as analytic_client:
            await analytic_client.post(
                f"{settings.supabase_url}/rest/v1/share_analytics",
                headers={
                    "Authorization": f"Bearer {settings.supabase_service_key}",
                    "apikey": settings.supabase_service_key,
                    "Content-Type": "application/json",
                },
                json={
                    "share_token": share_token,
                    "viewed_at": datetime.now(timezone.utc).isoformat(),
                    "viewer_ip_hash": "hashed_in_production",
                    "is_authenticated": False,
                    "forked": False,
                },
            )
    except Exception:
        pass  # Non-blocking

    # Return trace data (exclude password_hash from client response)
    result = {k: v for k, v in trace.items() if k != "password_hash"}
    return result
```

### TASK 1B-5: Add Fork endpoint

**Add this endpoint AFTER the `get_shared_trace` endpoint:**

```python
class ForkTraceResponse(BaseModel):
    trace_id: str
    share_token: str
    share_url: str


@router.post("/traces/shared/{share_token}/fork")
async def fork_shared_trace(
    share_token: str,
    authorization: str = Header(None),
):
    """
    Fork a shared trace — copies it into the authenticated user's account.
    The fork is a NEW trace owned by the caller, independent of the original.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")

    settings = Settings()
    user = await get_current_user(authorization)
    user_id = user.get("id", "")

    # Get the original trace
    async with httpx.AsyncClient(timeout=10.0) as client:
        orig_resp = await client.get(
            f"{settings.supabase_url}/rest/v1/traces",
            params={"share_token": f"eq.{share_token}", "select": "*"},
            headers={"apikey": settings.supabase_service_key},
        )

    orig_traces = orig_resp.json() if orig_resp.status_code == 200 else []
    if not orig_traces:
        raise HTTPException(status_code=404, detail="Shared trace not found")

    orig = orig_traces[0]

    # Create fork — new user_id, new share_token, same code + steps
    new_share_token = secrets.token_hex(16)
    fork_data = {
        "user_id": user_id,
        "code": orig.get("code", ""),
        "language": orig.get("language", "python"),
        "concept_tags": orig.get("concept_tags", []),
        "is_public": False,
        "share_token": new_share_token,
        "steps": orig.get("steps"),
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        fork_resp = await client.post(
            f"{settings.supabase_url}/rest/v1/traces",
            headers={
                "Authorization": f"Bearer {settings.supabase_service_key}",
                "apikey": settings.supabase_service_key,
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            json=fork_data,
        )

    if fork_resp.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail="Failed to fork trace")

    fork = fork_resp.json()
    if isinstance(fork, list) and len(fork) > 0:
        fork = fork[0]

    logger.info("trace_forked", extra={
        "original_token": share_token,
        "new_trace_id": fork.get("id", ""),
        "user_id": user_id,
    })

    return ForkTraceResponse(
        trace_id=fork.get("id", ""),
        share_token=new_share_token,
        share_url=f"/trace/{new_share_token}",
    )
```

**Verification:** Run the backend and test:

```bash
# Start server first
cd C:\Users\quoct\codescope\backend
python -m uvicorn app.main:app --port 8000

# Test 1: Create a trace with steps (requires auth — skip if no token)
# Test 2: GET shared trace (public, should return 200 or 404)
curl -s http://localhost:8000/api/traces/shared/nonexistent_token

# Expected: 404 with "Trace not found"
```

---

## Phase 3A: Backend — Accept `initial_namespace` in Tracer

### TASK 3A-1: Update `run_trace` signature in tracer.py

**File:** `backend/tracer/tracer.py`

**Find `def run_trace(source: str, max_steps: int = 500) -> dict:` and replace the entire function signature and docstring with:**

```python
def run_trace(
    source: str,
    max_steps: int = 500,
    initial_namespace: dict | None = None,
) -> dict:
    """
    Execute Python source code with step-by-step tracing.

    Args:
        source: Python source code string.
        max_steps: Maximum number of trace steps (default 500).
        initial_namespace: Optional dict of variable names → values to pre-populate
                          the execution namespace before code runs.
                          Values are evaluated as Python literals.
                          Example: {"items": [1, 2, 3], "threshold": 10}
    """
```

**Find `namespace: dict = {}` (after `start_time = time.perf_counter()`) and replace with:**

```python
    # Pre-populate namespace from initial_namespace if provided
    namespace: dict = {}
    if initial_namespace:
        for name, raw_val in initial_namespace.items():
            try:
                val = eval(repr(raw_val), {"__builtins__": {"True": True, "False": False, "None": None}})
                namespace[name] = val
            except Exception:
                pass  # Silently skip invalid initial values
```

**Find the `_capture_variables` function and add at the very end (before `return variables`):**

```python
    # Add initial namespace variables that haven't appeared in any frame yet
    # (they exist at step 0 before the code runs)
    for name, val in namespace.items():
        if name in _INTERNAL_NAMES or _is_internal_variable(name):
            continue
        if name not in variables:
            prev_repr = prev_variables.get(name, None)
            curr_repr = repr(val)[:200]
            variables[name] = VariableInfo(
                type=type(val).__name__,
                value=curr_repr,
                changed=(prev_repr is not None) and (curr_repr != prev_repr),
            )
```

**Verification:** Run in Python shell:

```python
import sys; sys.path.insert(0, 'C:/Users/quoct/codescope/backend')
from tracer.tracer import run_trace

# Test 1: Without initial_namespace
r1 = run_trace("x = 1")
print("Without ns — steps:", r1.get("total_steps"), "error:", r1.get("error", "none"))

# Test 2: With initial_namespace
r2 = run_trace("x = x + 1", initial_namespace={"x": 5})
print("With ns (x=5) — error:", r2.get("error", "none"))
# Expected: x should start at 5, result should be 6
```

---

## Phase 3B: Backend — Pass `initial_namespace` Through Subprocess

### TASK 3B-1: Update runner.py `run_trace` function

**File:** `backend/tracer/runner.py`

**Read the current `run_trace` function first to find its exact structure.**

**Replace the entire `run_trace` function with:**

```python
def run_trace(
    source: str,
    max_steps: int = 500,
    initial_namespace: dict | None = None,
    timeout_seconds: int = 5,
) -> dict:
    """
    Execute user code in an isolated subprocess with tracing.

    Args:
        source: Python source code string.
        max_steps: Maximum number of trace steps (default 500).
        initial_namespace: Optional pre-populated variable namespace dict.
        timeout_seconds: Execution timeout in seconds (default 5).

    Returns:
        dict with keys: steps (list), total_steps (int), duration_ms (float),
                        and optionally error (str), error_message (str)
    """
    import json
    import os
    import sys
    import tempfile

    # Serialize initial_namespace to JSON for passing to subprocess
    ns_json = json.dumps(initial_namespace or {})

    # Build the trace script
    trace_script = f'''
import sys
import json
from tracer.tracer import run_trace

ns_json = {repr(ns_json)}
initial_namespace = json.loads(ns_json) if ns_json != "null" else None

result = run_trace({repr(source)}, max_steps={max_steps}, initial_namespace=initial_namespace)
print("__RESULT_START__")
print(json.dumps(result))
print("__RESULT_END__")
'''

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        delete=False,
        encoding="utf-8",
    ) as f:
        f.write(trace_script)
        script_path = f.name

    try:
        proc = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            stdout, stderr = proc.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return {
                "error": "TIMEOUT",
                "message": f"Execution timed out after {timeout_seconds} seconds",
            }

        # Decode output
        stdout_text = stdout.decode("utf-8", errors="replace").strip()
        stderr_text = stderr.decode("utf-8", errors="replace").strip()

        if "__RESULT_START__" in stdout_text:
            json_str = stdout_text.split("__RESULT_START__")[1].split("__RESULT_END__")[0].strip()
            return json.loads(json_str)
        elif proc.returncode != 0:
            return {
                "error": "EXECUTION_ERROR",
                "message": stderr_text or "Unknown execution error",
            }
        else:
            return {
                "error": "PARSE_ERROR",
                "message": "Could not parse trace output",
                "raw_output": stdout_text[:500],
            }
    except Exception as e:
        return {
            "error": "SANDBOX_ERROR",
            "message": str(e),
        }
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass
```

**Verification:** Run in Python shell:

```python
import sys; sys.path.insert(0, 'C:/Users/quoct/codescope/backend')
from tracer.runner import run_trace

r = run_trace("x = x + 1", initial_namespace={"x": 5})
print("With ns — error:", r.get("error", "none"))
print("Steps:", r.get("total_steps", 0))
# If error is "none", the namespace was correctly injected
```

---

## Phase 3C: Backend — Accept `initial_namespace` in API

### TASK 3C-1: Update `TraceRequest` model

**File:** `backend/app/routers/traces.py`

**Find `class TraceRequest(BaseModel):` and replace with:**

```python
class TraceRequest(BaseModel):
    """Request body for /api/traces/run."""
    code: str = Field(..., max_length=5000, description="Python source code to trace")
    initial_namespace: dict[str, str] | None = Field(
        default=None,
        description=(
            "Optional initial variable values as name→string pairs. "
            "Values are evaluated as Python literals. "
            "Example: {\"items\": \"[1, 2, 3]\", \"threshold\": \"10\"}"
        ),
    )
```

### TASK 3C-2: Update `run_trace` endpoint to parse and pass `initial_namespace`

**Find `result = run_trace_subprocess(req.code, max_steps=500)` in the `POST /traces/run` endpoint and replace with:**

```python
    # Parse initial_namespace values from strings to Python values
    initial_ns = None
    if req.initial_namespace:
        initial_ns = {}
        for name, val_str in req.initial_namespace.items():
            try:
                initial_ns[name] = eval(val_str, {"__builtins__": {"True": True, "False": False, "None": None}})
            except Exception:
                pass  # Skip invalid values

    result = run_trace_subprocess(req.code, max_steps=500, initial_namespace=initial_ns)
```

**Verification:**

```bash
# Test without initial_namespace (should still work)
curl -s -X POST http://localhost:8000/api/traces/run \
  -H "Content-Type: application/json" \
  -d '{"code": "x = 1"}'
# Expected: returns steps

# Test with initial_namespace
curl -s -X POST http://localhost:8000/api/traces/run \
  -H "Content-Type: application/json" \
  -d '{"code": "x = x + 1", "initial_namespace": {"x": "5"}}'
# Expected: x starts at 5, ends at 6
```

---

## Phase 5B: Backend — Verify Review Endpoint Returns Steps

### TASK 5B-1: Verify `GET /review/{card_id}` returns steps

**File:** `backend/app/routers/review.py`

**Find the `get_review_card` endpoint and verify this line exists:**

```python
steps = json.loads(trace_data.get("steps", "[]")) if trace_data.get("steps") else []
```

This line should already exist. If it does, **no changes needed** — the endpoint will automatically return steps because the `traces.steps` column now exists (DB-1 migration).

**Verification:** Save a trace with steps in the DB, then load a review card:

```bash
# Save a trace with steps (requires auth)
# Then get the card
curl -s http://localhost:8000/api/review/<card_id> \
  -H "Authorization: Bearer <token>"
# Expected: response includes trace.steps array (non-empty)
```

---

## Phase 1D: Frontend — Share Button + Modal

### TASK 1D-1: Update `frontend/lib/api.ts` — Add options to `shareTrace`

**File:** `frontend/lib/api.ts`

**Find the `shareTrace` function and replace with:**

```typescript
export async function shareTrace(
  traceId: string,
  options?: {
    expiration_days?: number;
    password?: string;
  }
): Promise<{
  share_token: string;
  share_url: string;
  expires_at: string | null;
  has_password: boolean;
}> {
  const body: Record<string, unknown> = {};
  if (options?.expiration_days !== undefined) {
    body.expiration_days = options.expiration_days;
  }
  if (options?.password) {
    body.password = options.password;
  }
  const res = await authFetch(`${getApiBase()}/traces/${traceId}/share`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.status === 401) throw new Error("AUTH_REQUIRED");
  if (!res.ok) throw new Error(`Failed to generate share link: ${res.status}`);
  return res.json();
}
```

### TASK 1D-2: Update `frontend/lib/api.ts` — Add `initialNamespace` option to `runTrace`

**Find the standalone `runTrace` function (the one at the bottom of the file) and replace with:**

```typescript
export async function runTrace(
  code: string,
  options?: {
    initialNamespace?: Record<string, string>;
  }
): Promise<{
  trace_id: string;
  steps: TraceStep[];
  total_steps: number;
  duration_ms: number;
  error?: string;
  error_message?: string;
}> {
  const body: Record<string, unknown> = { code };
  if (options?.initialNamespace) {
    body.initial_namespace = options.initialNamespace;
  }
  const res = await fetch(`${getApiBase()}/traces/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Unknown error" }));
    throw new Error(err.detail?.error ?? err.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}
```

### TASK 1D-3: Add Share modal state to tracer page

**File:** `frontend/app/tracer/page.tsx`

**Find this line:**
```typescript
const [saveSuccess, setSaveSuccess] = useState(false);
```

**Add after it:**
```typescript
  const [showShareModal, setShowShareModal] = useState(false);
  const [shareResult, setShareResult] = useState<{
    share_token: string;
    share_url: string;
    expires_at: string | null;
    has_password: boolean;
  } | null>(null);
  const [shareError, setShareError] = useState<string | null>(null);
  const [isSharing, setIsSharing] = useState(false);
  const [sharePassword, setSharePassword] = useState("");
  const [expirationDays, setExpirationDays] = useState<number | null>(null);
```

**Find this import line:**
```typescript
import { api, saveTrace } from "@/lib/api";
```

**Replace with:**
```typescript
import { api, saveTrace, shareTrace } from "@/lib/api";
```

### TASK 1D-4: Add share handlers before the component function

**Find the line `// ── Check authentication on mount` and add BEFORE it:**

```typescript
  const handleShareClick = useCallback(() => {
    setShowShareModal(true);
    setShareResult(null);
    setShareError(null);
    setSharePassword("");
    setExpirationDays(null);
  }, []);

  const handleShareSubmit = useCallback(async () => {
    if (!traceResult?.trace_id) return;
    setIsSharing(true);
    setShareError(null);
    try {
      const result = await shareTrace(traceResult.trace_id, {
        expiration_days: expirationDays ?? undefined,
        password: sharePassword || undefined,
      });
      setShareResult(result);
    } catch (err) {
      setShareError(err instanceof Error ? err.message : "Failed to generate share link");
    } finally {
      setIsSharing(false);
    }
  }, [traceResult, expirationDays, sharePassword]);
```

### TASK 1D-5: Add Share button to toolbar

**Find this button:**
```tsx
<button className={styles.saveBtn} onClick={handleSaveTrace}
```

**Add BEFORE it:**
```tsx
          <button
            className={styles.shareBtn}
            onClick={handleShareClick}
            disabled={!traceResult}
            title={!traceResult ? "Run the trace first" : "Share this trace"}
          >
            🔗 Share
          </button>
```

### TASK 1D-6: Add Share Modal JSX before the footer

**Find `</main>` (closing the main element, around line 272) and add AFTER it, before the `<footer>`:**

```tsx
      {/* Share Modal */}
      {showShareModal && (
        <div className={styles.modalOverlay} onClick={() => setShowShareModal(false)}>
          <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
            <h2 className={styles.modalTitle}>Share Trace</h2>

            {!shareResult ? (
              <>
                <div className={styles.modalField}>
                  <label className={styles.modalLabel}>Expiration</label>
                  <select
                    className={styles.modalSelect}
                    value={expirationDays ?? ""}
                    onChange={(e) =>
                      setExpirationDays(e.target.value === "" ? null : Number(e.target.value))
                    }
                  >
                    <option value="">Never expires</option>
                    <option value="1">24 hours</option>
                    <option value="7">7 days</option>
                    <option value="30">30 days</option>
                    <option value="90">90 days</option>
                    <option value="365">1 year</option>
                  </select>
                </div>

                <div className={styles.modalField}>
                  <label className={styles.modalLabel}>Password (optional)</label>
                  <input
                    type="password"
                    className={styles.modalInput}
                    placeholder="Leave blank for no password"
                    value={sharePassword}
                    onChange={(e) => setSharePassword(e.target.value)}
                    maxLength={128}
                  />
                  <span className={styles.modalHint}>
                    Viewers must enter this password to access the trace.
                  </span>
                </div>

                {shareError && <div className={styles.modalError}>{shareError}</div>}

                <div className={styles.modalActions}>
                  <button
                    className={styles.modalCancelBtn}
                    onClick={() => setShowShareModal(false)}
                  >
                    Cancel
                  </button>
                  <button
                    className={styles.modalConfirmBtn}
                    onClick={handleShareSubmit}
                    disabled={isSharing}
                  >
                    {isSharing ? "Generating..." : "Generate Link"}
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className={styles.shareLinkBox}>
                  <input
                    type="text"
                    readOnly
                    className={styles.shareLinkInput}
                    value={
                      typeof window !== "undefined"
                        ? `${window.location.origin}${shareResult.share_url}`
                        : shareResult.share_url
                    }
                    onClick={(e) => (e.target as HTMLInputElement).select()}
                  />
                  <button
                    className={styles.copyBtn}
                    onClick={() => {
                      navigator.clipboard.writeText(
                        typeof window !== "undefined"
                          ? `${window.location.origin}${shareResult.share_url}`
                          : shareResult.share_url
                      );
                    }}
                  >
                    📋 Copy
                  </button>
                </div>
                {shareResult.has_password && (
                  <p className={styles.shareNote}>🔒 This link is password-protected.</p>
                )}
                {shareResult.expires_at && (
                  <p className={styles.shareNote}>
                    ⏱ Expires: {new Date(shareResult.expires_at).toLocaleDateString()}
                  </p>
                )}
                <div className={styles.modalActions}>
                  <button
                    className={styles.modalCancelBtn}
                    onClick={() => setShowShareModal(false)}
                  >
                    Done
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
```

### TASK 1D-7: Add Share modal CSS

**File:** `frontend/app/tracer/page.module.css`

**Append the following CSS classes:**

```css
/* Share button */
.shareBtn {
  padding: 8px 16px;
  background: #1e293b;
  color: #e2e8f0;
  border: 1px solid #334155;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.15s ease;
}
.shareBtn:hover:not(:disabled) { background: #334155; }
.shareBtn:disabled { opacity: 0.4; cursor: not-allowed; }

/* Modal overlay */
.modalOverlay {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.modal {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 16px;
  padding: 32px;
  width: 480px;
  max-width: 90vw;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.4);
}

.modalTitle {
  font-size: 20px; font-weight: 700;
  color: #f8fafc; margin: 0 0 24px 0;
}

.modalField { margin-bottom: 20px; }

.modalLabel {
  display: block; font-size: 14px; font-weight: 600;
  color: #cbd5e1; margin-bottom: 8px;
}

.modalSelect, .modalInput {
  width: 100%; padding: 10px 12px;
  background: #0f172a; border: 1px solid #334155;
  border-radius: 8px; color: #f8fafc; font-size: 14px;
  box-sizing: border-box;
}
.modalSelect:focus, .modalInput:focus { outline: none; border-color: #6366f1; }

.modalHint {
  display: block; font-size: 12px; color: #64748b; margin-top: 6px;
}

.modalError {
  padding: 10px 12px; background: #450a0a;
  border: 1px solid #991b1b; border-radius: 8px;
  color: #fca5a5; font-size: 14px; margin-bottom: 16px;
}

.modalActions {
  display: flex; gap: 12px; justify-content: flex-end; margin-top: 24px;
}

.modalCancelBtn {
  padding: 10px 20px; background: transparent;
  border: 1px solid #334155; border-radius: 8px;
  color: #94a3b8; cursor: pointer; font-size: 14px; font-weight: 500;
  transition: all 0.15s ease;
}
.modalCancelBtn:hover { background: #1e293b; color: #e2e8f0; }

.modalConfirmBtn {
  padding: 10px 20px; background: #6366f1; border: none;
  border-radius: 8px; color: white;
  cursor: pointer; font-size: 14px; font-weight: 600;
  transition: all 0.15s ease;
}
.modalConfirmBtn:hover:not(:disabled) { background: #4f46e5; }
.modalConfirmBtn:disabled { opacity: 0.5; cursor: not-allowed; }

/* Share link box */
.shareLinkBox { display: flex; gap: 8px; margin-bottom: 16px; }

.shareLinkInput {
  flex: 1; padding: 10px 12px;
  background: #0f172a; border: 1px solid #334155;
  border-radius: 8px;
  color: #22c55e; font-size: 13px;
  font-family: "Fira Code", "Courier New", monospace;
}

.copyBtn {
  padding: 10px 16px; background: #22c55e; border: none;
  border-radius: 8px; color: #052e16;
  cursor: pointer; font-size: 13px; font-weight: 600;
  white-space: nowrap;
}
.copyBtn:hover { background: #16a34a; }

.shareNote {
  font-size: 13px; color: #94a3b8; margin: 4px 0;
}
```

**Verification:**
```bash
cd C:\Users\quoct\codescope\frontend
npm run build
# Expected: build succeeds with 0 errors
```

---

## Phase 1E: Frontend — Update Shared Trace Page

### TASK 1E-1: Add `authFetch` import and Fork state to shared trace page

**File:** `frontend/app/trace/[share_token]/page.tsx`

**Find this import:**
```typescript
import { fetchSharedTrace, saveTrace } from "@/lib/api";
```

**Replace with:**
```typescript
import { fetchSharedTrace, saveTrace, authFetch } from "@/lib/api";
```

**Find this line:**
```typescript
const [error, setError] = useState<string | null>(null);
```

**Add after it:**
```typescript
  const [password, setPassword] = useState("");
  const [passwordRequired, setPasswordRequired] = useState(false);
  const [expired, setExpired] = useState(false);
  const [isForking, setIsForking] = useState(false);
```

### TASK 1E-2: Update the `useEffect` that loads the trace

**Find the `useEffect` that calls `fetchSharedTrace` and replace it entirely:**

```typescript
  useEffect(() => {
    async function load() {
      try {
        const data = await fetchSharedTrace(shareToken);
        setTrace(data);
        setCode(data.code);
        if (data.steps?.length) {
          setTraceResult({
            trace_id: data.id,
            steps: data.steps,
            total_steps: data.steps.length,
            duration_ms: 0,
          });
        }
      } catch (err) {
        const errObj = err as Error & { status?: number; body?: Record<string, unknown> };
        if (err instanceof Error && err.message === "TRACE_NOT_FOUND") {
          setNotFound(true);
        } else if (errObj.status === 401) {
          setPasswordRequired(true);
        } else if (errObj.status === 410) {
          setExpired(true);
        } else {
          setError(err instanceof Error ? err.message : "Failed to load trace");
        }
      }
    }
    load();
  }, [shareToken]);

  // Password submission for protected traces
  const handlePasswordSubmit = useCallback(async () => {
    try {
      const data = await fetchSharedTrace(shareToken);
      setTrace(data);
      setCode(data.code);
      setPasswordRequired(false);
      if (data.steps?.length) {
        setTraceResult({
          trace_id: data.id,
          steps: data.steps,
          total_steps: data.steps.length,
          duration_ms: 0,
        });
      }
    } catch (err) {
      const errObj = err as Error & { status?: number };
      if (errObj.status === 401) {
        setError("Incorrect password");
      } else {
        setError(err instanceof Error ? err.message : "Failed to load trace");
      }
    }
  }, [shareToken]);

  // Fork handler
  const handleFork = useCallback(async () => {
    setIsForking(true);
    setError(null);
    try {
      const res = await authFetch(
        `${getApiBase()}/traces/shared/${shareToken}/fork`,
        { method: "POST" }
      );
      if (!res.ok) throw new Error("Fork failed");
      const data = await res.json();
      router.push(data.share_url);
    } catch {
      router.push("/auth/login");
    } finally {
      setIsForking(false);
    }
  }, [shareToken, router]);
```

**Find `const getApiBase = ...` or the API_BASE constant and add it if missing (needed for `handleFork`):**

```typescript
const API_BASE =
  (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000") + "/api";
function getApiBase() {
  return API_BASE;
}
```

### TASK 1E-3: Add password gate and expiry state renders

**Find `if (notFound) { ... }` and add BEFORE it:**

```tsx
  if (expired) {
    return (
      <div className={styles.page}>
        <div className={styles.notFound}>
          <h1>🔗 This trace link has expired</h1>
          <p>Sign in to CodeScope to view this trace.</p>
          <Link href="/auth/login" className={styles.homeLink}>
            ← Sign in to CodeScope
          </Link>
        </div>
      </div>
    );
  }

  if (passwordRequired) {
    return (
      <div className={styles.page}>
        <div className={styles.passwordGate}>
          <h1>🔒 Password Required</h1>
          <p>Enter the password to view this trace.</p>
          <input
            type="password"
            className={styles.passwordInput}
            placeholder="Enter password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handlePasswordSubmit()}
            autoFocus
          />
          {error && <p className={styles.passwordError}>{error}</p>}
          <button className={styles.passwordSubmitBtn} onClick={handlePasswordSubmit}>
            View Trace
          </button>
          <Link href="/" className={styles.homeLink}>
            ← Go to CodeScope
          </Link>
        </div>
      </div>
    );
  }
```

### TASK 1E-4: Add Fork button to header

**Find the header `actions` div and add after the Trace button:**

```tsx
          <button
            onClick={handleFork}
            disabled={isForking}
            className={styles.forkBtn}
            title="Fork this trace to your account"
          >
            {isForking ? "⏳" : "🍴"} Fork &amp; Trace
          </button>
```

### TASK 1E-5: Add CSS for new shared page elements

**File:** `frontend/app/trace/[share_token]/share.module.css`

**Append:**

```css
/* Password gate */
.passwordGate {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; min-height: 60vh;
  text-align: center; padding: 32px;
}
.passwordGate h1 { font-size: 24px; color: #f8fafc; margin-bottom: 12px; }
.passwordGate p { color: #94a3b8; margin-bottom: 20px; }
.passwordInput {
  padding: 12px 16px; width: 300px;
  background: #0f172a; border: 1px solid #334155;
  border-radius: 8px; color: #f8fafc;
  font-size: 16px; text-align: center; margin-bottom: 12px;
}
.passwordInput:focus { outline: none; border-color: #6366f1; }
.passwordError { color: #fca5a5; font-size: 14px; margin-bottom: 8px; }
.passwordSubmitBtn {
  padding: 12px 32px; background: #6366f1; border: none;
  border-radius: 8px; color: white; cursor: pointer;
  font-size: 16px; font-weight: 600; margin-bottom: 16px;
}
.passwordSubmitBtn:hover { background: #4f46e5; }

/* Fork button */
.forkBtn {
  padding: 8px 16px; background: #065f46;
  border: 1px solid #047857; border-radius: 8px;
  color: #6ee7b7; cursor: pointer;
  font-size: 14px; font-weight: 500; transition: all 0.15s ease;
}
.forkBtn:hover:not(:disabled) { background: #047857; }
.forkBtn:disabled { opacity: 0.5; cursor: not-allowed; }
```

**Verification:**
```bash
cd C:\Users\quoct\codescope\frontend
npm run build
# Expected: build succeeds
```

---

## Phase 1F: Frontend — Open Graph Meta Tags

### TASK 1F-1: Add `generateMetadata` to shared trace page

**File:** `frontend/app/trace/[share_token]/page.tsx`

**Add this export at the bottom of the file, OUTSIDE the component function:**

```typescript
export async function generateMetadata({
  params,
}: {
  params: { share_token: string };
}) {
  return {
    title: "CodeScope Trace",
    description: "See exactly what this Python code does — step by step.",
    openGraph: {
      title: "CodeScope — Python Trace",
      description: "An interactive step-by-step visualization of Python code execution.",
      type: "article",
    },
    twitter: {
      card: "summary",
      title: "See this Python code execute step-by-step",
      description: "Visualize variable state, branches, and loops in real-time.",
    },
  };
}
```

---

## Phase 3D: Frontend — WhatIfModal Component

### TASK 3D-1: Create `WhatIfModal.tsx`

**File:** `frontend/components/tracer/WhatIfModal.tsx` ⊕ (new file)

```typescript
"use client";

import { useState, useCallback } from "react";
import type { TraceStep } from "@/types/trace";
import styles from "./WhatIfModal.module.css";

interface WhatIfModalProps {
  steps: TraceStep[];
  code: string;
  onSubmit: (initialNamespace: Record<string, string>, changedVars: string[]) => void;
  onClose: () => void;
  isLoading?: boolean;
}

type VarType = "string" | "number" | "list" | "dict" | "bool" | "null" | "unknown";

function detectType(valueStr: string): VarType {
  const trimmed = valueStr.trim();
  if (trimmed === "True" || trimmed === "False") return "bool";
  if (trimmed === "None") return "null";
  if (trimmed.startsWith("[") && trimmed.endsWith("]")) return "list";
  if (trimmed.startsWith("{") && trimmed.endsWith("}")) return "dict";
  if (trimmed.startsWith('"') || trimmed.startsWith("'")) return "string";
  if (!isNaN(Number(trimmed)) && trimmed !== "") return "number";
  return "unknown";
}

function TypeInput({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const varType = detectType(value);

  if (varType === "list" || varType === "dict") {
    return (
      <textarea
        className={styles.textareaInput}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={3}
        placeholder={varType === "list" ? "[1, 2, 3]" : '{"key": "value"}'}
      />
    );
  }
  if (varType === "bool") {
    return (
      <select className={styles.selectInput} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="True">True</option>
        <option value="False">False</option>
      </select>
    );
  }
  if (varType === "number") {
    return (
      <input
        type="number"
        className={styles.textInput}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }
  return (
    <input
      type="text"
      className={styles.textInput}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={value || "Enter value..."}
    />
  );
}

export function WhatIfModal({ steps, code, onSubmit, onClose, isLoading }: WhatIfModalProps) {
  const firstStep = steps[0];
  const initialVars = firstStep?.variables ?? {};

  const [values, setValues] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    for (const [name, info] of Object.entries(initialVars)) {
      init[name] = info.value;
    }
    return init;
  });

  const [changedVars, setChangedVars] = useState<Set<string>>(new Set());

  const handleChange = useCallback(
    (name: string, newValue: string) => {
      setValues((prev) => ({ ...prev, [name]: newValue }));
      if (newValue !== initialVars[name]?.value) {
        setChangedVars((prev) => new Set(prev).add(name));
      } else {
        setChangedVars((prev) => {
          const next = new Set(prev);
          next.delete(name);
          return next;
        });
      }
    },
    [initialVars]
  );

  const handleSubmit = useCallback(() => {
    onSubmit(values, Array.from(changedVars));
  }, [values, changedVars, onSubmit]);

  const changedList = Array.from(changedVars);

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h2 className={styles.title}>What If?</h2>
          <p className={styles.subtitle}>
            Modify initial values and see how the execution changes.
          </p>
        </div>

        <div className={styles.variables}>
          {Object.keys(initialVars).length === 0 ? (
            <p className={styles.noVars}>No variables detected at step 0.</p>
          ) : (
            Object.entries(initialVars).map(([name, info]) => (
              <div key={name} className={styles.varRow}>
                <div className={styles.varHeader}>
                  <span className={`${styles.varName} ${changedVars.has(name) ? styles.changed : ""}`}>
                    {changedVars.has(name) ? "● " : ""}
                    {name}
                  </span>
                  <span className={styles.varType}>{info.type}</span>
                </div>
                <TypeInput
                  value={values[name] ?? info.value}
                  onChange={(v) => handleChange(name, v)}
                />
                {changedVars.has(name) && (
                  <div className={styles.originalValue}>was: {info.value}</div>
                )}
              </div>
            ))
          )}
        </div>

        {changedList.length > 0 && (
          <div className={styles.summary}>
            <span className={styles.summaryLabel}>You changed:</span>
            <code className={styles.summaryCode}>
              {changedList.map((v) => `${v} = ${values[v]}`).join(", ")}
            </code>
          </div>
        )}

        <div className={styles.actions}>
          <button className={styles.cancelBtn} onClick={onClose} disabled={isLoading}>
            Cancel
          </button>
          <button
            className={styles.replayBtn}
            onClick={handleSubmit}
            disabled={isLoading || changedList.length === 0}
          >
            {isLoading ? "⏳ Replaying..." : "🔁 Replay from Here"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

### TASK 3D-2: Create `WhatIfModal.module.css`

**File:** `frontend/components/tracer/WhatIfModal.module.css` ⊕ (new file)

```css
.overlay {
  position: fixed; inset: 0;
  background: rgba(0, 0, 0, 0.65);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000; backdrop-filter: blur(4px);
}

.modal {
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 16px;
  padding: 32px;
  width: 560px; max-width: 90vw; max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.5);
}

.header { margin-bottom: 24px; }

.title {
  font-size: 22px; font-weight: 700;
  color: #f8fafc; margin: 0 0 8px 0;
}

.subtitle { font-size: 14px; color: #64748b; margin: 0; }

.variables {
  display: flex; flex-direction: column;
  gap: 16px; margin-bottom: 20px;
}

.noVars {
  color: #64748b; font-size: 14px;
  text-align: center; padding: 24px;
}

.varRow {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 10px; padding: 14px;
}

.varHeader {
  display: flex; align-items: center;
  justify-content: space-between; margin-bottom: 10px;
}

.varName {
  font-size: 15px; font-weight: 600;
  color: #e2e8f0;
  font-family: "Fira Code", "Courier New", monospace;
}

.varName.changed { color: #fbbf24; }

.varType {
  font-size: 12px; color: #64748b;
  background: #0f172a; padding: 2px 8px;
  border-radius: 4px; border: 1px solid #1e293b;
}

.textInput, .selectInput, .textareaInput {
  width: 100%; padding: 8px 10px;
  background: #0f172a; border: 1px solid #334155;
  border-radius: 6px;
  color: #22c55e; font-size: 13px;
  font-family: "Fira Code", "Courier New", monospace;
  box-sizing: border-box; resize: vertical;
}
.textInput:focus, .selectInput:focus, .textareaInput:focus {
  outline: none; border-color: #6366f1;
}

.originalValue {
  margin-top: 6px; font-size: 12px;
  color: #64748b;
  font-family: "Fira Code", "Courier New", monospace;
}

.summary {
  background: #1c1917; border: 1px solid #44403c;
  border-radius: 8px; padding: 12px 14px; margin-bottom: 20px;
}

.summaryLabel { font-size: 13px; color: #a8a29e; margin-right: 8px; }

.summaryCode {
  font-size: 13px; color: #fbbf24;
  font-family: "Fira Code", "Courier New", monospace;
}

.actions {
  display: flex; gap: 12px; justify-content: flex-end;
}

.cancelBtn {
  padding: 10px 20px; background: transparent;
  border: 1px solid #334155; border-radius: 8px;
  color: #94a3b8; cursor: pointer; font-size: 14px; font-weight: 500;
  transition: all 0.15s ease;
}
.cancelBtn:hover:not(:disabled) { background: #1e293b; color: #e2e8f0; }

.replayBtn {
  padding: 10px 20px; background: #6366f1; border: none;
  border-radius: 8px; color: white;
  cursor: pointer; font-size: 14px; font-weight: 600;
  transition: all 0.15s ease;
}
.replayBtn:hover:not(:disabled) { background: #4f46e5; }
.replayBtn:disabled { opacity: 0.4; cursor: not-allowed; }
```

---

## Phase 3E: Frontend — Wire What-If Into Tracer Page

### TASK 3E-1: Import WhatIfModal

**File:** `frontend/app/tracer/page.tsx`

**Find this import:**
```typescript
import { VariablePanel } from "@/components/tracer/VariablePanel";
```

**Add after it:**
```typescript
import { WhatIfModal } from "@/components/tracer/WhatIfModal";
```

### TASK 3E-2: Add What-If state

**Find `const [showExplanation, setShowExplanation] = useState(false);` and add after it:**

```typescript
  const [showWhatIf, setShowWhatIf] = useState(false);
  const [whatIfLoading, setWhatIfLoading] = useState(false);
```

### TASK 3E-3: Add What-If button in footer

**Find `<div className={styles.lineActions}>` and add BEFORE the existing `<button className={styles.whyBtn}>`:**

```tsx
          <button
            className={styles.whatIfBtn}
            onClick={() => setShowWhatIf(true)}
            disabled={!traceResult || (traceResult.steps?.length ?? 0) === 0}
            title={!traceResult ? "Run the trace first" : "Modify initial values and replay"}
          >
            🔄 What If?
          </button>
```

### TASK 3E-4: Add WhatIfModal render

**Find the closing `</footer>` tag and add BEFORE it (after the last child of footer):**

```tsx
      {showWhatIf && (
        <WhatIfModal
          steps={traceResult?.steps ?? []}
          code={code}
          isLoading={whatIfLoading}
          onClose={() => setShowWhatIf(false)}
          onSubmit={async (initialNamespace, changedVars) => {
            setShowWhatIf(false);
            setWhatIfLoading(true);
            setTraceResult(null);
            setError(null);
            reset();
            try {
              const result = await runTrace(code, { initialNamespace });
              if (result.error) {
                setError(result.error_message ?? result.error);
              } else {
                setTraceResult({
                  trace_id: result.trace_id ?? "",
                  steps: result.steps ?? [],
                  total_steps: result.total_steps ?? result.steps?.length ?? 0,
                  duration_ms: result.duration_ms ?? 0,
                });
              }
            } catch (err) {
              setError(err instanceof Error ? err.message : "Failed to run trace");
            } finally {
              setWhatIfLoading(false);
            }
          }}
        />
      )}
```

**Find the `import { runTrace }` usage** — note that `runTrace` is imported from `@/lib/api` as a standalone function (see TASK 1D-2). Verify the import is available.

### TASK 3E-5: Add What-If button CSS

**Append to `frontend/app/tracer/page.module.css`:**

```css
.whatIfBtn {
  padding: 8px 16px; background: #1c1917;
  color: #fbbf24; border: 1px solid #44403c;
  border-radius: 8px; cursor: pointer;
  font-size: 14px; font-weight: 600;
  transition: all 0.15s ease;
  display: flex; align-items: center; gap: 6px;
}
.whatIfBtn:hover:not(:disabled) { background: #292524; border-color: #57534e; }
.whatIfBtn:disabled { opacity: 0.4; cursor: not-allowed; }
```

**Verification:**
```bash
cd C:\Users\quoct\codescope\frontend
npm run build
# Expected: build succeeds
```

---

## Phase 5A: Frontend — Review Page Uses `useTrace` Hook

### TASK 5A-1: Replace manual rAF with `useTrace` hook

**File:** `frontend/app/review/[card_id]/page.tsx`

**This is the most impactful change — replaces ~40 lines of manual requestAnimationFrame code with the battle-tested useTrace hook.**

**Replace the entire component function body (from `export default function ReviewPage()` to the end of the component, but KEEP the imports at the top) with:**

```typescript
export default function ReviewPage() {
  const params = useParams();
  const router = useRouter();
  const cardId = params.card_id as string;

  const [card, setCard] = useState<ReviewCardDetail | null>(null);
  const [reviewState, setReviewState] = useState<ReviewState>("loading");
  const [rating, setRating] = useState<"again" | "hard" | "good" | "easy" | null>(null);
  const [nextReview, setNextReview] = useState<string | null>(null);
  const [nextInterval, setNextInterval] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // REPLAY: Use saved steps from the card (NOT re-execution).
  // Backend returns card.trace.steps from the traces.steps JSONB column.
  const steps = card?.trace?.steps ?? [];

  // useTrace manages animation state — same hook as tracer page
  const {
    currentStep,
    playbackState,
    currentStepData,
    play,
    pause,
    togglePlayPause,
    stepForward,
    stepBackward,
    jumpToStep,
    setSpeed,
    reset,
  } = useTrace({ steps, autoPlay: true });

  // Load card on mount
  useEffect(() => {
    async function load() {
      const { data } = await getSupabase().auth.getSession();
      if (!data?.session) {
        router.replace("/auth/login");
        return;
      }
      try {
        const loadedCard = await fetchReviewCard(cardId);
        setCard(loadedCard);
        setReviewState("playing");
      } catch (err) {
        if (err instanceof Error && err.message === "CARD_NOT_FOUND") {
          setError("Card not found. It may have already been reviewed.");
        } else if (err instanceof Error && err.message === "AUTH_REQUIRED") {
          router.replace("/auth/login");
        } else {
          setError(err instanceof Error ? err.message : "Failed to load card");
        }
        setReviewState("error");
      }
    }
    load();
  }, [cardId, router]);

  // Transition from playing → rating when playback ends
  useEffect(() => {
    if (playbackState === "ended" && reviewState === "playing") {
      setReviewState("rating");
    }
  }, [playbackState, reviewState]);

  const handleRating = useCallback(
    async (r: "again" | "hard" | "good" | "easy") => {
      setRating(r);
      setReviewState("submitting");
      try {
        const result = await submitReviewRating(cardId, r);
        setNextReview(result.next_review_date);
        setNextInterval(result.new_interval_days);
        setReviewState("submitted");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to submit review");
        setReviewState("rating"); // Return to rating so user can retry
      }
    },
    [cardId]
  );

  if (reviewState === "loading") {
    return (
      <div className={styles.page}>
        <div className={styles.loading}>
          <span className={styles.spinner}>◈</span> Loading review...
        </div>
      </div>
    );
  }

  if (reviewState === "error") {
    return (
      <div className={styles.page}>
        <div className={styles.errorState}>
          <p>⚠ {error}</p>
          <Link href="/dashboard" className={styles.backBtn}>
            ← Back to dashboard
          </Link>
        </div>
      </div>
    );
  }

  const currentStepData = steps[currentStep] ?? null;

  return (
    <div className={styles.page}>
      <header className={styles.topBar}>
        <Link href="/dashboard" className={styles.backLink}>
          ← Dashboard
        </Link>
        <div className={styles.cardInfo}>
          {card && <span className={styles.conceptTag}>{card.concept_tag}</span>}
          <span className={styles.replayBadge}>🔁 Replay</span>
        </div>
        <div />
      </header>

      <main className={styles.main}>
        <div className={styles.editorSection}>
          {card ? (
            <CodeEditor
              code={card.trace.code}
              onChange={() => {}}
              currentLine={currentStepData?.line_number ?? 1}
              readOnly
            />
          ) : (
            <div className={styles.noCode}>
              <p>Trace code unavailable.</p>
              <p className={styles.hint}>The trace may have been deleted.</p>
            </div>
          )}
        </div>

        {/* Manual step controls during playback */}
        {reviewState === "playing" && steps.length > 0 && (
          <>
            <div className={styles.stepCounter}>
              Step {currentStep + 1} / {steps.length}
            </div>
            <div className={styles.controlsRow}>
              <button onClick={stepBackward} disabled={currentStep === 0}>⏮</button>
              <button onClick={togglePlayPause}>
                {playbackState === "playing" ? "⏸" : "▶"}
              </button>
              <button onClick={stepForward} disabled={currentStep >= steps.length - 1}>⏭</button>
            </div>
          </>
        )}

        {/* Rating buttons */}
        {(reviewState === "rating" || reviewState === "submitting") && (
          <div className={styles.ratingPanel}>
            <h2 className={styles.ratingTitle}>
              {reviewState === "submitting"
                ? "Submitting..."
                : "How well did you understand this?"}
            </h2>
            <div className={styles.ratingButtons}>
              {(["again", "hard", "good", "easy"] as const).map((r) => (
                <button
                  key={r}
                  onClick={() => handleRating(r)}
                  disabled={reviewState === "submitting" || rating !== null}
                  className={`${styles.ratingBtn} ${styles[`ratingBtn_${r}`]}`}
                >
                  <span className={styles.ratingLabel}>{RATING_CONFIG[r].label}</span>
                  <span className={styles.ratingHint}>{RATING_CONFIG[r].hint}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Submitted state */}
        {reviewState === "submitted" && (
          <div className={styles.submittedPanel}>
            <div className={styles.submittedIcon}>✓</div>
            <h2 className={styles.submittedTitle}>Review complete!</h2>
            {nextReview && nextInterval !== null && (
              <p className={styles.submittedInfo}>
                Next review: <strong>{formatNextReview(new Date(nextReview))}</strong> (
                {nextInterval === 1 ? "1 day" : `${nextInterval} days`})
              </p>
            )}
            <button
              onClick={() => router.push("/dashboard")}
              className={styles.dashboardBtn}
            >
              ← Back to Dashboard
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
```

### TASK 5A-2: Update review page imports

**Find the imports section at the top of the file and replace the imports block with:**

```typescript
import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import dynamic from "next/dynamic";
import { getSupabase } from "@/lib/supabase";
import { fetchReviewCard, submitReviewRating } from "@/lib/api";
import { formatNextReview } from "@/lib/sm2";
import type { ReviewCardDetail } from "@/types/user";
import { useTrace } from "@/hooks/useTrace"; // ← REPLACES manual rAF
import styles from "./review.module.css";
```

### TASK 5A-3: Add CSS for replay badge and controls

**Append to `frontend/app/review/[card_id]/review.module.css`:**

```css
.replayBadge {
  font-size: 11px; padding: 3px 8px;
  background: #1c1917; color: #fbbf24;
  border: 1px solid #44403c; border-radius: 4px;
  font-weight: 600; letter-spacing: 0.02em; margin-left: 8px;
}

.stepCounter {
  text-align: center; font-size: 13px;
  color: #64748b; margin-bottom: 8px;
}

.controlsRow {
  display: flex; justify-content: center;
  gap: 12px; margin-bottom: 16px;
}

.controlsRow button {
  padding: 8px 16px; background: #1e293b;
  border: 1px solid #334155; border-radius: 8px;
  color: #e2e8f0; cursor: pointer; font-size: 16px;
  transition: all 0.15s ease;
}
.controlsRow button:hover:not(:disabled) { background: #334155; }
.controlsRow button:disabled { opacity: 0.3; cursor: not-allowed; }
```

**Verification:**
```bash
cd C:\Users\quoct\codescope\frontend
npm run build
# Expected: build succeeds
```

---

## Final Verification Checklist

After completing all phases, verify each feature works end-to-end:

### Feature 1 — Shared Trace Links
- [ ] DB migration DB-1 applied → `traces` has `steps` JSONB column
- [ ] DB migration DB-2 applied → `traces` has `expires_at` and `password_hash`
- [ ] Save a trace → steps are stored in DB
- [ ] Open shared link (`/trace/{token}`) → replay plays from saved steps
- [ ] Share button appears on tracer toolbar when trace is loaded
- [ ] Share modal shows expiration dropdown + password field
- [ ] Generate share link → URL appears with copy button
- [ ] Password-protected trace shows password gate
- [ ] Expired trace shows 410 page
- [ ] Fork button on shared page → creates new trace and redirects

### Feature 3 — What-If Sandbox
- [ ] What-If button appears in tracer footer
- [ ] Click What-If → modal shows type-appropriate inputs for all variables
- [ ] Change `items = []` → replay shows modified execution
- [ ] "was: X" shows below changed variable inputs
- [ ] "You changed:" summary shows at bottom of modal

### Feature 5 — Trace Replay from Saved State
- [ ] Save a trace → steps saved in DB (DB-1)
- [ ] Open dashboard → click review card → animation plays from saved steps (NOT re-execution)
- [ ] Review page uses `useTrace` hook (no manual rAF)
- [ ] 🔁 Replay badge shown in review page header
- [ ] Manual step controls work during playback

### Smoke Tests
- [ ] `pytest backend/tests/ -v` — all pass
- [ ] `cd frontend && npm test` — all pass
- [ ] `cd frontend && npm run build` — succeeds with 0 errors

---

## Phase Gate Criteria

| Phase | Gate | How to verify |
|-------|------|---------------|
| DB | Migrations applied | SQL query returns all expected columns |
| 1C | Steps saved in DB | Supabase: `SELECT steps FROM traces LIMIT 1` returns array |
| 1B | Share API works | curl tests for expiry, password, fork |
| 3A | initial_namespace in tracer | Python shell test with `{"x": 5}` |
| 3B | initial_namespace in runner | Python shell test via runner |
| 3C | API accepts initial_namespace | curl with `initial_namespace` param |
| 1D | Share button + modal visible | Browser: click Trace, then Share |
| 1E | Shared page handles expiry + password + fork | Browser tests |
| 1F | OG tags present | Browser: inspect `<head>` of shared URL |
| 3D | WhatIfModal renders | Browser: click What-If button |
| 3E | What-If replay works | Browser: change value, click Replay |
| 5A | Review page plays from saved steps | Browser: open review card |
| 5B | Review endpoint returns steps | curl + JWT to review endpoint |
