# CodeScope Architecture

**Metadata:**

- **Version:** 1.1
- **Date:** 2026-04-30
- **Author:** [Author]
- **Status:** Draft — for implementation
- **Based on:** `codescope_prd.md`, `codescope_analysis.md`, `research_report.md`
- **Assumptions:** No formal research study. Study mode, telemetry pipeline, and evaluation pipeline are out of scope. CodeScope is built as a working product demo/tool.

---

## 1. System Context

CodeScope is a browser-based Python code comprehension tool. A user pastes AI-generated Python code, watches it execute step-by-step with animated variable state, and can ask "why is this here?" for any line.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              BROWSER (User's Device)                           │
│                                                                                 │
│   Next.js (Vercel)                                                             │
│   ├── Monaco editor (code input, line highlighting)                             │
│   ├── Variable state panel (live display of locals)                             │
│   ├── Animation controls (play/pause/step)                                      │
│   ├── "Why is this here?" panel (SSE streaming response)                        │
│   └── Save / Share action bar                                                  │
└────────────────────┬──────────────────────────────────────────────────────────┘
                     │ HTTPS POST /api/traces/run  (user code → steps JSON)
                     │ HTTPS GET  /api/llm/explain/stream  (SSE streaming)
                     │ HTTPS POST /api/traces  (authenticated)
                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         RAILWAY (FastAPI Backend)                               │
│                                                                                 │
│   FastAPI (Python 3.12+)                                                        │
│   ├── /api/traces/run    → spawns tracer subprocess, returns step JSON        │
│   ├── /api/llm/explain/stream  → SSE → Ollama Cloud / Claude fallback         │
│   ├── /api/traces        → CRUD on saved traces                                │
│   ├── /api/review/*      → spaced repetition operations (Month 3+)             │
│                                                                                 │
│   tracer/  (pip-installable library, subprocess-isolated)                       │
│   ├── tracer.py        — sys.settrace() bytecode instrumentation                 │
│   ├── validator.py     — side-effect detection (import/open/requests/eval)       │
│   └── models.py        — TraceStep, VariableState dataclasses                   │
│                                                                                 │
│   services/                                                                          │
│   ├── llm_router.py    — Ollama Cloud → local Ollama → Claude fallback           │
│   ├── cache.py         — content-addressable cache for explanations             │
│   └── tracer_runner.py — Subprocess spawn + resource limits + 5s timeout        │
└────────────────────┬──────────────────────────────────────────────────────────┘
                     │ SSE token stream (one token per event)
                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Ollama Cloud (ollama.com/api)                       │
│   Primary LLM provider. Free, zero-setup, no GPU required.                      │
│   No account needed by end users. Your API key not required — ollama.com hosts.  │
└─────────────────────────────────────────────────────────────────────────────────┘
          ↑                          ↑
          │ (fallback only)          │ (default)
          ▼                          │
┌──────────────────────┐              │
│   Claude Sonnet 4    │              │
│   (Anthropic API)    │              │
│   ANTHROPIC_API_KEY  │◄─────────────┘
│   env var on Railway │
└──────────────────────┘

  ┌──────────────────────────────────────────────────────┐
  │   MODAL.COM (Developer Testing Only)                   │
  │   Free GPU tier for testing Ollama integration.        │
  │   NOT used by study participants.                      │
  └──────────────────────────────────────────────────────┘
```

**Key design decision — Tracer placement:** The tracer runs as an **isolated Python subprocess spawned by FastAPI per request**. The subprocess executes the user's code with `sys.settrace()` active, captures step data, and returns JSON. The tracer subprocess is killed after 5 seconds or 500 steps, whichever comes first. The subprocess does NOT share memory with the FastAPI process.

**Key design decision — LLM routing:** Ollama Cloud (`https://ollama.com/api`) is the primary explanation provider — free, zero setup, no GPU required. Claude Sonnet 4 is the fallback when Ollama Cloud is unavailable or times out.

**Note on subprocess resource limits:** `resource.setrlimit()` used in the tracer subprocess is a Unix-only API. Railway runs Linux containers, so this works correctly in production. On Windows developer machines, the subprocess runs without CPU/memory limits enforced — the 5-second `communicate(timeout=5)` still functions as the primary guard on all platforms. For stricter cross-platform resource control, consider gVisor or a Docker-based sandbox in a future iteration.

---

## 2. Ollama Strategy

Three-tier configuration, controlled by the `ollama_endpoint` field in the Profile model:


| Tier                  | Endpoint                 | Cost                   | Use Case                                                             |
| --------------------- | ------------------------ | ---------------------- | -------------------------------------------------------------------- |
| **Primary (default)** | `https://ollama.com/api` | Free                   | All users in production. Zero setup, no GPU required.                |
| **Developer testing** | Modal.com free GPU       | Free                   | You testing Ollama integration on a cloud GPU. Not visible to users. |
| **Optional override** | `localhost:11434`        | Free (user's hardware) | Users with local Ollama who want full privacy.                       |


**Implementation — `llm_router.py` tries endpoints in order:**

```
1. Read ollama_endpoint from user profile (default: https://ollama.com/api)
2. Try POST {endpoint}/chat with model=llama3.2, 8s timeout
   → success: stream SSE tokens back to client
   → timeout/error: continue to step 3
3. If profile.ollama_endpoint == localhost:11434 (not already tried)
   → try localhost:11434/chat, 8s timeout
   → success: stream SSE
   → error: continue to step 4
4. Try Anthropic Claude API (ANTHROPIC_API_KEY env var), 10s timeout
   → success: stream SSE
   → error: return HTTP 500
     "Explanation service is temporarily unavailable. Please try again."
```

**Important clarification on Ollama Cloud:** Ollama Cloud at `ollama.com/api` is a hosted service operated by Ollama — your users do NOT need an Ollama account. You (the developer) do NOT need to provide an Ollama API key. The service is free at current usage levels. Your users' code (code snippet + line number + variable state) is sent to Ollama's servers. If this is unacceptable for a given use case, users can switch to `localhost:11434` (local Ollama, fully private) in their profile settings.

---

## 3. Component Architecture

### 3.1 Frontend (Next.js 16, App Router, TypeScript)

**Directory structure:**

```
frontend/
├── app/
│   ├── page.tsx                   # Landing page
│   ├── tracer/
│   │   └── page.tsx               # Main tracer tool
│   ├── dashboard/
│   │   └── page.tsx               # Saved traces + review queue
│   ├── trace/[share_token]/
│   │   └── page.tsx               # Shared trace (read-only, no auth required)
│   └── auth/
│       ├── login/page.tsx
│       └── signup/page.tsx
├── components/
│   ├── editor/
│   │   ├── CodeEditor.tsx          # Monaco wrapper (dark theme, Python lang)
│   │   └── CodeEditor.module.css
│   ├── tracer/
│   │   ├── VariablePanel.tsx       # Live variable display with type badges + pulse
│   │   ├── VariablePanel.module.css
│   │   ├── AnimationControls.tsx    # Play/Pause/Step/Back + speed selector
│   │   └── AnimationControls.module.css
│   ├── llm/
│   │   ├── ExplanationPanel.tsx     # SSE streaming response display
│   │   └── ExplanationPanel.module.css
│   ├── errors/
│   │   └── ErrorBoundary.tsx       # React error boundaries (per-panel isolation)
│   └── ui/
│       ├── Button.tsx
│       └── Modal.tsx
├── lib/
│   ├── api.ts                     # Typed fetch wrappers for all API endpoints
│   ├── sm2.ts                    # SM-2 spaced repetition algorithm
│   └── supabase.ts               # Supabase client (auth + DB reads)
├── hooks/
│   ├── useTrace.ts               # rAF-based animation loop (replaces setInterval)
│   └── useStreamingExplanation.ts # SSE connection with auto-retry + exponential backoff
├── i18n/
│   ├── i18n.ts                   # next-intl config (EN + VI supported)
│   └── locales/
│       ├── en.json               # English translations (31 keys)
│       └── vi.json               # Vietnamese translations
└── types/
    └── trace.ts                   # TraceStep, VariableState, CallFrame types
```

**State management:** React Context for global user state (auth, Pro status). URL state for trace playback position (`?step=5`). No external state library needed at MVP scale.

**Animation loop (`useTrace.ts`):** The animation loop uses `requestAnimationFrame` with elapsed time tracking, not `setInterval`. This is critical for correctness:

```
Speed 1× → 750ms per step
Speed 2× → 375ms per step
Speed 5× → 150ms per step
Speed 0.5× → 1500ms per step

Behavior:
  Play:  rAF fires → check elapsed → advance step if ≥ intervalMs → schedule next rAF
  Pause: cancelAnimationFrame → current step preserved
  Step forward: cancel rAF → advance one step → stay paused
  Step backward: cancel rAF → retreat one step (step > 0 only) → stay paused
  End of trace: cancel rAF automatically

Why not setInterval?
  - setInterval fires even when tab is backgrounded → steps accumulate and jump when tab returns
  - rAF is synchronized with the rendering refresh cycle → no drift
  - Tab visibility handler pauses the loop when document.hidden = true
```

**Keyboard shortcuts:**
  Space     → play/pause
  ArrowRight → step forward (pauses if playing)
  ArrowLeft  → step backward (pauses if playing)
  Home       → reset to step 0
  End        → jump to last step

**Monaco configuration:**

- Language: Python
- Theme: `vs-dark` (VS Code Dark+)
- Line numbers: on
- Minimap: off
- Collaborative editing: disabled
- Read-only mode: used for shared trace view (read-only replay)

**SSE streaming for "Why is this here?":** The ExplanationPanel connects to `GET /api/llm/explain/stream` via `EventSource`. The SSE stream renders token-by-token with a blinking cursor. The trace remains fully interactive (play/pause/step) while the explanation streams — these are independent UI panels.

**API base URL in production:** The frontend reads `NEXT_PUBLIC_API_URL` from environment. In Vercel, this is set to the Railway public URL (`https://codescope-api.up.railway.app`). CORS is configured on Railway to allow `https://codescope.vercel.app`.

### 3.2 Backend (FastAPI, Python 3.12+)

**Directory structure:**

```
backend/
├── app/
│   ├── main.py                    # FastAPI app entry point, CORS config, lifespan
│   ├── config.py                  # Environment variables, validated at startup
│   ├── concurrency.py              # asyncio.Semaphore — max concurrent trace executions
│   ├── routers/
│   │   ├── traces.py             # /api/traces, /api/traces/run, /api/traces/{id}
│   │   ├── llm.py               # /api/llm/explain/stream (SSE)
│   │   ├── review.py             # /api/review/* (SM-2 spaced repetition)
│   │   └── profiles.py           # /api/profiles/me (update ollama_endpoint)
│   ├── services/
│   │   ├── llm_router.py         # Ollama Cloud → local Ollama → Claude fallback
│   │   ├── rate_limit.py         # Redis-backed distributed rate limiter (Lua script)
│   │   └── tracer_runner.py      # Subprocess spawn + resource limits + 5s timeout
│   └── models/
│       └── schemas.py            # Pydantic request/response models
├── tracer/                       # pip-installable library (publishable to PyPI)
│   ├── __init__.py
│   ├── tracer.py                 # sys.settrace() + branch detection (AST + bytecode)
│   ├── validator.py              # Side-effect pattern detection (20+ patterns)
│   ├── models.py                 # TraceStep, VariableState dataclasses
│   └── py.typed                 # PEP 561 marker — type hints included
├── migrations/                   # Supabase SQL migrations
│   ├── V001__initial_schema.sql
│   └── V002__add_explanations.sql
├── tests/
│   ├── unit/
│   │   ├── test_tracer.py        # Bytecode trace + branch detection (20 test cases)
│   │   ├── test_validator.py     # Side-effect detection tests
│   │   └── test_llm_router.py   # Provider fallback tests
│   └── integration/
│       └── test_trace_flow.py    # End-to-end trace request tests
├── Dockerfile
├── pyproject.toml               # Includes pytest, ruff, mypy in dev dependencies
└── .env.example
```

**Concurrency limiter (`concurrency.py`):**

```python
# Concurrency limiter — prevents Railway instance from being overwhelmed
# by a burst of simultaneous trace requests.
#
# One Semaphore is created per FastAPI worker process (uvicorn workers=N).
# With N=2 workers and limit=25 per worker: 50 concurrent traces total.
#
# If the semaphore is full, requests queue in the async event loop —
# no threads are consumed while waiting. This is the correct pattern for I/O-bound
# subprocess calls.

import asyncio

TRACE_CONCURRENCY_LIMIT = 25  # per worker process
_semaphore = asyncio.Semaphore(TRACE_CONCURRENCY_LIMIT)

async def run_with_concurrency_limit(fn, *args, **kwargs):
    async with _semaphore:
        return fn(*args, **kwargs)
```

**Subprocess management (`tracer_runner.py`):**

```python
import subprocess
import resource
import json
import uuid
import os

MAX_STEPS = 500
TIMEOUT_SECONDS = 5
TRACER_LIB_PATH = os.path.join(os.path.dirname(__file__), "..", "tracer")

def run_trace(code: str) -> dict:
    """Spawns a subprocess, runs tracer, returns step JSON."""
    trace_id = str(uuid.uuid4())

    # Write code to a temp file to avoid shell injection from inline code
    temp_file = f"/tmp/codescope_trace_{trace_id}.py"
    with open(temp_file, "w") as f:
        f.write(code)

    try:
        # Build inline Python script that imports tracer and prints result
        script = f"""
import sys
sys.path.insert(0, '{TRACER_LIB_PATH}')
from tracer.tracer import run_trace
import json
result = run_trace(open('{temp_file}').read(), max_steps={MAX_STEPS})
print(json.dumps(result))
"""
        proc = subprocess.Popen(
            ["python", "-c", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            stdout, stderr = proc.communicate(timeout=TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return {"error": "TIMEOUT", "message": "Execution exceeded 5 seconds"}

    finally:
        # Clean up temp file
        if os.path.exists(temp_file):
            os.remove(temp_file)

    if proc.returncode != 0:
        return {"error": "RUNTIME_ERROR", "message": stderr.decode()}

    return json.loads(stdout.decode())
```

**On `resource.setrlimit()` and Windows:** `resource.setrlimit()` is Unix-only. Railway uses Linux containers, so the limits work in production. On Windows development machines, the 5-second `communicate(timeout=5)` remains the functional timeout. The architecture is designed for Railway's Linux target. If stricter cross-platform sandboxing is needed, migrate the tracer to gVisor or a Docker-in-Docker container in a future iteration.

**Rate limiting implementation (`services/rate_limit.py`):**

```python
# Redis-backed distributed rate limiter — works correctly across all Railway instances.
# In-memory fallback logs a warning for single-instance correctness only.

# Redis is the primary store. If unavailable, falls back to in-memory dict
# but logs a warning that multi-instance deployments may allow bypass.

# Algorithm: Sliding window counter via Redis Lua script (atomic read-modify-write)

_redis_client = redis.asyncio.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)

RATE_LIMIT = 20       # requests per hour
WINDOW_SECONDS = 3600 # 1 hour sliding window

LUA_SCRIPT = """
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window_seconds = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local window_start = now - window_seconds

local data = redis.call('GET', key)
local count, ws = 0, now

if data then
    local parsed = cjson.decode(data)
    count, ws = parsed.count or 0, parsed.window_start or now
    if ws < window_start then count, ws = 0, now end  -- window expired
end

if count >= limit then
    return {0, 0, ws + window_seconds, math.ceil(ws + window_seconds - now)}
end

count = count + 1
redis.call('SET', key, cjson.encode({count=count, window_start=ws}), 'EX', window_seconds * 2)
return {1, limit - count, ws + window_seconds, 0}
"""

async def check_rate_limit(key: str) -> RateLimitResult:
    redis_key = f"rate_limit:{key}"
    result = await _redis_client.eval(LUA_SCRIPT, 1, redis_key, RATE_LIMIT, WINDOW_SECONDS, time.time())
    allowed, remaining, reset_at, retry_after = result
    return RateLimitResult(allowed=bool(allowed), remaining=remaining,
                           reset_at=reset_at, retry_after_seconds=int(retry_after))
```

> **Why Redis?** The original in-memory `threading.Lock` approach breaks on Railway with 2+ uvicorn workers: each worker has its own memory, so a user hitting worker 1 then worker 2 gets 2× the configured rate limit. Redis provides a single source of truth across all instances. The Lua script guarantees atomicity — no race conditions under concurrent requests.

> **Fallback:** If Redis is unavailable at startup, the service logs a warning and falls back to in-memory counting. This is noted as single-instance-only in logs so operators know to add Redis.

**CORS configuration (`main.py`):**

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://codescope.vercel.app",  # Production Vercel
        "http://localhost:3000",          # Local dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**SSE streaming for explanations (`routers/llm.py`):**

```python
from fastapi import APIRouter, Query, HTTPException
from sse_starlette.sse import EventSourceResponse
import json

@router.get("/api/llm/explain/stream")
async def stream_explanation(
async def stream_explanation(
    code: str = Query(..., max_length=5000),
    line_number: int = Query(..., ge=1),
    line_content: str = Query(..., max_length=500),
    locals_json: str = Query(..., max_length=2000),
):
    # Validate inputs
    if len(code) > 5000:
        raise HTTPException(422, "code exceeds maximum length of 5000 characters")
    try:
        locals_dict = json.loads(locals_json)
    except json.JSONDecodeError:
        raise HTTPException(422, "locals_json must be valid JSON")

    async def event_generator():
        try:
            async for token in llm_router.stream_explain(
                code, line_number, line_content, locals_dict
            ):
                yield {"event": "message", "data": token}
            yield {"event": "done", "data": ""}
        except Exception as e:
            logger.error("sse_stream_error", error=str(e))
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(event_generator())
```

### 3.3 The Tracer Library (`tracer/`)

This is the core technical component. It is a pip-installable Python library that can be extracted and published to PyPI post-project.

**How `sys.settrace()` works:**

CPython executes bytecode, not source lines. Each bytecode instruction fires the tracer callback. The tracer groups consecutive bytecode events into source-line events:

```python
import sys
import dis
import time
from dataclasses import dataclass, asdict

@dataclass
class TraceStep:
    step_number: int
    line_number: int
    bytecode_offset: int
    opcode: str
    variables: dict        # {name: {"type": str, "value": str, "changed": bool}}
    call_depth: int
    branches_taken: dict  # e.g., {"if": True, "for": 0}
    duration_ms: float    # time spent on this step

def run_trace(source: str, max_steps: int = 500) -> dict:
    """
    Executes `source` with sys.settrace() active.
    Returns: {"steps": [TraceStep, ...], "total_steps": int, "duration_ms": float}
    """
    steps: list[TraceStep] = []
    prev_line = None
    local_state: dict = {}
    start_time = time.monotonic()

    # Pre-compile to get bytecode instruction list for opcode resolution
    try:
        compiled = compile(source, "<codescope>", "exec")
    except SyntaxError as e:
        return {"error": "SYNTAX_ERROR", "message": str(e), "line": e.lineno}

    # Build a map from instruction offset to source line for opcode resolution
    instr_map = {instr.offset: instr.opname for instr in dis.get_instructions(source)}

    def trace(frame, event, arg):
        nonlocal prev_line, local_state

        if len(steps) >= max_steps:
            return None  # stop tracing

        if event == "line":
            # Resolve opcode at current bytecode position
            opcode = instr_map.get(frame.f_lasti, "UNKNOWN")

            # Capture local variables at this frame
            new_local_state = {}
            for name, val in frame.f_locals.items():
                if name.startswith("__"):
                    continue
                val_repr = repr(val)[:200]
                is_new = name not in local_state
                changed = not is_new and local_state[name]["value"] != val_repr
                new_local_state[name] = {
                    "type": type(val).__name__,
                    "value": val_repr,
                    "changed": changed,
                }
            local_state = new_local_state

            step = TraceStep(
                step_number=len(steps),
                line_number=frame.f_lineno,
                bytecode_offset=frame.f_lasti,
                opcode=opcode,
                variables=local_state,
                call_depth=len(frame.f_code.co_freevars),
                branches_taken={},
                duration_ms=0.0,  # populated after all steps collected
            )
            steps.append(step)
            prev_line = frame.f_lineno

        elif event == "return":
            return None  # stop tracing on function return

        return trace

    try:
        sys.settrace(trace)
        exec(compiled, {"__name__": "__codescope__"})
    finally:
        sys.settrace(None)

    total_duration = (time.monotonic() - start_time) * 1000

    # Backfill duration_ms per step (approximate, proportional)
    if steps and total_duration > 0:
        per_step = total_duration / len(steps)
        for step in steps:
            step.duration_ms = round(per_step, 2)

    return {
        "steps": [asdict(s) for s in steps],
        "total_steps": len(steps),
        "duration_ms": round(total_duration, 2),
    }
```

**What the tracer captures per step:**

- `line_number` — which source line is executing
- `variables` — all local variables with type, truncated value, and a `changed` flag
- `call_depth` — nesting level (approximation via freevars count)
- `branches_taken` — branch decision info for `if`/`for`/`while`/`and_or` (v1 now captures this)
- `step_number` — sequential position in the trace
- `duration_ms` — estimated time spent on this step

**Branch detection (v1 — IMPLEMENTED):**

> **Change from PRD v2.0:** The original PRD noted `branches_taken` as a future enhancement. In implementation, branch detection was added in the first iteration because it directly undermines the product's core promise: users cannot understand AI-generated code without knowing which branch fired.

Branch detection works by combining **AST analysis** (before execution) with **bytecode opcode inspection** (during execution):

1. **AST pre-pass** (`_parse_ast_for_jumps`): Before running the tracer, the AST is parsed to find all conditional nodes (`ast.If`, `ast.For`, `ast.While`, `ast.BoolOp`) and their target lines. This builds a map of where each branch leads.
2. **Bytecode inspection** (`_detect_branch`): During `sys.settrace()` execution, specific bytecode opcodes are detected:
  - `POP_JUMP_IF_TRUE` → condition was truthy → "if" branch taken
  - `POP_JUMP_IF_FALSE` → condition was falsy → "else" branch taken (or loop condition check)
  - `FOR_ITER` → for loop iteration fired → capture iteration count
  - `JUMP_IF_TRUE_OR_POP` / `JUMP_IF_FALSE_OR_POP` → boolean short-circuit decision
3. **Loop iteration tracking**: `FOR_ITER` bytecode events are counted per source line to produce `iteration: N` for each loop step.

```python
@dataclass
class BranchInfo:
    branch_type: str   # 'if' | 'for' | 'while' | 'ternary' | 'and_or'
    taken: Optional[bool]   # True = if branch, False = else branch
    line: int
    iteration: int = 0      # 0 = not a loop
```

Example output for a nested if:

```
Step 3:  if x > 10:
  → branches_taken: {"type": "if", "taken": True, "line": 3}
Step 4:      result = "big"
  → branches_taken: {}
Step 5:  elif x > 5:
  → branches_taken: {"type": "if", "taken": False, "line": 5}
Step 7:      result = "medium"
```

**What the tracer does NOT capture:**

- Global variables outside the executed function
- Object internals (only `repr()` is captured)
- Code outside the provided snippet (imports, other modules)
- Branch decisions for `if`/`for`/`while` — `branches_taken` is always `{}` in v1

**Side-effect detection (`validator.py`):**

```python
SIDE_EFFECT_PATTERNS = [
    r"\bimport\s+(os|sys|subprocess|requests|urllib|httpx|socket|sqlite3|pickle)",
    r"\bopen\s*\(",
    r"\brequests\.",
    r"\bos\.",
    r"\bsubprocess\.",
    r"\beval\s*\(",
    r"\bexec\s*\(",
    r"\b__import__\s*\(",
    r"\bgetattr\s*\(",
    r"\bsetattr\s*\(",
    r"\binput\s*\(",
    r"\bprint\s*\(",          # harmless but flagged for review
]

def detect_side_effects(code: str) -> list[dict]:
    """Returns [{pattern: str, matched: str}, ...] for all detected patterns."""
    import re
    found = []
    for pattern in SIDE_EFFECT_PATTERNS:
        match = re.search(pattern, code)
        if match:
            found.append({"pattern": pattern, "matched": match.group()})
    return found

def validate_code(code: str) -> tuple[bool, list[dict]]:
    """
    Returns (is_valid, detected_side_effects).
    is_valid=False means execution should be blocked.
    """
    effects = detect_side_effects(code)
    # print() is flagged but does not block execution — warning only
    blocking_effects = [e for e in effects if "print" not in e["pattern"]]
    return len(blocking_effects) == 0, blocking_effects
```

### 3.4 Database (Supabase / PostgreSQL)

**Migrations:** Supabase CLI (`supabase db push`) or Flyway. All migrations live in `backend/migrations/`.

**Final data models (no study/telemetry tables):**

```sql
-- V001__initial_schema.sql

CREATE TABLE profiles (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    experience_level TEXT CHECK (experience_level IN ('student', 'junior', 'mid')),
    ai_tools_usage   TEXT CHECK (ai_tools_usage IN ('none', 'light', 'moderate', 'heavy')),
    python_years     INT DEFAULT 0,
    ollama_endpoint  TEXT DEFAULT 'https://ollama.com/api',
    stripe_customer_id TEXT,
    plan             TEXT DEFAULT 'free' CHECK (plan IN ('free', 'pro')),
    created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE traces (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID REFERENCES profiles(id) ON DELETE CASCADE,
    code         TEXT NOT NULL,
    language     TEXT DEFAULT 'python',
    steps        JSONB NOT NULL,
    concept_tags TEXT[] DEFAULT '{}',
    is_public    BOOLEAN DEFAULT false,
    share_token  TEXT UNIQUE DEFAULT encode(gen_random_bytes(16), 'hex'),
    created_at   TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE review_cards (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID REFERENCES profiles(id) ON DELETE CASCADE,
    trace_id         UUID REFERENCES traces(id) ON DELETE CASCADE,
    concept_tag      TEXT,
    easiness_factor  FLOAT DEFAULT 2.5,
    interval_days    INT DEFAULT 1,
    repetitions      INT DEFAULT 0,
    next_review_date DATE,
    last_reviewed_at TIMESTAMPTZ,
    created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE explanations (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id          UUID REFERENCES traces(id) ON DELETE CASCADE,
    line_number       INT NOT NULL,
    explanation_text  TEXT NOT NULL,
    cache_key         TEXT NOT NULL,    -- SHA-256 of (code + line_number + line_content[:50])
    model_used        TEXT DEFAULT 'ollama',  -- 'ollama' | 'claude'
    model_name        TEXT,
    cached            BOOLEAN DEFAULT false,
    human_rating      INT CHECK (human_rating BETWEEN 1 AND 5),
    pattern_category  TEXT,
    created_at        TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_explanations_cache_key ON explanations(cache_key);

-- RLS Policies
ALTER TABLE profiles         ENABLE ROW LEVEL SECURITY;
ALTER TABLE traces           ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_cards    ENABLE ROW LEVEL SECURITY;
ALTER TABLE explanations    ENABLE ROW LEVEL SECURITY;

CREATE POLICY "own_profile"    ON profiles      FOR ALL USING (user_id = auth.uid());
CREATE POLICY "own_traces"     ON traces        FOR ALL USING (user_id = auth.uid());
CREATE POLICY "public_traces" ON traces        FOR SELECT USING (is_public = true);
CREATE POLICY "own_cards"       ON review_cards  FOR ALL USING (user_id = auth.uid());
CREATE POLICY "own_explanations" ON explanations FOR ALL
    USING (trace_id IN (SELECT id FROM traces WHERE user_id = auth.uid()));
```

**Schema differences from PRD v1.1 (removed):**

- `TelemetryEvent` table — removed (no formal study)
- `TelemetrySession` table — removed (no formal study)
- `study_consent_given` field in Profile — removed
- `judge_answer` / `judge_confidence` fields in Explanations — removed (no evaluation pipeline)
- `cache_key` column added to Explanations — required for the caching layer

### 3.5 AI Layer (LLM Router + Streaming)

**Provider selection logic (`llm_router.py`):**

```
1. Ollama Cloud (https://ollama.com/api)
   - Model: llama3.2 (default, fast)
   - Timeout: 8 seconds
   - If success → stream SSE tokens to client

2. Local Ollama (localhost:11434)
   - Only tried if profile.ollama_endpoint is localhost:11434
   - Same model (llama3.2)
   - Timeout: 8 seconds

3. Anthropic Claude Sonnet 4
   - Requires ANTHROPIC_API_KEY in Railway environment
   - Timeout: 10 seconds

4. All fail → return HTTP 500
   "Explanation service is temporarily unavailable. Please try again."
```

**Explanation caching:** Before calling any LLM, check if an explanation is already cached:

```python
import hashlib
import json

def make_cache_key(code: str, line_number: int, line_content: str) -> str:
    payload = json.dumps({
        "code": code[:200],
        "ln": line_number,
        "lc": line_content[:50],
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()

def get_cached(key: str) -> str | None:
    row = supabase.table("explanations").select(
        "explanation_text"
    ).eq("cache_key", key).execute()
    if row.data:
        # Mark as cached for analytics
        return row.data[0]["explanation_text"]
    return None

def store_cached(key: str, text: str, model_used: str, model_name: str) -> None:
    try:
        supabase.table("explanations").insert({
            "cache_key": key,
            "explanation_text": text,
            "model_used": model_used,
            "model_name": model_name,
            "cached": True,
        }).execute()
    except Exception as e:
        # Log but don't fail — explanation was already streamed successfully to the user.
        # Worst case: next identical request regenerates the explanation.
        logger.warning("cache_store_failed", key=key, error=str(e))
```

Cached explanations are stored with a `cache_key` column. Repeat requests return instantly (zero API cost, zero rate-limit cost). No TTL in v1 — cache entries are permanent unless manually purged.

**Streaming implementation (`llm_router.py`):**

```python
SYSTEM_PROMPT = """You are a Python code educator. Explain why a specific line of
code exists, given the current execution context. Current line: {line_content}.
Current variable state: {locals}. Explain in 2-3 sentences. Be precise. Do not
explain what the code does generally — explain WHY this specific line is necessary
given the current state. Include a code snippet if helpful."""

async def stream_explain(
    code: str,
    line_number: int,
    line_content: str,
    locals_dict: dict,
) -> AsyncGenerator[str, None]:
    # 1. Check cache
    key = make_cache_key(code, line_number, line_content)
    cached = get_cached(key)
    if cached:
        yield cached
        return

    # 2. Build prompt
    prompt = SYSTEM_PROMPT.format(
        line_content=line_content,
        locals=json.dumps(locals_dict, indent=2),
    )

    # 3. Stream from Ollama Cloud
    async with httpx.AsyncClient(timeout=8.0) as client:
        async with client.stream(
            "POST",
            OLLAMA_CLOUD_URL + "/chat",
            json={
                "model": "llama3.2",
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
            },
        ) as response:
            full_response = []
            async for line in response.aiter_lines():
                if line.strip():
                    data = json.loads(line)
                    token = data.get("message", {}).get("content", "")
                    if token:
                        full_response.append(token)
                        yield token  # stream to SSE

    # 4. Store in cache (after streaming completes)
    full_text = "".join(full_response)
    store_cached(key, full_text, "ollama", "llama3.2")
```

**SSE client implementation (frontend `useStreamingExplanation.ts`):**

```typescript
// Features over original architecture:
// - Automatic reconnection with exponential backoff (max 3 retries)
// - Connection state tracking (idle/connecting/streaming/done/error)
// - Proper cleanup on unmount (no memory leaks)
// - Blinking cursor while streaming
// - Retry button on error state

export function useStreamingExplanation() {
  const [text, setText] = useState("");
  const [state, setState] = useState<"idle"|"connecting"|"streaming"|"done"|"error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [provider, setProvider] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const retryCountRef = useRef(0);
  const retryTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const MAX_RETRIES = 3;
  const BASE_RETRY_DELAY_MS = 1000;

  const start = (params: { code: string; line_number: number;
      line_content: string; locals: Record<string, { type: string; value: string }>;
  }) => {
    eventSourceRef.current?.close();
    if (retryTimeoutRef.current) clearTimeout(retryTimeoutRef.current);
    retryCountRef.current = 0;
    setText(""); setError(null); setProvider(null); setState("connecting");

    const query = new URLSearchParams({
      code: params.code, line_number: String(params.line_number),
      line_content: params.line_content, locals_json: JSON.stringify(params.locals),
    });
    const es = new EventSource(`/api/llm/explain/stream?${query}`);

    es.onopen = () => setState("streaming");
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.token) setText((prev) => prev + data.token);
        if (data.provider) setProvider(data.provider);
      } catch { setText((prev) => prev + e.data); }
    };
    es.addEventListener("done", () => { setState("done"); es.close(); });
    es.addEventListener("error", (e: MessageEvent) => {
      const errorData = e.data ? JSON.parse(e.data) : {};
      const msg = errorData.message || "Failed to load explanation";
      setError(msg); setState("error");
      if (retryCountRef.current < MAX_RETRIES) {
        retryCountRef.current++;
        setState("connecting");
        retryTimeoutRef.current = setTimeout(() => {
          if (params) start(params);  // retry
        }, BASE_RETRY_DELAY_MS * Math.pow(2, retryCountRef.current - 1));
      } else { es.close(); }
    });
    eventSourceRef.current = es;
  };

  const stop = () => { eventSourceRef.current?.close(); setState("idle"); setText(""); };
  const retry = () => { retryCountRef.current = 0; /* re-trigger start from current params */ };

  useEffect(() => () => { eventSourceRef.current?.close();
    if (retryTimeoutRef.current) clearTimeout(retryTimeoutRef.current); }, []);

  return { text, state, error, provider, start, stop, retry };
}
```

**Frontend Error Boundaries:**

Each major UI panel is wrapped in its own React `ErrorBoundary`. If the Monaco editor crashes, only the editor panel shows the error — the variable panel and explanation panel continue working. Similarly for the variable panel and explanation panel. This prevents a single crash from taking down the entire page.

```typescript
// Each panel has its own boundary:
<ErrorBoundary fallback={<EditorErrorFallback />}>
  <CodeEditor />
