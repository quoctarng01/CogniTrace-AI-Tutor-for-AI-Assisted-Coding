# FEATURE-IDEA.md — Implementation Plan

## Top 3 Features: Shared Trace Links, What-If Sandbox, Trace Replay from Saved State

> **Goal:** Atomic, step-by-step tasks so any AI (even a worst one) can implement without bugs.
> Each task is: file → exact change → expected outcome.

---

## Conventions Used in This Plan


| Symbol | Meaning                       |
| ------ | ----------------------------- |
| `+`    | Add new code                  |
| `-`    | Remove code                   |
| `~`    | Replace existing code         |
| `[→]`  | Rename                        |
| `M`    | Migration file (database)     |
| `B`    | Backend (FastAPI)             |
| `F`    | Frontend (Next.js)            |
| `T`    | Type definition               |
| `D`    | Database (Supabase/Postgres)  |
| `⊕`    | New file                      |
| `✦`    | Critical dependency (blocker) |
| `→`    | Depends on                    |


---

## Quick-Reference: File Map

```
Codebase
├── backend/
│   ├── tracer/
│   │   ├── tracer.py          ← Core trace execution engine
│   │   ├── runner.py          ← Subprocess wrapper for tracer
│   │   └── models.py          ← TraceStep, VariableInfo dataclasses
│   ├── app/
│   │   ├── config.py          ← Settings (Supabase URL, keys)
│   │   ├── routers/
│   │   │   ├── traces.py      ← POST /traces/run, POST /traces, GET /traces/shared/{token}, POST /traces/{id}/share
│   │   │   └── review.py      ← GET /review/due, GET /review/{id}, POST /review/{id}
│   │   └── main.py            ← FastAPI app registration
│   └── migrations/
│       └── V001__initial_schema.sql ← Database schema
├── frontend/
│   ├── app/
│   │   ├── tracer/page.tsx               ← Main tracer page
│   │   ├── trace/[share_token]/page.tsx  ← Shared trace view (READ-ONLY)
│   │   ├── review/[card_id]/page.tsx     ← SM-2 review page
│   │   └── dashboard/page.tsx            ← Dashboard
│   ├── components/
│   │   ├── tracer/VariablePanel.tsx       ← Variable display
│   │   └── tracer/AnimationControls.tsx  ← Playback controls
│   ├── hooks/
│   │   └── useTrace.ts                   ← Animation loop hook
│   ├── lib/
│   │   ├── api.ts                        ← API client
│   │   └── sm2.ts                       ← SM-2 algorithm
│   └── types/
│       ├── trace.ts                      ← TraceStep, TraceResult types
│       └── user.ts                       ← SavedTrace, ReviewCard types
```

---

## ═══════════════════════════════════════════════

## FEATURE 1 — Shared Trace Links: One-Click Replay

## ═══════════════════════════════════════════════

### Priority: 1 — Effort: S (Small)

### What Already Exists (DO NOT REIMPLEMENT)

- `share_token` is generated as `secrets.token_hex(16)` on every save
- `/trace/[share_token]/page.tsx` renders code + variable panel + animation controls
- `POST /traces/{id}/share` generates a new token and sets `is_public=true`
- `GET /traces/shared/{share_token}` fetches trace by token
- RLS policy allows unauthenticated reads of `is_public=true` traces

### What's Missing


| Missing Feature      | Gap                                                     |
| -------------------- | ------------------------------------------------------- |
| Share toolbar button | User must navigate to `/traces/{id}/share` API manually |
| "Copy Link" button   | No UI to copy the share URL                             |
| Expiration options   | No `expires_at` column                                  |
| Password protection  | No `password_hash` column                               |
| Fork capability      | No "Fork & Trace" button on shared page                 |
| Share analytics      | No `share_analytics` table                              |
| Social preview       | No Open Graph meta tags                                 |
| Steps on shared page | Steps NOT saved in DB → shared page can't replay        |


### ⚠️ CRITICAL PREREQUISITE (Fix First!)

**The shared page CANNOT replay traces because `steps` are not saved in the DB.**
This is the #1 blocker for the entire feature.
See **Section: SHARED BLOCKER FIX** below before doing anything else.

---

### Phase 1A: Database Migration — Shared Link Infrastructure

**File:** `backend/migrations/V002__shared_trace_enhancements.sql` ⊕

```sql
-- MIGRATION V002: Shared Trace Link Enhancements
-- Adds: expiration, password, analytics tracking to traces + share_analytics table

-- 1. Add columns to traces table
ALTER TABLE traces ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE traces ADD COLUMN IF NOT EXISTS password_hash TEXT;  -- bcrypt hash, nullable

-- 2. Share analytics table
CREATE TABLE IF NOT EXISTS share_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    share_token TEXT NOT NULL,
    viewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    viewer_ip_hash TEXT,       -- SHA-256 of IP, never raw IP
    referrer TEXT,             -- e.g. "discord.com", "twitter.com"
    is_authenticated BOOLEAN NOT NULL DEFAULT false,
    forked BOOLEAN NOT NULL DEFAULT false,
    user_agent TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for fast lookups by share_token
CREATE INDEX IF NOT EXISTS idx_share_analytics_token ON share_analytics(share_token);
CREATE INDEX IF NOT EXISTS idx_share_analytics_viewed ON share_analytics(share_token, viewed_at DESC);
```

**Run this migration:** `supabase db push` or apply via Supabase dashboard SQL editor.
**Verification:** After running, `SELECT column_name FROM information_schema.columns WHERE table_name='traces';` should show `expires_at` and `password_hash`.

---

### Phase 1B: Backend — Update Share Endpoint

**File:** `backend/app/routers/traces.py`

#### SUB-TASK 1B-1: Add `ShareTraceRequest` model (near line 260)

Add AFTER `SaveTraceRequest` class definition:

```python
class ShareTraceRequest(BaseModel):
    """Request body for POST /traces/{id}/share."""
    expiration_days: int | None = Field(
        default=None,
        ge=0,  # 0 = never expires
        le=365,  # max 1 year
        description="Days until link expires. null/0 = never. Values: null (never), 1, 7, 30, 90, 365.",
    )
    password: str | None = Field(
        default=None,
        max_length=128,
        description="Optional password to protect the shared link. If set, viewers must enter this password.",
    )
```

#### SUB-TASK 1B-2: Import bcrypt

Add to imports at TOP of file (after existing imports):

```python
import bcrypt
```

#### SUB-TASK 1B-3: Replace `POST /traces/{trace_id}/share` endpoint (line 394–422)

**Replace ENTIRE endpoint with:**