</ErrorBoundary>
<ErrorBoundary fallback={<VariablePanelErrorFallback />}>
  <VariablePanel />
</ErrorBoundary>
<ErrorBoundary fallback={<ExplanationPanelErrorFallback />}>
  <ExplanationPanel />
</ErrorBoundary>
```

**i18n Support:**

The frontend uses `next-intl` for internationalization. English (`en`) is the default; Vietnamese (`vi`) is the first additional locale. The locale is detected from the `Accept-Language` header and can be overridden via a `NEXT_LOCALE` cookie.

```
Translation keys: 31 (covering: landing, tracer, reviews, auth, errors)
i18n files: i18n/locales/en.json, i18n/locales/vi.json
```

---

## 4. API Contract

All endpoints are prefixed with `/api`. Base URL in production: `https://codescope-api.up.railway.app`.

### `POST /api/traces/run` — Execute a trace

**Auth:** Optional (anonymous allowed, Pro unlocks save)

**Concurrency:** Requests are gated by an `asyncio.Semaphore(25)` per FastAPI worker. At 2 uvicorn workers, this allows 50 total concurrent trace executions. Requests that arrive when the semaphore is full queue in the async event loop — no threads are consumed while waiting. Returns HTTP 429 if the queue exceeds a reasonable wait threshold.

**Request:**

```json
{
  "code": "def add(a, b):\\n    return a + b\\nadd(2, 3)"
}
```

**Response (200):**

```json
{
  "trace_id": "550e8400-e29b-41d4-a716-446655440000",
  "steps": [
    {
      "step_number": 0,
      "line_number": 1,
      "bytecode_offset": 0,
      "opcode": "LOAD_CONST",
      "variables": {
        "a": {"type": "int", "value": "2", "changed": false},
        "b": {"type": "int", "value": "3", "changed": false}
      },
      "call_depth": 0,
      "branches_taken": {},
      "duration_ms": 0.31
    },
    {
      "step_number": 1,
      "line_number": 2,
      "bytecode_offset": 4,
      "opcode": "LOAD_NAME",
      "variables": {
        "a": {"type": "int", "value": "2", "changed": false},
        "b": {"type": "int", "value": "3", "changed": false},
        "result": {"type": "int", "value": "5", "changed": true}
      },
      "call_depth": 0,
      "branches_taken": {},
      "duration_ms": 0.18
    }
  ],
  "total_steps": 4,
  "duration_ms": 12.4
}
```

> **Change from v1.1:** `branches_taken` is now populated. The example above shows empty `{}` for simple arithmetic, but for conditional code it would contain e.g. `{"type": "if", "taken": true, "line": 5}` when an if branch fires.