```python
@router.post("/traces/{trace_id}/share")
async def share_trace(
    trace_id: str,
    req: ShareTraceRequest | None = None,
    authorization: str = Header(None),
):
    """
    Generate or update a share link for a trace.
    
    Sets is_public=true and generates/updates the share_token.
    
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
        # Never expires — ensure column is null
        update_payload["expires_at"] = None

    # Handle password protection
    if req and req.password:
        hashed = bcrypt.hashpw(req.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        update_payload["password_hash"] = hashed
    else:
        update_payload["password_hash"] = None

    async with httpx.AsyncClient(timeout=10.0) as client:
        # First verify the trace belongs to this user
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

#### SUB-TASK 1B-4: Update `GET /traces/shared/{share_token}` for expiration + password

**Replace ENTIRE endpoint (line 373–391) with:**

```python
class VerifyPasswordRequest(BaseModel):
    password: str


@router.get("/traces/shared/{share_token}")
async def get_shared_trace(
    share_token: str,
    password: str | None = None,
):
    """
    Get a trace by its share token. Public endpoint.
    
    Returns:
      - 200: trace data (or 401 if password required but not provided)
      - 404: trace not found or expired
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
        if datetime.now(timezone.utc) > datetime.fromisoformat(expires_at.replace("Z", "+00:00")):
            raise HTTPException(
                status_code=410,
                detail={
                    "error": "EXPIRED",
                    "message": "This trace has expired. Sign in to CodeScope to view it.",
                    "login_url": "/auth/login",
                }
            )

    # Check password
    password_hash = trace.get("password_hash")
    if password_hash:
        if not password:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "PASSWORD_REQUIRED",
                    "message": "This trace is password-protected. Pass ?password=... to verify.",
                }
            )
        if not bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8")):
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "WRONG_PASSWORD",
                    "message": "Incorrect password.",
                }
            )

    # Log analytics (non-blocking — don't fail the request if this errors)
    try:
        from datetime import datetime, timezone
        import hashlib
        async with httpx.AsyncClient(timeout=3.0) as analytic_client:
            ip_hash = "unknown"  # In production, hash the real IP
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
                    "viewer_ip_hash": ip_hash,
                    "is_authenticated": False,
                    "forked": False,
                },
            )
    except Exception:
        pass  # Non-blocking

    # Return trace data (include steps if available)
    result = {k: v for k, v in trace.items() if k not in ("password_hash",)}
    return result
```

#### SUB-TASK 1B-5: Add Fork endpoint

**Add AFTER `POST /traces/{trace_id}/share` endpoint:**

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
        "is_public": False,  # Forks start private
        "share_token": new_share_token,
        "steps": orig.get("steps"),  # Preserve full steps for replay
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
        "new_trace_id": fork.get("id"),
        "user_id": user_id,
    })

    return ForkTraceResponse(
        trace_id=fork.get("id", ""),
        share_token=new_share_token,
        share_url=f"/trace/{new_share_token}",
    )
```

---

### Phase 1C: Backend — Update Save Endpoint to Include Steps

**File:** `backend/app/routers/traces.py`

#### SUB-TASK 1C-1: Update `SaveTraceRequest` model to include steps

**Replace `SaveTraceRequest` class (line 254–259):**

```python
class SaveTraceRequest(BaseModel):
    code: str
    language: str = "python"
    steps: list[dict] = Field(default_factory=list, description="Full trace steps array for replay")
    concept_tags: list[str] = Field(default_factory=list)
    is_public: bool = False
```

#### SUB-TASK 1C-2: Update trace_data in `save_trace` to include steps

**In `save_trace` endpoint, replace `trace_data = {...}` block (lines 289–296) with:**

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

#### SUB-TASK 1C-3: Also update `GET /traces/shared/{share_token}` response

The `get_shared_trace` endpoint now returns the full trace object including `steps` (since it returns `{k: v for k, v in trace.items()}`). Ensure the `steps` column in Supabase is JSONB type (it should already be via migration or type inference).

---

### Phase 1D: Frontend — Add "Share" Button + Modal

**File:** `frontend/app/tracer/page.tsx`

#### SUB-TASK 1D-1: Add Share modal state and shareTrace API import

**Find `const [saveSuccess, setSaveSuccess] = useState(false);` (line 65) and ADD AFTER it:**

```typescript
  const [showShareModal, setShowShareModal] = useState(false);
  const [shareResult, setShareResult] = useState<{ share_token: string; share_url: string; expires_at: string | null; has_password: boolean } | null>(null);
  const [shareError, setShareError] = useState<string | null>(null);
  const [isSharing, setIsSharing] = useState(false);
  const [sharePassword, setSharePassword] = useState('');
  const [expirationDays, setExpirationDays] = useState<number | null>(null);
```

#### SUB-TASK 1D-2: Add `shareTrace` import

**Find `import { api, saveTrace } from '@/lib/api';` (line 6) and ADD `shareTrace`:**

```typescript
import { api, saveTrace, shareTrace } from '@/lib/api';
```

#### SUB-TASK 1D-3: Add share handler function after `handleSaveTrace`

**Find `// ── Check authentication on mount` comment (line 92) and ADD BEFORE it:**

```typescript
  const handleShareClick = useCallback(() => {
    setShowShareModal(true);
    setShareResult(null);
    setShareError(null);
    setSharePassword('');
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
      setShareError(err instanceof Error ? err.message : 'Failed to generate share link');
    } finally {
      setIsSharing(false);
    }
  }, [traceResult, expirationDays, sharePassword]);
```

#### SUB-TASK 1D-4: Add "Share" button to toolbar

**Find the `actions` div inside `<header className={styles.topBar}>` (around line 203), specifically the `<button className={styles.saveBtn}>` block. Add BEFORE the save button:**

```tsx
          <button
            className={styles.shareBtn}
            onClick={handleShareClick}
            disabled={!traceResult}
            title={!traceResult ? 'Run the trace first' : 'Share this trace'}
          >
            🔗 Share
          </button>
```

#### SUB-TASK 1D-5: Add Share Modal JSX

**Find the closing `</div>` of `main` tag (line 272) and ADD AFTER it, BEFORE the footer:**

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
                    value={expirationDays ?? ''}
                    onChange={(e) => setExpirationDays(e.target.value === '' ? null : Number(e.target.value))}
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
                  <span className={styles.modalHint}>Viewers must enter this password to access the trace.</span>
                </div>

                {shareError && (
                  <div className={styles.modalError}>{shareError}</div>
                )}

                <div className={styles.modalActions}>
                  <button className={styles.modalCancelBtn} onClick={() => setShowShareModal(false)}>
                    Cancel
                  </button>
                  <button className={styles.modalConfirmBtn} onClick={handleShareSubmit} disabled={isSharing}>
                    {isSharing ? 'Generating...' : 'Generate Link'}
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
                    value={typeof window !== 'undefined' ? `${window.location.origin}${shareResult.share_url}` : shareResult.share_url}
                    onClick={(e) => (e.target as HTMLInputElement).select()}
                  />
                  <button
                    className={styles.copyBtn}
                    onClick={() => {
                      navigator.clipboard.writeText(
                        typeof window !== 'undefined'
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
                  <button className={styles.modalCancelBtn} onClick={() => setShowShareModal(false)}>
                    Done
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
```

#### SUB-TASK 1D-6: Update `frontend/lib/api.ts` — Add password/expiration to shareTrace

**Find the `shareTrace` function (line 312–318) and REPLACE with:**

```typescript
export async function shareTrace(
  traceId: string,
  options?: {
    expiration_days?: number;
    password?: string;
  }
): Promise<{ share_token: string; share_url: string; expires_at: string | null; has_password: boolean }> {
  const body: Record<string, unknown> = {};
  if (options?.expiration_days !== undefined) {
    body.expiration_days = options.expiration_days;
  }
  if (options?.password) {
    body.password = options.password;
  }
  const res = await authFetch(`${getApiBase()}/traces/${traceId}/share`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  throwOnStatus(res, 'share');
  return res.json();
}
```

#### SUB-TASK 1D-7: Update `SharedTraceData` type to include steps

**File:** `frontend/types/user.ts`

**Find `SharedTraceData` interface and UPDATE:**

```typescript
/** Shared trace with embedded steps — returned by GET /api/traces/shared/{share_token} */
export interface SharedTraceData {
  id: string;
  code: string;
  language: string;
  concept_tags: string[];
  is_public: boolean;
  share_token: string;
  created_at: string;
  expires_at: string | null;
  password_hash: string | null;  // Only present server-side, never sent to client
  steps: TraceStep[];  // ← NOW INCLUDED (previously missing)
}
```

---

### Phase 1E: Frontend — Update Shared Trace Page with Steps Replay + Fork

**File:** `frontend/app/trace/[share_token]/page.tsx`

#### SUB-TASK 1E-1: Update page to auto-replay saved steps

**The shared page already loads `data.steps` and sets `traceResult` (lines 60–67). This is now CORRECT since steps are saved in DB.**

BUT: The shared page needs to handle:

1. Password gate when `password_hash` is returned
2. Expiry error (410) with friendly message
3. Fork button for authenticated users
4. Auto-play option

**Find the `useEffect` that loads trace data (lines 54–74) and REPLACE with:**

```typescript
  const [password, setPassword] = useState('');
  const [passwordRequired, setPasswordRequired] = useState(false);
  const [expired, setExpired] = useState(false);

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
        if (errObj.message === 'TRACE_NOT_FOUND') setNotFound(true);
        else if (errObj.status === 401 && (errObj.body as Record<string, unknown>)?.error === 'PASSWORD_REQUIRED') {
          setPasswordRequired(true);
        } else if (errObj.status === 410) {
          setExpired(true);
        } else {
          setError(err instanceof Error ? err.message : 'Failed to load trace');
        }
      }
    }
    load();
  }, [shareToken]);

  // Password submission
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
        setError('Incorrect password');
      } else {
        setError(err instanceof Error ? err.message : 'Failed to load trace');
      }
    }
  }, [shareToken]);
```

**Find the `if (notFound)` block and ADD AFTER it:**

```typescript
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
            onKeyDown={(e) => e.key === 'Enter' && handlePasswordSubmit()}
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

#### SUB-TASK 1E-2: Add Fork button

**Find the header `actions` div and ADD after the Trace button:**

```tsx
          <button
            onClick={handleFork}
            disabled={isForking}
            className={styles.forkBtn}
            title="Fork this trace to your account"
          >
            {isForking ? '⏳' : '🍴'} Fork & Trace
          </button>
```

**Add `handleFork` callback after `handleSave`:**

```typescript
  const [isForking, setIsForking] = useState(false);
  const [forkResult, setForkResult] = useState<string | null>(null);

  const handleFork = useCallback(async () => {
    setIsForking(true);
    setError(null);
    try {
      const res = await authFetch(`${getApiBase()}/traces/shared/${shareToken}/fork`, { method: 'POST' });
      if (!res.ok) throw new Error('Fork failed');
      const data = await res.json();
      router.push(data.share_url);
    } catch {
      // If not authenticated, redirect to login
      router.push('/auth/login');
    } finally {
      setIsForking(false);
    }
  }, [shareToken, router]);
```

**Add `authFetch` import at top of file:**

```typescript
import { fetchSharedTrace, saveTrace, authFetch } from '@/lib/api';
```

---

### Phase 1F: Frontend — Open Graph Meta Tags for Social Preview

**File:** `frontend/app/trace/[share_token]/page.tsx`

**ADD inside the component, after the `useEffect` for loading (around line 55):**

```typescript
  useEffect(() => {
    if (!trace) return;
    // Update document title
    document.title = `CodeScope Trace — ${trace.code.split('\n')[0].slice(0, 60)}`;
  }, [trace]);
```

**Also add a metadata export for Next.js (add at BOTTOM of the file, outside the component):**

```typescript
export async function generateMetadata({ params }: { params: { share_token: string } }) {
  return {
    title: 'CodeScope Trace',
    description: 'See exactly what this Python code does — step by step.',
    openGraph: {
      title: 'CodeScope — Python Trace',
      description: 'An interactive step-by-step visualization of Python code execution.',
      type: 'article',
    },
    twitter: {
      card: 'summary',
      title: 'See this Python code execute step-by-step',
      description: 'Visualize variable state, branches, and loops in real-time.',
    },
  };
}
```

---

### Phase 1G: CSS Updates for New UI Elements

**File:** `frontend/app/tracer/page.module.css` ⊕ (or append to existing)

**ADD the following CSS classes:**

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
.shareBtn:hover:not(:disabled) {
  background: #334155;
  border-color: #475569;
}
.shareBtn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Modal overlay */
.modalOverlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
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
  font-size: 20px;
  font-weight: 700;
  color: #f8fafc;
  margin: 0 0 24px 0;
}

.modalField {
  margin-bottom: 20px;
}

.modalLabel {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: #cbd5e1;
  margin-bottom: 8px;
}

.modalSelect,
.modalInput {
  width: 100%;
  padding: 10px 12px;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 8px;
  color: #f8fafc;
  font-size: 14px;
  box-sizing: border-box;
}
.modalSelect:focus,
.modalInput:focus {
  outline: none;
  border-color: #6366f1;
}

.modalHint {
  display: block;
  font-size: 12px;
  color: #64748b;
  margin-top: 6px;
}

.modalError {
  padding: 10px 12px;
  background: #450a0a;
  border: 1px solid #991b1b;
  border-radius: 8px;
  color: #fca5a5;
  font-size: 14px;
  margin-bottom: 16px;
}

.modalActions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 24px;
}

.modalCancelBtn {
  padding: 10px 20px;
  background: transparent;
  border: 1px solid #334155;
  border-radius: 8px;
  color: #94a3b8;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.15s ease;
}
.modalCancelBtn:hover {
  background: #1e293b;
  color: #e2e8f0;
}

.modalConfirmBtn {
  padding: 10px 20px;
  background: #6366f1;
  border: none;
  border-radius: 8px;
  color: white;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  transition: all 0.15s ease;
}
.modalConfirmBtn:hover:not(:disabled) {
  background: #4f46e5;
}
.modalConfirmBtn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Share link box */
.shareLinkBox {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.shareLinkInput {
  flex: 1;
  padding: 10px 12px;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 8px;
  color: #22c55e;
  font-size: 13px;
  font-family: 'Fira Code', 'Courier New', monospace;
}

.copyBtn {
  padding: 10px 16px;
  background: #22c55e;
  border: none;
  border-radius: 8px;
  color: #052e16;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}
.copyBtn:hover {
  background: #16a34a;
}

.shareNote {
  font-size: 13px;
  color: #94a3b8;
  margin: 4px 0;
}
```

**File:** `frontend/app/trace/[share_token]/share.module.css` — ADD for new elements:

```css
/* Password gate */
.passwordGate {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  text-align: center;
  padding: 32px;
}
.passwordGate h1 {
  font-size: 24px;
  color: #f8fafc;
  margin-bottom: 12px;
}
.passwordGate p {
  color: #94a3b8;
  margin-bottom: 20px;
}
.passwordInput {
  padding: 12px 16px;
  width: 300px;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 8px;
  color: #f8fafc;
  font-size: 16px;
  text-align: center;
  margin-bottom: 12px;
}
.passwordInput:focus {
  outline: none;
  border-color: #6366f1;
}
.passwordError {
  color: #fca5a5;
  font-size: 14px;
  margin-bottom: 8px;
}
.passwordSubmitBtn {
  padding: 12px 32px;
  background: #6366f1;
  border: none;
  border-radius: 8px;
  color: white;
  cursor: pointer;
  font-size: 16px;
  font-weight: 600;
  margin-bottom: 16px;
}
.passwordSubmitBtn:hover {
  background: #4f46e5;
}

/* Fork button */
.forkBtn {
  padding: 8px 16px;
  background: #065f46;
  border: 1px solid #047857;
  border-radius: 8px;
  color: #6ee7b7;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.15s ease;
}
.forkBtn:hover:not(:disabled) {
  background: #047857;
}
.forkBtn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
```

---

## ═══════════════════════════════════════════════

## SHARED BLOCKER FIX — Save Steps in DB

## ═══════════════════════════════════════════════

> ⚠️ **This fix is required by BOTH Feature 1 AND Feature 5.**
> Without it, the shared page cannot replay traces and review cards have no steps.
> **Do this FIRST** before testing either feature.

### DB Migration: Add `steps` Column

**File:** `backend/migrations/V003__save_steps_in_traces.sql` ⊕

```sql
-- MIGRATION V003: Save full trace steps in traces table
-- Required by: Shared Trace Links (Feature 1) and Trace Replay (Feature 5)

-- The steps column must be JSONB to store the full trace step array
ALTER TABLE traces ADD COLUMN IF NOT EXISTS steps JSONB NOT NULL DEFAULT '[]'::jsonb;
```

**Run:** `supabase db push` or apply via Supabase SQL editor.

**Verification SQL:**

```sql
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'traces' AND column_name = 'steps';
-- Expected: steps | jsonb
```

---

## ═══════════════════════════════════════════════

## FEATURE 3 — What-If Sandbox: Override Initial Namespace

## ═══════════════════════════════════════════════

### Priority: 3 — Effort: XS (Extra Small)

### Concept

Users can modify initial variable values before running a trace. The backend runs `run_trace(source)` but with a pre-filled namespace dict instead of an empty one.

### What's New


| New Component                       | File                                           |
| ----------------------------------- | ---------------------------------------------- |
| `WhatIfModal` component             | `frontend/components/tracer/WhatIfModal.tsx` ⊕ |
| `initial_namespace` param in tracer | `backend/tracer/tracer.py`                     |
| `initial_namespace` param in runner | `backend/tracer/runner.py`                     |
| `initial_namespace` param in API    | `backend/app/routers/traces.py`                |
| What-If button + state              | `frontend/app/tracer/page.tsx`                 |


---

### Phase 3A: Backend — Accept `initial_namespace` in Tracer

**File:** `backend/tracer/tracer.py`

#### SUB-TASK 3A-1: Update `run_trace` signature to accept `initial_namespace`

**Find `def run_trace(source: str, max_steps: int = 500) -> dict:` (line 111) and REPLACE with:**

```python
def run_trace(
    source: str,
    max_steps: int = 500,
    initial_namespace: dict | None = None,
) -> dict:
    """
    Execute Python source code with step-by-step tracing.
    
    Args:
        source: Python source code string
        max_steps: Maximum number of trace steps (default 500)
        initial_namespace: Optional dict of variable names → values to pre-populate
                           the execution namespace. These variables are available
                           at step 0 (before any code executes).
                           Values are evaluated as Python literals (int, float, str,
                           list, dict, tuple, bool, None).
                           Example: {"items": [1, 2, 3], "threshold": 10}
    """
```

#### SUB-TASK 3A-2: Update the namespace initialization

**Find `namespace: dict = {}` (line 129) and REPLACE with:**

```python
    # Pre-populate namespace from initial_namespace if provided
    namespace: dict = {}
    if initial_namespace:
        for name, raw_val in initial_namespace.items():
            try:
                # Evaluate each value as a Python literal
                # This is safe: we only execute the user's code, not the namespace values
                val = eval(repr(raw_val), {"__builtins__": {"True": True, "False": False, "None": None}})
                namespace[name] = val
            except Exception:
                # Silently skip invalid initial values
                pass
```

#### SUB-TASK 3A-3: Update `_capture_variables` to include initial namespace vars

**Find the `_capture_variables` function end (around line 107), just before `return variables`.**
**ADD AFTER the namespace loop:**

```python
    # Add any initial namespace variables that haven't appeared yet
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

---

### Phase 3B: Backend — Pass `initial_namespace` Through Subprocess

**File:** `backend/tracer/runner.py`

#### SUB-TASK 3B-1: Update `run_trace` in runner.py to accept `initial_namespace`

**Read the runner.py file first to find the exact current signature.**
**Replace `run_trace` function:**

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
        source: Python source code
        max_steps: Maximum trace steps
        initial_namespace: Optional pre-populated variable namespace dict
        timeout_seconds: Execution timeout (default 5s)
    
    Returns:
        dict with keys: steps (list), total_steps (int), duration_ms (float),
                        and optionally error (str), error_message (str)
    """
    import json
    import tempfile
    import os
    import subprocess
    import sys

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
        mode='w',
        suffix='.py',
        delete=False,
        encoding='utf-8',
    ) as f:
        f.write(trace_script)
        script_path = f.name

    try:
        proc = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=os.path.dirname(os.path.abspath(__file__)),
        )

        # Extract JSON from output between markers
        stdout = proc.stdout
        stderr = proc.stderr

        if "__RESULT_START__" in stdout:
            json_str = stdout.split("__RESULT_START__")[1].split("__RESULT_END__")[0].strip()
            return json.loads(json_str)
        elif proc.returncode != 0:
            # Execution error
            return {
                "error": "EXECUTION_ERROR",
                "message": stderr.strip() if stderr else "Unknown execution error",
            }
        else:
            return {
                "error": "PARSE_ERROR",
                "message": "Could not parse trace output",
                "raw_output": stdout[:500],
            }
    except subprocess.TimeoutExpired:
        return {
            "error": "TIMEOUT",
            "message": f"Execution timed out after {timeout_seconds} seconds",
        }
    except Exception as e:
        return {
            "error": "SANDBOX_ERROR",
            "message": str(e),
        }
    finally:
        os.unlink(script_path)