**Errors:**

- `422`: Code contains side effects (validation failure) — `{"error": "SIDE_EFFECT_BLOCKED", "matched": ["\\bimport\\s+os"]}`
- `422`: Code exceeds 5000 characters — `{"error": "CODE_TOO_LONG", "message": "..."}`
- `429`: Concurrency limit reached (all 25 worker slots busy) — `{"error": "SERVER_BUSY", "retry_after_seconds": 5}`
- `500`: Tracer error (syntax error, infinite loop timeout) — `{"error": "TIMEOUT", "message": "..."}` or `{"error": "SYNTAX_ERROR", "message": "...", "line": 5}`

### `POST /api/traces` — Save a trace

**Auth:** Required (Pro for unlimited, free max 50/month)

**Request:**

```json
{
  "code": "def add(a, b):\\n    return a + b",
  "concept_tags": ["COMPLEX_CONTROL_FLOW"],
  "is_public": false
}
```

**Response (201):**

```json
{
  "id": "uuid",
  "share_token": "abc123...",
  "created_at": "2026-04-28T10:00:00Z"
}
```

### `GET /api/traces` — List user's traces

**Auth:** Required

**Response (200):**

```json
{
  "traces": [
    {
      "id": "uuid",
      "code": "...",
      "steps": [...],
      "concept_tags": ["COMPLEX_CONTROL_FLOW"],
      "is_public": false,
      "share_token": "abc123...",
      "created_at": "2026-04-28T10:00:00Z"
    }
  ]
}
```

### `GET /trace/{share_token}` — Shared trace (public, no auth)

**Auth:** None

**Note on URL structure:** `/trace/` (no `/api/` prefix) intentionally differs from the other API endpoints. This route serves public read-only trace replays and is mapped directly in Next.js as `app/trace/[share_token]/page.tsx`. It is NOT a FastAPI route — the frontend proxies it or Next.js serves it from the same Vercel deployment. The FastAPI is only called for authenticated or rate-limited operations.

**Response:** Trace object without user identity. Read-only replay mode. Returns 404 if share_token not found.

### `GET /api/profiles/me` — Get current user profile

**Auth:** Required

**Response (200):**

```json
{
  "id": "uuid",
  "experience_level": "student",
  "ai_tools_usage": "moderate",
  "ollama_endpoint": "https://ollama.com/api",
  "plan": "free"
}
```

### `PATCH /api/profiles/me` — Update profile settings

**Auth:** Required

**Request:**

```json
{
  "ollama_endpoint": "localhost:11434",
  "experience_level": "junior",
  "ai_tools_usage": "heavy"
}
```

**Response (200):** Updated profile object.

**Note:** `ollama_endpoint` defaults to `https://ollama.com/api` for all new users. Setting it to `localhost:11434` enables full local inference — the user's own Ollama instance handles all explanation requests. This field is the only profile setting that affects the AI layer. `plan` and `stripe_customer_id` cannot be updated via this endpoint (managed by Stripe webhooks).