```

---

### Phase 3C: Backend — Accept `initial_namespace` in API Endpoint

**File:** `backend/app/routers/traces.py`

#### SUB-TASK 3C-1: Update `TraceRequest` model

**Find `class TraceRequest(BaseModel):` (line 76) and REPLACE with:**

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

#### SUB-TASK 3C-2: Update `run_trace` endpoint to pass `initial_namespace`

**Find the `result = run_trace_subprocess(req.code, max_steps=500)` call (line 154) and REPLACE with:**

```python
    # Parse initial_namespace values from strings to Python values
    initial_ns = None
    if req.initial_namespace:
        initial_ns = {}
        for name, val_str in req.initial_namespace.items():
            try:
                initial_ns[name] = eval(val_str, {"__builtins__": {"True": True, "False": False, "None": None}})
            except Exception:
                # Skip invalid values — tracer will just not have this variable
                pass

    result = run_trace_subprocess(req.code, max_steps=500, initial_namespace=initial_ns)
```

---

### Phase 3D: Frontend — WhatIfModal Component

**File:** `frontend/components/tracer/WhatIfModal.tsx` ⊕

```typescript
// frontend/components/tracer/WhatIfModal.tsx
'use client';

import { useState, useCallback } from 'react';
import type { VariableInfo, TraceStep } from '@/types/trace';
import styles from './WhatIfModal.module.css';