### `GET /api/llm/explain/stream` — Get explanation (streaming)

**Auth:** Pro (unlimited) or anonymous (rate-limited: 20/hour)

**Rate limiting:** `check_rate_limit()` is called at the top of this handler using the client IP as the key. Returns HTTP 429 with `{"error": "RATE_LIMITED", "retry_after_seconds": N}` when exceeded.

**Query params:**

```
GET /api/llm/explain/stream?code=...&line_number=5&line_content=...&locals_json=...
```

**Response:** Server-Sent Events stream. Tokens sent as `message` events. `done` event when complete.

**Rate limit response (HTTP 429):**

```json
{"error": "RATE_LIMITED", "retry_after_seconds": 1423}
```

**All-provider-fail response (HTTP 500):**

```json
{"error": "EXPLANATION_UNAVAILABLE", "message": "Explanation service is temporarily unavailable. Please try again."}
```

### `GET /api/review/due` — Get due review cards

**Auth:** Pro required

**Response (200):**

```json
{
  "cards": [
    {
      "id": "uuid",
      "trace_id": "uuid",
      "trace": {"code": "...", "steps": [...]},
      "concept_tag": "COMPLEX_CONTROL_FLOW",
      "next_review_date": "2026-05-01",
      "interval_days": 6,
      "easiness_factor": 2.6,
      "repetitions": 1
    }
  ],
  "streak": 5
}
```

### `POST /api/review/{card_id}` — Submit review rating

**Auth:** Pro required

**Request:**

```json
{ "rating": "good" }
```

**Response (200):** Updated card with new `next_review_date`.

**Errors:** `404` (not found), `401` (not authenticated), `402` (Pro required).

---

## 5. Project Structure

```
codescope/
├── frontend/                        # Next.js app (Vercel)
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── hooks/
│   ├── types/
│   ├── package.json
│   └── .env.local                  # NEXT_PUBLIC_API_URL
│                                   # NEXT_PUBLIC_SUPABASE_URL
│                                   # NEXT_PUBLIC_SUPABASE_ANON_KEY
├── backend/                         # FastAPI app (Railway)
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── routers/
│   │   └── services/
│   ├── tracer/                     # pip-installable library
│   │   ├── tracer.py
│   │   ├── validator.py
│   │   └── models.py
│   ├── migrations/
│   ├── tests/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── .env.example                # ANTHROPIC_API_KEY, SUPABASE_URL,
│                                   # SUPABASE_SERVICE_KEY, OLLAMA_CLOUD_URL
└── docker-compose.yml               # Local dev: Supabase + FastAPI
```

---

## 6. Deployment Architecture

### Local Development

```yaml
# docker-compose.yml (complete local dev environment)

version: "3.9"

services:
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
      NEXT_PUBLIC_SUPABASE_URL: http://localhost:54321
      NEXT_PUBLIC_SUPABASE_ANON_KEY: ${SUPABASE_ANON_KEY:-eyJ...}
    volumes:
      - ./frontend:/app
      - /app/node_modules
      - /app/.next
    depends_on:
      backend:
        condition: service_healthy
    networks:
      - codescope

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      SUPABASE_URL: http://localhost:54321
      SUPABASE_SERVICE_KEY: ${SUPABASE_SERVICE_KEY:-eyJ...}
      REDIS_URL: redis://redis:6379          # ← REQUIRED for distributed rate limiting
      LOG_LEVEL: DEBUG
    volumes:
      - ./backend:/app
      - /app/__pycache__
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s
    networks:
      - codescope

  redis:                          # ← REQUIRED for distributed rate limiting
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5
    networks:
      - codescope

  supabase-db:
    image: supabase/postgres:15.1.0.147
    ports:
      - "54321:5432"
    environment:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: postgres
    volumes:
      - supabase-data:/var/lib/postgresql/data
      - ./backend/migrations:/docker-entrypoint-initdb.d:ro
    networks:
      - codescope

  supabase-studio:               # DB management UI at http://localhost:3001
    image: supabase/studio:20241028-91dd0f8
    ports:
      - "3001:3000"
    environment:
      SUPABASE_URL: http://localhost:54321
      STUDIO_PG_META_URL: http://supabase-db:5432
      SUPABASE_ANON_KEY: ${SUPABASE_ANON_KEY:-eyJ...}
    depends_on:
      - supabase-db
    networks:
      - codescope

networks:
  codescope:
    driver: bridge

volumes:
  redis_data:                     # ← Persistent Redis data
  supabase-data:
```

Run locally with:

```bash
docker compose up --build
# Frontend:  http://localhost:3000
# API:       http://localhost:8000/docs (Swagger UI)
# Supabase:  http://localhost:54321 (Supabase Studio)
```

**On Windows development:** If `resource.setrlimit()` fails on Windows (Unix-only), the tracer subprocess still runs with the 5-second `communicate(timeout=5)` guard. Add a try/except around the `resource.setrlimit()` calls in `tracer_runner.py` so the dev experience works on Windows.

### Production Deployment

**Vercel (Frontend):**

```
Repository: github.com/username/codescope
Framework: Next.js 16
Build command: npm install && npm run build
Environment variables:
  NEXT_PUBLIC_API_URL=https://codescope-api.up.railway.app
  NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
  NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
```

**Railway (Backend):**

```
Repository: github.com/username/codescope
Root directory: backend/
Start command: uvicorn app.main:app --host 0.0.0.0 --port 8000
Environment variables:
  ANTHROPIC_API_KEY=sk-ant-...          # fallback only
  SUPABASE_URL=https://xxxx.supabase.co
  SUPABASE_SERVICE_KEY=eyJ...
  OLLAMA_CLOUD_URL=https://ollama.com/api
  CORS_ORIGIN=https://codescope.vercel.app
```

**Railway CORS configuration (in `main.py`):**

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://codescope.vercel.app",   # Production Vercel
        "http://localhost:3000",           # Local dev
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Railway environment variables for logging (optional):**

```
SENTRY_DSN=https://...@sentry.io/...    # Sentry error tracking
LOG_LEVEL=INFO                           # structlog log level
```

---

## 7. SPIKEs

Two technical uncertainties identified in the PRD. The architecture is designed to accommodate either outcome of each spike.

### SPIKE 1 (Week 1): Tracer overhead profiling

**Question:** Does `sys.settrace()` add more than 200ms overhead on 200-line functions?

**Test plan:** Profile `run_trace()` on synthetic 200-line Python functions. Measure total execution time vs. baseline (no tracer). Run 10 iterations, report mean and P95.

**Architecture response if overhead > 200ms:**

- Move the tracer call to a **thread pool** using FastAPI's `run_in_executor()`:
  ```python
  from concurrent.futures import ThreadPoolExecutor
  executor = ThreadPoolExecutor(max_workers=10)

  @app.post("/api/traces/run")
  async def run_trace_endpoint(req: TraceRequest):
      loop = asyncio.get_event_loop()
      result = await loop.run_in_executor(executor, tracer_runner.run_trace, req.code)
      return result
  ```
- This keeps the subprocess architecture but prevents one slow trace from blocking the async event loop and other concurrent requests.

**Architecture response if overhead ≤ 200ms:**

- No architectural change needed. The current async design handles it.

### SPIKE 2 (Month 2): Ollama model selection

**Question:** Which Ollama model provides the best explanation quality for code education?

**Test plan:** Run 50 explanation responses through a rubric (clarity, accuracy, educational value, each rated 1–5). Test against: `llama3.2`, `phi3`, `mistral`, `codellama`. Select based on highest mean rubric score.