interface WhatIfModalProps {
  /** Current trace's steps (to extract initial variable names + types) */
  steps: TraceStep[];
  /** Current code (used to re-run trace) */
  code: string;
  /** Called when user submits new namespace values */
  onSubmit: (initialNamespace: Record<string, string>, changedVars: string[]) => void;
  /** Called when user closes the modal */
  onClose: () => void;
  isLoading?: boolean;
}

type VarType = 'string' | 'number' | 'list' | 'dict' | 'bool' | 'null' | 'unknown';

/** Detect the type of a variable from its value string. */
function detectType(valueStr: string): VarType {
  const trimmed = valueStr.trim();
  if (trimmed === 'True' || trimmed === 'False') return 'bool';
  if (trimmed === 'None') return 'null';
  if (trimmed.startsWith('[') && trimmed.endsWith(']')) return 'list';
  if (trimmed.startsWith('{') && trimmed.endsWith('}')) return 'dict';
  if (trimmed.startsWith('"') || trimmed.startsWith("'")) return 'string';
  if (!isNaN(Number(trimmed)) && trimmed !== '') return 'number';
  return 'unknown';
}

/** Render the appropriate input for a given variable type. */
function TypeInput({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const varType = detectType(value);

  if (varType === 'list') {
    return (
      <textarea
        className={styles.listInput}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={3}
        placeholder='[1, 2, 3]'
      />
    );
  }
  if (varType === 'dict') {
    return (
      <textarea
        className={styles.dictInput}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={2}
        placeholder='{"key": "value"}'
      />
    );
  }
  if (varType === 'bool') {
    return (
      <select
        className={styles.selectInput}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="True">True</option>
        <option value="False">False</option>
      </select>
    );
  }
  if (varType === 'number') {
    return (
      <input
        type="number"
        className={styles.textInput}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="0"
      />
    );
  }
  // Default: text input
  return (
    <input
      type="text"
      className={styles.textInput}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={value || 'Enter value...'}
    />
  );
}

export function WhatIfModal({ steps, code, onSubmit, onClose, isLoading }: WhatIfModalProps) {
  // Extract variable names and their types from step 0 (or first step with variables)
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

  const handleChange = useCallback((name: string, newValue: string) => {
    setValues(prev => ({ ...prev, [name]: newValue }));
    if (newValue !== initialVars[name]?.value) {
      setChangedVars(prev => new Set(prev).add(name));
    } else {
      setChangedVars(prev => {
        const next = new Set(prev);
        next.delete(name);
        return next;
      });
    }
  }, [initialVars]);

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
          {Object.entries(initialVars).length === 0 ? (
            <p className={styles.noVars}>No variables detected at step 0.</p>
          ) : (
            Object.entries(initialVars).map(([name, info]) => (
              <div key={name} className={styles.varRow}>
                <div className={styles.varHeader}>
                  <span className={`${styles.varName} ${changedVars.has(name) ? styles.changed : ''}`}>
                    {changedVars.has(name) ? '● ' : ''}{name}
                  </span>
                  <span className={styles.varType}>{info.type}</span>
                </div>
                <TypeInput
                  value={values[name] ?? info.value}
                  onChange={(v) => handleChange(name, v)}
                />
                {changedVars.has(name) && (
                  <div className={styles.originalValue}>
                    was: {info.value}
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {changedList.length > 0 && (
          <div className={styles.summary}>
            <span className={styles.summaryLabel}>You changed:</span>
            <code className={styles.summaryCode}>
              {changedList.map(v => `${v} = ${values[v]}`).join(', ')}
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
            {isLoading ? '⏳ Replaying...' : '🔁 Replay from Here'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

**File:** `frontend/components/tracer/WhatIfModal.module.css` ⊕

```css
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.65);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.modal {
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 16px;
  padding: 32px;
  width: 560px;
  max-width: 90vw;
  max-height: 80vh;
  overflow-y: auto;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.5);
}

.header {
  margin-bottom: 24px;
}

.title {
  font-size: 22px;
  font-weight: 700;
  color: #f8fafc;
  margin: 0 0 8px 0;
}

.subtitle {
  font-size: 14px;
  color: #64748b;
  margin: 0;
}

.variables {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 20px;
}

.noVars {
  color: #64748b;
  font-size: 14px;
  text-align: center;
  padding: 24px;
}

.varRow {
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 10px;
  padding: 14px;
}

.varHeader {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.varName {
  font-size: 15px;
  font-weight: 600;
  color: #e2e8f0;
  font-family: 'Fira Code', 'Courier New', monospace;
}

.varName.changed {
  color: #fbbf24;
}

.varType {
  font-size: 12px;
  color: #64748b;
  background: #0f172a;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid #1e293b;
}

.textInput,
.selectInput,
.listInput,
.dictInput {
  width: 100%;
  padding: 8px 10px;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 6px;
  color: #22c55e;
  font-size: 13px;
  font-family: 'Fira Code', 'Courier New', monospace;
  box-sizing: border-box;
  resize: vertical;
}

.textInput:focus,
.selectInput:focus,
.listInput:focus,
.dictInput:focus {
  outline: none;
  border-color: #6366f1;
}

.originalValue {
  margin-top: 6px;
  font-size: 12px;
  color: #64748b;
  font-family: 'Fira Code', 'Courier New', monospace;
}

.summary {
  background: #1c1917;
  border: 1px solid #44403c;
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 20px;
}

.summaryLabel {
  font-size: 13px;
  color: #a8a29e;
  margin-right: 8px;
}

.summaryCode {
  font-size: 13px;
  color: #fbbf24;
  font-family: 'Fira Code', 'Courier New', monospace;
}

.actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.cancelBtn {
  padding: 10px 20px;
  background: transparent;
  border: 1px solid #334155;
  border-radius: 8px;
  color: #94a3b8;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.15s ease;
}
.cancelBtn:hover:not(:disabled) {
  background: #1e293b;
  color: #e2e8f0;
}

.replayBtn {
  padding: 10px 20px;
  background: #6366f1;
  border: none;
  border-radius: 8px;
  color: white;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  transition: all 0.15s ease;
}
.replayBtn:hover:not(:disabled) {
  background: #4f46e5;
}
.replayBtn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
```

---

### Phase 3E: Frontend — Wire What-If Into Tracer Page

**File:** `frontend/app/tracer/page.tsx`

#### SUB-TASK 3E-1: Import WhatIfModal

**Find `import { VariablePanel } from '@/components/tracer/VariablePanel';` (line 11) and ADD AFTER:**

```typescript
import { WhatIfModal } from '@/components/tracer/WhatIfModal';
```

#### SUB-TASK 3E-2: Add WhatIf state and update API import

**Find `const [error, setError] = useState<string | null>(null);` (line 66) and ADD AFTER:**

```typescript
  const [showWhatIf, setShowWhatIf] = useState(false);
  const [whatIfLoading, setWhatIfLoading] = useState(false);
```

**Find `import { api, saveTrace, shareTrace } from '@/lib/api';` and ADD `runTrace` if not already there (it should be imported as the standalone function):**

```typescript
// Ensure runTrace is imported (it's a standalone export, not part of the class)
import { api, saveTrace, shareTrace, runTrace as runTraceApi } from '@/lib/api';
```

#### SUB-TASK 3E-3: Add What-If button in footer

**Find `<div className={styles.lineActions}>` inside `<footer>` (around line 295) and ADD BEFORE the `<button className={styles.whyBtn}>`:**

```tsx
          <button
            className={styles.whatIfBtn}
            onClick={() => setShowWhatIf(true)}
            disabled={!traceResult || traceResult.steps.length === 0}
            title={!traceResult ? 'Run the trace first' : 'Modify initial values and replay'}
          >
            🔄 What If?
          </button>
```

#### SUB-TASK 3E-4: Add WhatIfModal render

**Find the closing `</div>` of `main` tag (before footer, around line 272) and ADD AFTER:**

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
              const result = await runTraceApi(code);
              if (result.error) {
                setError(result.error_message ?? result.error);
              } else {
                setTraceResult({
                  trace_id: result.trace_id ?? '',
                  steps: result.steps ?? [],
                  total_steps: result.total_steps ?? result.steps?.length ?? 0,
                  duration_ms: result.duration_ms ?? 0,
                });
              }
            } catch (err) {
              setError(err instanceof Error ? err.message : 'Failed to run trace');
            } finally {
              setWhatIfLoading(false);
            }
          }}
        />
      )}
```

**IMPORTANT:** Currently the `runTrace` API call does NOT support `initial_namespace`. The `api.runTrace` method needs to be updated to support it.

#### SUB-TASK 3E-5: Update `runTrace` API call to support `initial_namespace`

**File:** `frontend/lib/api.ts`

**Find the standalone `runTrace` function (line 322–335) and REPLACE with:**

```typescript
export async function runTrace(
  code: string,
  options?: {
    initialNamespace?: Record<string, string>;
  }
): Promise<{ trace_id: string; steps: TraceStep[]; total_steps: number; duration_ms: number; error?: string; error_message?: string }> {
  const body: Record<string, unknown> = { code };
  if (options?.initialNamespace) {
    body.initial_namespace = options.initialNamespace;
  }
  const res = await fetch(`${getApiBase()}/traces/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail?.error ?? err.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}
```

#### SUB-TASK 3E-6: Wire `initial_namespace` through the modal's `onSubmit`

**In `frontend/app/tracer/page.tsx`, update the `onSubmit` callback in the `WhatIfModal` render (SUB-TASK 3E-4) to pass `initialNamespace`:**

```typescript
          onSubmit={async (initialNamespace, changedVars) => {
            setShowWhatIf(false);
            setWhatIfLoading(true);
            setTraceResult(null);
            setError(null);
            reset();
            try {
              const result = await runTraceApi(code, { initialNamespace });
              if (result.error) {
                setError(result.error_message ?? result.error);
              } else {
                setTraceResult({
                  trace_id: result.trace_id ?? '',
                  steps: result.steps ?? [],
                  total_steps: result.total_steps ?? result.steps?.length ?? 0,
                  duration_ms: result.duration_ms ?? 0,
                });
              }
            } catch (err) {
              setError(err instanceof Error ? err.message : 'Failed to run trace');
            } finally {
              setWhatIfLoading(false);
            }
          }}
```

#### SUB-TASK 3E-7: Add CSS for What-If button

**Append to `frontend/app/tracer/page.module.css`:**

```css
.whatIfBtn {
  padding: 8px 16px;
  background: #1c1917;
  color: #fbbf24;
  border: 1px solid #44403c;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  transition: all 0.15s ease;
  display: flex;
  align-items: center;
  gap: 6px;
}
.whatIfBtn:hover:not(:disabled) {
  background: #292524;
  border-color: #57534e;
}
.whatIfBtn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
```

---

## ═══════════════════════════════════════════════

## FEATURE 5 — Trace Replay from Saved State

## ═══════════════════════════════════════════════

### Priority: 5 — Effort: XS (Extra Small)

### Concept

When a user loads a review card, the page should replay the saved trace steps (not re-execute code). Steps are already saved in DB (via the shared blocker fix). The review page just needs to use `useTrace` hook properly.

### What's Missing


| Missing                                                     | File                                     |
| ----------------------------------------------------------- | ---------------------------------------- |
| ✦ `steps` column in DB                                      | Fixed by SHARED BLOCKER FIX above        |
| Review page uses manual `setInterval` instead of `useTrace` | `frontend/app/review/[card_id]/page.tsx` |
| Review page doesn't use saved steps                         | `frontend/app/review/[card_id]/page.tsx` |
| Missing `useTrace` import                                   | `frontend/app/review/[card_id]/page.tsx` |
| No visual distinction for replay (REPLAY badge)             | `frontend/app/review/[card_id]/page.tsx` |


---

### Phase 5A: Frontend — Refactor Review Page to Use `useTrace` Hook

**File:** `frontend/app/review/[card_id]/page.tsx`

#### SUB-TASK 5A-1: Replace manual animation with `useTrace` hook

**This is the most impactful change — replaces 40+ lines of manual `requestAnimationFrame` code with the battle-tested `useTrace` hook.**

**Replace ALL of the component content (lines 30–243) with:**

```typescript
// frontend/app/review/[card_id]/page.tsx
'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { getSupabase } from '@/lib/supabase';
import { fetchReviewCard, submitReviewRating } from '@/lib/api';
import { formatNextReview } from '@/lib/sm2';
import type { ReviewCardDetail } from '@/types/user';
import { useTrace } from '@/hooks/useTrace';  // ← REPLACES manual rAF
import styles from './review.module.css';

const CodeEditor = dynamic(() => import('@/components/editor/CodeEditor').then(m => m.CodeEditor), {
  ssr: false,
  loading: () => <div className={styles.editorLoading}>Loading code...</div>,
});

type ReviewState = 'loading' | 'playing' | 'rating' | 'submitting' | 'submitted' | 'error';

const RATING_CONFIG: Record<'again' | 'hard' | 'good' | 'easy', { label: string; hint: string }> = {
  again: { label: 'Again', hint: 'Forgot it' },
  hard: { label: 'Hard', hint: 'Struggled' },
  good: { label: 'Good', hint: 'Got it' },
  easy: { label: 'Easy', hint: 'Too easy' },
};

export default function ReviewPage() {
  const params = useParams();
  const router = useRouter();
  const cardId = params.card_id as string;

  const [card, setCard] = useState<ReviewCardDetail | null>(null);
  const [reviewState, setReviewState] = useState<ReviewState>('loading');
  const [rating, setRating] = useState<'again' | 'hard' | 'good' | 'easy' | null>(null);
  const [nextReview, setNextReview] = useState<string | null>(null);
  const [nextInterval, setNextInterval] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // ← REPLAY: use saved steps from the card (NOT re-execution)
  // The backend returns card.trace.steps which comes from the traces.steps JSONB column.
  // This means NO re-execution needed — the trace is a complete replay recording.
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
        router.replace('/auth/login');
        return;
      }
      try {
        const loadedCard = await fetchReviewCard(cardId);
        setCard(loadedCard);
        // Use useTrace's autoPlay — steps are from saved state, not re-execution
        setReviewState('playing');
      } catch (err) {
        if (err instanceof Error && err.message === 'CARD_NOT_FOUND') {
          setError('Card not found. It may have already been reviewed.');
        } else if (err instanceof Error && err.message === 'AUTH_REQUIRED') {
          router.replace('/auth/login');
        } else {
          setError(err instanceof Error ? err.message : 'Failed to load card');
        }
        setReviewState('error');
      }
    }
    load();
  }, [cardId, router]);

  // Transition from playing → rating when playback ends
  useEffect(() => {
    if (playbackState === 'ended' && reviewState === 'playing') {
      setReviewState('rating');
    }
  }, [playbackState, reviewState]);

  const handleRating = useCallback(
    async (r: 'again' | 'hard' | 'good' | 'easy') => {
      setRating(r);
      setReviewState('submitting');
      try {
        const result = await submitReviewRating(cardId, r);
        setNextReview(result.next_review_date);
        setNextInterval(result.new_interval_days);
        setReviewState('submitted');
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to submit review');
        setReviewState('rating'); // Return to rating so user can retry
      }
    },
    [cardId]
  );

  if (reviewState === 'loading') {
    return (
      <div className={styles.page}>
        <div className={styles.loading}>
          <span className={styles.spinner}>◈</span> Loading review...
        </div>
      </div>
    );
  }

  if (reviewState === 'error') {
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

        {/* Step counter + manual controls (playing state) */}
        {reviewState === 'playing' && steps.length > 0 && (
          <>
            <div className={styles.stepCounter}>
              Step {currentStep + 1} / {steps.length}
            </div>
            <div className={styles.controlsRow}>
              <button onClick={stepBackward} disabled={currentStep === 0}>⏮</button>
              <button onClick={togglePlayPause}>{playbackState === 'playing' ? '⏸' : '▶'}</button>
              <button onClick={stepForward} disabled={currentStep >= steps.length - 1}>⏭</button>
            </div>
          </>
        )}

        {/* Rating buttons (rating state) */}
        {(reviewState === 'rating' || reviewState === 'submitting') && (
          <div className={styles.ratingPanel}>
            <h2 className={styles.ratingTitle}>
              {reviewState === 'submitting' ? 'Submitting...' : 'How well did you understand this?'}
            </h2>
            <div className={styles.ratingButtons}>
              {(['again', 'hard', 'good', 'easy'] as const).map(r => (
                <button
                  key={r}
                  onClick={() => handleRating(r)}
                  disabled={reviewState === 'submitting' || rating !== null}
                  className={`${styles.ratingBtn} ${styles[`ratingBtn_${r}`]}`}
                >
                  <span className={styles.ratingLabel}>{RATING_CONFIG[r].label}</span>
                  <span className={styles.ratingHint}>{RATING_CONFIG[r].hint}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {reviewState === 'submitted' && (
          <div className={styles.submittedPanel}>
            <div className={styles.submittedIcon}>✓</div>
            <h2 className={styles.submittedTitle}>Review complete!</h2>
            {nextReview && nextInterval !== null && (
              <p className={styles.submittedInfo}>
                Next review: <strong>{formatNextReview(new Date(nextReview))}</strong> (
                {nextInterval === 1 ? '1 day' : `${nextInterval} days`})
              </p>
            )}
            <button onClick={() => router.push('/dashboard')} className={styles.dashboardBtn}>
              ← Back to Dashboard
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
```

#### SUB-TASK 5A-2: Add CSS for replay badge and controls

**Append to `frontend/app/review/[card_id]/review.module.css`:**

```css
.replayBadge {
  font-size: 11px;
  padding: 3px 8px;
  background: #1c1917;
  color: #fbbf24;
  border: 1px solid #44403c;
  border-radius: 4px;
  font-weight: 600;
  letter-spacing: 0.02em;
  margin-left: 8px;
}

.stepCounter {
  text-align: center;
  font-size: 13px;
  color: #64748b;
  margin-bottom: 8px;
}

.controlsRow {
  display: flex;
  justify-content: center;
  gap: 12px;
  margin-bottom: 16px;
}

.controlsRow button {
  padding: 8px 16px;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  color: #e2e8f0;
  cursor: pointer;
  font-size: 16px;
  transition: all 0.15s ease;
}
.controlsRow button:hover:not(:disabled) {
  background: #334155;
}
.controlsRow button:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
```

---

### Phase 5B: Backend — Ensure Review Card Endpoint Returns Steps

**File:** `backend/app/routers/review.py`

**Verify the `GET /review/{card_id}` endpoint returns steps:**
The existing endpoint (lines 224–246) already returns `trace_data` with `steps`. Since we added `steps` to the traces table via the shared blocker fix, this should now work automatically. The critical line is:

```python
steps = json.loads(trace_data.get("steps", "[]")) if trace_data.get("steps") else []
```

**This line already exists** — no changes needed. The steps will now be available because:

1. Migration V003 added the `steps` JSONB column
2. Save endpoint now includes `steps` in the payload (Phase 1C)
3. Review endpoint reads `steps` from the trace record

**Verification:** After completing all tasks, test by:

1. Running a trace and saving it
2. Loading the review card at `/review/{card_id}`
3. The animation should play from the saved steps (NOT re-executing the code)

---

## ═══════════════════════════════════════════════

## PHASE ORDER & DEPENDENCY GRAPH

## ═══════════════════════════════════════════════

```
[START]
    │
    ├─► [DB Migrations — in any order]
    │       V002 (share columns)
    │       V003 (steps column)
    │
    ├─► [Phase 1C] Backend: Save endpoint includes steps
    │       │
    │       └─► [Phase 1B] Backend: Share endpoint with expiry/password
    │               │
    │               └─► [Phase 1D] Frontend: Share button + modal
    │                       │
    │                       └─► [Phase 1E] Frontend: Shared page update (fork, password, expiry)
    │                               │
    │                               └─► [Phase 1F] Frontend: Open Graph meta tags
    │
    └─► [Phase 3A] Backend: tracer.py accepts initial_namespace
            │
            ├─► [Phase 3B] Backend: runner.py passes initial_namespace
            │       │
            │       └─► [Phase 3C] Backend: API endpoint accepts initial_namespace
            │               │
            │               └─► [Phase 3D] Frontend: WhatIfModal component
            │                       │
            │                       └─► [Phase 3E] Frontend: Wire into tracer page
            │
            └─► [Phase 5A] Frontend: Review page uses useTrace hook
                    │
                    └─► [Phase 5B] Backend: Verify review endpoint returns steps
```

---

## ═══════════════════════════════════════════════

## VERIFICATION CHECKLIST

## ═══════════════════════════════════════════════

### Feature 1 — Shared Trace Links

- Migration V002 applied → `traces` has `expires_at` and `password_hash` columns
- Migration V003 applied → `traces` has `steps` JSONB column
- `shareTrace()` API accepts `{expiration_days, password}` options
- Shared page shows password gate for protected links
- Shared page shows 410 expiry message for expired links
- "Share" button appears on tracer toolbar when trace is loaded
- Share modal shows expiration dropdown and password field
- Share modal shows generated URL with copy button
- Fork button appears on shared page for authenticated users
- Fork creates new trace and redirects to it
- Analytics are logged on each shared trace view

### Feature 3 — What-If Sandbox

- Backend `run_trace()` accepts `initial_namespace` parameter
- Runner passes `initial_namespace` to subprocess
- API endpoint `POST /traces/run` accepts `initial_namespace` in body
- What-If button appears in tracer footer
- What-If modal shows type-appropriate inputs (text, number, list JSON, bool select)
- Replaying with modified namespace shows changed variables highlighted
- Original values shown as "was: X" below modified fields

### Feature 5 — Trace Replay from Saved State

- Steps are saved to DB when saving a trace
- `GET /review/{card_id}` returns `trace.steps` from DB
- Review page plays animation from saved steps (NOT re-executing)
- Review page uses `useTrace` hook (not manual rAF)
- REPLAY badge shown in review page header
- Manual step controls available during playback

### Smoke Tests

- Run `pytest backend/tests/` — all tests pass
- Run `cd frontend && npm test` — all tests pass
- `cd frontend && npm run build` — build succeeds
- Create a trace → save → share → open shared link → replay works
- Create a trace → open What-If → change `items = []` → replay shows modified execution
- Save a trace → open dashboard → click review → animation plays from saved steps