**Architecture response:**

- Model name is stored in `backend/app/config.py` and set via `OLLAMA_MODEL` environment variable on Railway:
  ```python
  DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
  ```
- Swapping models requires only a Railway environment variable change — no code deployment needed.
- The `explanations.model_name` column records which model produced each explanation, enabling post-hoc quality analysis by model.
- Both Ollama Cloud and local Ollama use the same `DEFAULT_MODEL` setting.

---

## 8. Key Technical Decisions


| Decision            | Choice                                                    | Rationale                                                                             |
| ------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| Tracer architecture | Subprocess on FastAPI server                              | Server-side isolation; no browser sandbox concerns; works on Railway Linux containers |
| Ollama provider     | Ollama Cloud (ollama.com)                                 | Free, zero-setup; no GPU required; Ollama.com handles hosting                         |
| Claude role         | Fallback only                                             | $0 cost at MVP; used only when Ollama Cloud is unavailable                            |
| LLM response        | Streaming SSE                                             | Transforms UX quality; one extra day to implement                                     |
| Explanation cache   | Content-addressable SHA-256                               | Repeat clicks on same line are instant; zero API cost                                 |
| Rate limiting       | Token bucket, 20 explanations/hour (anonymous)            | Protects free tier from abuse; enforced in `llm_router.py`                            |
| Shared traces       | `/trace/{share_token}` public page + `share_token` column | Anyone with the link can view; no login friction; served as Next.js page, not FastAPI |
| DB ORM              | Supabase JS client (frontend) + raw SQL (backend)         | Simplicity; no SQLAlchemy overhead at MVP scale                                       |
| Auth                | Supabase Auth (email/password)                            | Free, managed, no custom auth code                                                    |
| Deployment          | Vercel (frontend) + Railway (backend)                     | Both have generous free tiers; matches PRD plan                                       |
| Docker              | Docker Compose for local dev only                         | Production is Vercel + Railway; no Kubernetes                                         |
| Logging             | structlog + Railway log drain                             | Structured JSON logs; correlation IDs; no external SaaS dependency                    |
| Error tracking      | Sentry (Python SDK)                                       | Automatic exception grouping; source maps; alert on error rate spike                  |


---

## 9. Out of Scope for V1


| Feature                                                            | Why Out of Scope                                           |
| ------------------------------------------------------------------ | ---------------------------------------------------------- |
| Formal research study (telemetry, study mode, evaluation pipeline) | Supervisor confirmed no formal study requirement           |
| Pyodide / browser-side execution                                   | Replaced by backend tracer per PRD v1.1                    |
| Multi-language support (JS, Java)                                  | Only Python in V1; tracer is CPython-specific              |
| Mobile responsive UI                                               | Desktop-only for V1; Monaco editor requires desktop        |
| B2B / team features (SSO, admin dashboard)                         | Post-project SaaS feature                                  |
| Dark/light theme toggle                                            | Dark-only standard for developer tools                     |
| Export to Anki                                                     | Nice-to-have; no thesis requirement                        |
| GitHub integration                                                 | Requires OAuth + webhook; deferred                         |
| Side-effect code execution (file I/O, network)                     | Security risk in shared server environment; blocked in V1  |
| Docker-based sandbox (gVisor)                                      | Only needed if resource limits are insufficient on Railway |


---

## 10. Implementation Order


| Week        | Milestone                | Deliverable                                                                |
| ----------- | ------------------------ | -------------------------------------------------------------------------- |
| **Week 1**  | Tracer MVP               | `tracer/tracer.py` works locally; `POST /api/traces/run` returns step JSON |
| **Week 1**  | Side-effect validation   | Side-effect patterns blocked before execution; error returned clearly      |
| **Week 2**  | Frontend trace view      | Monaco editor + line highlighting + variable panel                         |
| **Week 2**  | Animation controls       | Play/Pause/Step/Back with keyboard shortcuts; `useTrace.ts` loop           |
| **Week 3**  | LLM explanations         | Streaming SSE from Ollama Cloud; Claude fallback; rate limiter             |
| **Week 3**  | Explanation cache        | SHA-256 cache in Supabase; repeat explanations return instantly            |
| **Week 4**  | Save traces              | Auth + Supabase save; shared trace links                                   |
| **Week 5**  | Rate limiting            | Token bucket on anonymous explanations; 429 responses with retry-after     |
| **Week 6**  | Docker Compose + logging | Full local dev environment; structlog + correlation IDs                    |
| **Month 2** | Ollama model benchmark   | Evaluate phi3, mistral, llama3.2; pick best; set via env var               |
| **Month 2** | Railway staging deploy   | Railway staging environment; integration testing                           |
| **Month 2** | Error tracking setup     | Sentry SDK wired to FastAPI; alerts on error rate spike                    |
| **Month 3** | Spaced repetition        | SM-2 algorithm in `lib/sm2.ts`; review queue; streak tracking              |
| **Month 3** | Pro tier                 | Stripe integration; freemium gate enforcement                              |
| **Month 4** | Production polish        | Lighthouse audit; performance profiling; error monitoring review           |


SPIKEs are scheduled for Week 1 (tracer profiling) and Month 2 (Ollama benchmarking).

---

## Appendix: PRD Requirement Traceability

Each architecture component maps to a PRD requirement:


| PRD Requirement                    | Architecture Component                                             |
| ---------------------------------- | ------------------------------------------------------------------ |
| REQ-CORE-02: Step-by-step trace    | `tracer/tracer.py` + `POST /api/traces/run`                        |
| REQ-CORE-01: Code validation       | `tracer/validator.py` + pre-execution check in `tracer_runner.py`  |
| REQ-CORE-03: Variable state panel  | `TraceStep.variables` + `VariablePanel.tsx`                        |
| REQ-CORE-04: Animation controls    | `useTrace.ts` + `AnimationControls.tsx`                            |
| REQ-CORE-05: Line highlighting     | `LineHighlight.tsx` + `?step=N` URL state                          |
| REQ-AI-01: "Why is this here?"     | `GET /api/llm/explain/stream` + `ExplanationPanel.tsx`             |
| REQ-AI-01: Streaming               | `EventSource` in frontend + `EventSourceResponse` in FastAPI       |
| REQ-AI-01: Cache                   | `cache_key` in `explanations` table + `llm_router.py` cache lookup |
| REQ-TRACK-01: Save to review queue | `POST /api/traces` + `review_cards` table                          |
| REQ-TRACK-02: SM-2 scheduler       | `lib/sm2.ts` (frontend) + `POST /api/review/{card_id}`             |
| REQ-AUTH-01: Sign up / sign in     | Supabase Auth (email/password)                                     |
| REQ-AUTH-02: Share trace link      | `share_token` column + `GET /trace/{share_token}`                  |
| REQ-TRACK-01: Freemium gate        | `plan` field in `profiles` + `POST /api/traces` checks plan        |


