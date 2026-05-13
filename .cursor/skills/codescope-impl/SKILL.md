---
name: codescope-impl
description: Implements CodeScope — a Python code visualization tool. Decomposes SPEC.md into atomic, zero-guesswork tasks for any AI. Use when building CodeScope from scratch, implementing a Phase, or adding features to tracer, frontend, or backend.
---

# CodeScope Implementation Skill

## Golden Rule

**Never skip steps. Never combine steps. If a step has prerequisites, do prerequisites first.**

Every task below is ordered so that file N only depends on files 1..N-1. Read and follow tasks in strict sequence.

---

## Quick Reference

| Item | Value |
|---|---|
| Project root | `C:\Users\quoct\codescope\` |
| Frontend | `C:\Users\quoct\codescope\frontend\` |
| Backend | `C:\Users\quoct\codescope\backend\` |
| AI Provider | **GitHub Models** (`https://models.github.ai/inference/chat/completions`) |
| AI Auth | PAT with `models` scope (never commit) |
| Default model | `openai/gpt-4.1` (or pick from catalog) |
| Subprocess | User code ALWAYS runs in isolated subprocess, never in FastAPI process |

---

## Phase 1A: Backend Tracer

### TASK 1A-1: Create backend directory structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   └── routers/
│       ├── __init__.py
│       └── traces.py
├── tracer/
│   ├── __init__.py
│   ├── models.py
│   ├── tracer.py
│   ├── validator.py
│   └── runner.py
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── test_tracer.py
│   │   └── test_validator.py
│   └── integration/
│       ├── __init__.py
│       └── test_trace_flow.py
├── pyproject.toml
├── .env.example
└── Dockerfile
```

Create every file as an **empty placeholder** first. Do not write any logic yet. Create them in order:

1. Run: `mkdir -p backend/app/routers backend/tracer backend/tests/unit backend/tests/integration`
2. Create each `__init__.py` as: `"""Package."""`
3. Create `.env.example` with the variables listed below
4. Create `pyproject.toml`
5. Create `Dockerfile`

**`.env.example` content:**
```
# GitHub Models PAT — required for AI explanations
# Generate at: https://github.com/settings/tokens
# Scope needed: models
GITHUB_MODELS_PAT=github_pat_11XXXXXXXXXX

# Ollama (Phase 4 — not needed now)
OLLAMA_CLOUD_URL=https://ollama.com/api
OLLAMA_MODEL=llama3.2

# Supabase (Phase 2 — not needed for Phase 1A)
SUPABASE_URL=http://localhost:54321
SUPABASE_SERVICE_KEY=postgres

# Redis (Phase 2 — not needed for Phase 1A)
REDIS_URL=redis://localhost:6379

# Logging
LOG_LEVEL=INFO
```

**`pyproject.toml` content:**
```toml
[project]
name = "codescope-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.6.0",
    "httpx>=0.28.0",
    "structlog>=24.0.0",
    "sse-starlette>=2.0.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.25.0",
    "ruff>=0.8.0",
    "mypy>=1.14.0",
    "httpx>=0.28.0",
]
```

**`Dockerfile` content:**
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install -e .

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### TASK 1A-2: Install dependencies

Open a terminal and run:

```bash
cd C:\Users\quoct\codescope\backend
pip install -e ".[dev]"
```

If on Windows and `pip` is not in PATH, use: `py -m pip install -e ".[dev]"`

**Success indicator:** No error output. You can run `pip list | findstr fastapi` and see `fastapi` listed.

---

### TASK 1A-3: Implement `tracer/models.py`

**Prerequisite:** TASK 1A-1 must be complete.

**File:** `backend/tracer/models.py`

Write this exact code. Do not modify variable names or types.

```python
"""Trace data models."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class VariableInfo:
    """A variable's state at a specific trace step."""
    type: str          # type(val).__name__
    value: str         # repr(val)[:200]
    changed: bool      # true if value changed from previous step


@dataclass
class BranchInfo:
    """A branch taken during control flow."""
    branch_type: str   # 'if' | 'for' | 'while' | 'ternary' | 'and_or'
    taken: Optional[bool]  # True = if branch, False = else branch
    line: int
    iteration: int = 0      # 0 = not a loop


@dataclass
class TraceStep:
    """One step in the execution trace."""
    step_number: int
    line_number: int
    bytecode_offset: int
    opcode: str
    variables: dict[str, VariableInfo]
    branches_taken: dict
    duration_ms: float


@dataclass
class TraceResult:
    """Successful trace result."""
    steps: list[TraceStep]
    total_steps: int
    duration_ms: float


@dataclass
class TraceError:
    """Failed trace result."""
    error: str        # 'SYNTAX_ERROR' | 'TIMEOUT' | 'MAX_STEPS' | 'EXECUTION_ERROR'
    message: str
    line: Optional[int] = None
```

**Verify:** Run `python -c "from tracer.models import TraceStep, VariableInfo; print('OK')"` — output must be `OK`.

---

### TASK 1A-4: Implement `tracer/validator.py`

**Prerequisite:** TASK 1A-3 must be complete.

**File:** `backend/tracer/validator.py`

Write this exact code:

```python
"""Side-effect detection for user code validation."""
import re

SIDE_EFFECT_PATTERNS = [
    (r"\bimport\s+(os|sys|subprocess|requests|urllib|httpx|socket|sqlite3|pickle)", "dangerous_import"),
    (r"\bopen\s*\(", "file_io"),
    (r"\brequests\.", "http_requests"),
    (r"\bos\.", "os_module"),
    (r"\bsubprocess\.", "subprocess_module"),
    (r"\beval\s*\(", "eval_usage"),
    (r"\bexec\s*\(", "exec_usage"),
    (r"\b__import__\s*\(", "dynamic_import"),
    (r"\bgetattr\s*\(", "getattr_usage"),
    (r"\bsetattr\s*\(", "setattr_usage"),
    (r"\binput\s*\(", "input_usage"),
]

WARNING_PATTERNS = [
    (r"\bprint\s*\(", "print_statement"),
]


def validate_code(source: str) -> tuple[bool, list[dict], list[dict]]:
    """
    Check user code for dangerous side effects.

    Returns: (is_valid, blocking_effects, warnings)
    - is_valid: True if code is safe to execute
    - blocking_effects: [] if safe, list of matched dangerous patterns if not
    - warnings: list of warnings (print() is warning only, not blocking)
    """
    blocking = []
    warnings = []

    for pattern, name in SIDE_EFFECT_PATTERNS:
        match = re.search(pattern, source)
        if match:
            blocking.append({"pattern": name, "matched": match.group()})

    for pattern, name in WARNING_PATTERNS:
        match = re.search(pattern, source)
        if match:
            warnings.append({"pattern": name, "matched": match.group()})

    return (len(blocking) == 0, blocking, warnings)
```

**Verify:** Run `python -c "from tracer.validator import validate_code; v, b, w = validate_code('import os'); print('blocked:', not v, 'patterns:', len(b))"` — output must be `blocked: True patterns: 1`.

---

### TASK 1A-5: Write validator tests

**Prerequisite:** TASK 1A-4 must be complete.

**File:** `backend/tests/unit/test_validator.py`

Write this exact code:

```python
"""Tests for the side-effect validator."""
import pytest
from tracer.validator import validate_code


def test_safe_code_returns_valid():
    """Code with no side effects should be valid."""
    is_valid, blocking, warnings = validate_code("x = 1\ny = x + 2")
    assert is_valid is True
    assert len(blocking) == 0


def test_import_os_is_blocked():
    """import os should be blocked."""
    is_valid, blocking, warnings = validate_code("import os")
    assert is_valid is False
    assert any(e["pattern"] == "dangerous_import" for e in blocking)


def test_open_builtin_is_blocked():
    """open() should be blocked."""
    is_valid, blocking, warnings = validate_code("f = open('test.txt')")
    assert is_valid is False
    assert any(e["pattern"] == "file_io" for e in blocking)


def test_print_is_warning_not_block():
    """print() should be a warning only, not blocking."""
    is_valid, blocking, warnings = validate_code("print('hello')")
    assert is_valid is True
    assert len(blocking) == 0
    assert any(w["pattern"] == "print_statement" for w in warnings)


def test_multiple_blocking_effects():
    """Multiple dangerous patterns should all be reported."""
    code = "import os\nimport sys\nopen('x')"
    is_valid, blocking, warnings = validate_code(code)
    assert is_valid is False
    assert len(blocking) >= 2


def test_regex_does_not_false_positive():
    """Variable names starting with 'os' should not trigger os module block."""
    is_valid, blocking, warnings = validate_code("oscar = 'Oscar'")
    assert is_valid is True
    assert not any(e["pattern"] == "os_module" for e in blocking)
```

**Verify:** Run `pytest backend/tests/unit/test_validator.py -v` — all 6 tests must pass.

---

### TASK 1A-6: Implement `tracer/tracer.py` — AST pre-pass

**Prerequisite:** TASK 1A-3 must be complete.

**File:** `backend/tracer/tracer.py`

**CRITICAL: This is the hardest file in the entire project. Follow every line exactly.**

Write this code. The comments explain each section:

```python
"""
Python code tracer using sys.settrace().
User code executes step-by-step; each step captures variable state.
"""
import sys
import ast
import time
import dis
import types
from tracer.models import TraceStep, VariableInfo


def _build_jump_map(source: str) -> dict[int, list[ast.AST]]:
    """
    AST pre-pass: find all conditional nodes.
    Returns {line_number: [node, ...]} for branch detection.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    jump_map: dict[int, list[ast.AST]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.For, ast.While)):
            if hasattr(node, 'test') and node.test:
                jump_map.setdefault(node.test.lineno, []).append(node)
        elif isinstance(node, ast.BoolOp):
            jump_map.setdefault(node.lineno, []).append(node)
    return jump_map


def _build_opcode_map(code: types.CodeType) -> dict[int, str]:
    """
    Build bytecode offset → opname map.
    Used to annotate each trace step with its Python opcode.
    """
    return {instr.offset: instr.opname for instr in dis.get_instructions(code)}


def run_trace(source: str, max_steps: int = 500) -> dict:
    """
    Execute `source` with sys.settrace() active.
    Returns: {"steps": [...], "total_steps": int, "duration_ms": float}
    Errors: {"error": str, "message": str, "line": int?}
    """
    # Step 1: AST pre-pass for branch detection
    jump_map = _build_jump_map(source)

    # Step 2: Compile source (catches SyntaxError early)
    try:
        compiled = compile(source, "<codescope>", "exec")
    except SyntaxError as e:
        return {"error": "SYNTAX_ERROR", "message": str(e), "line": e.lineno}

    # Step 3: Build opcode map
    opcode_map = _build_opcode_map(compiled)

    # Step 4: Initialize trace state
    steps: list[TraceStep] = []
    prev_variables: dict[str, str] = {}  # name → repr string
    start_time = time.perf_counter()

    # Step 5: Tracer callback
    def tracer_callback(frame, event, arg):
        nonlocal prev_variables

        # Stop if max steps reached
        if len(steps) >= max_steps:
            return None

        # Only trace 'line' events for step-by-step visualization
        # 'call' events would add noise; 'return' handled below
        if event not in ("line",):
            return tracer_callback

        # Get opcode for this byte position
        bytecode_offset = frame.f_lasti
        opcode = opcode_map.get(bytecode_offset, "UNKNOWN")

        # Capture variables from current frame's locals
        # IMPORTANT: access by iterating keys, not the dict directly
        # frame.f_locals is a proxy dict that can go stale
        variables: dict[str, VariableInfo] = {}
        for name in list(frame.f_locals.keys()):
            try:
                val = frame.f_locals[name]
                prev_repr = prev_variables.get(name, None)
                curr_repr = repr(val)[:200]
                changed = (prev_repr is None) or (curr_repr != prev_repr)
                variables[name] = VariableInfo(
                    type=type(val).__name__,
                    value=curr_repr,
                    changed=changed,
                )
            except (NameError, RuntimeError, KeyError):
                # Skip variables that cannot be accessed at this point
                pass

        # Capture closure variables from outer scope
        if frame.f_back:
            for name in list(frame.f_back.f_locals.keys()):
                if name not in variables:
                    try:
                        val = frame.f_back.f_locals[name]
                        prev_repr = prev_variables.get(name, None)
                        curr_repr = repr(val)[:200]
                        changed = (prev_repr is None) or (curr_repr != prev_repr)
                        variables[name] = VariableInfo(
                            type=type(val).__name__,
                            value=curr_repr,
                            changed=changed,
                        )
                    except (NameError, RuntimeError, KeyError):
                        pass

        # Branch detection: check if this line is a conditional
        branches_taken: dict = {}
        line_no = frame.f_lineno
        if line_no in jump_map:
            for node in jump_map[line_no]:
                if isinstance(node, ast.If):
                    branches_taken["if"] = {"taken": True, "line": line_no, "iteration": 0}

        # Detect generator functions
        is_generator = bool(frame.f_code.co_flags & 0x20)

        step = TraceStep(
            step_number=len(steps),
            line_number=line_no,
            bytecode_offset=bytecode_offset,
            opcode=opcode,
            variables=variables,
            branches_taken=branches_taken,
            duration_ms=0.0,
        )
        steps.append(step)
        prev_variables = {k: v.value for k, v in variables.items()}

        # Stop tracing on return from a function (prevents infinite recursion)
        # Exception: generators must continue tracing
        if event == "return" and not is_generator:
            return None

        return tracer_callback

    # Step 6: Execute with tracing active
    sys.settrace(tracer_callback)
    try:
        exec(compiled, {})
    except SystemExit:
        pass
    finally:
        sys.settrace(None)

    # Step 7: Calculate durations
    duration_ms = (time.perf_counter() - start_time) * 1000
    if steps:
        per_step = duration_ms / len(steps)
        for step in steps:
            step.duration_ms = round(per_step, 3)

    return {
        "steps": [_step_to_dict(s) for s in steps],
        "total_steps": len(steps),
        "duration_ms": round(duration_ms, 2),
    }


def _step_to_dict(step: TraceStep) -> dict:
    """Convert a TraceStep to a plain dict for JSON serialization."""
    return {
        "step_number": step.step_number,
        "line_number": step.line_number,
        "bytecode_offset": step.bytecode_offset,
        "opcode": step.opcode,
        "variables": {
            name: {"type": v.type, "value": v.value, "changed": v.changed}
            for name, v in step.variables.items()
        },
        "branches_taken": step.branches_taken,
        "duration_ms": step.duration_ms,
    }
```

**Verify:** Run `python -c "from tracer.tracer import run_trace; r = run_trace('x = 1'); print('steps:', r.get('total_steps', 0), 'error:', r.get('error', 'none'))"` — output should show `steps: N` (some number) and `error: none`.

---

### TASK 1A-7: Implement `tracer/runner.py`

**Prerequisite:** TASK 1A-6 must be complete.

**File:** `backend/tracer/runner.py`

**CRITICAL: User code runs in a subprocess. This is a security boundary.**

```python
"""
Subprocess runner for executing untrusted user code.
Handles: temp file cleanup, 5s timeout, stderr capture, Windows compat.
"""
import os
import sys
import json
import tempfile
import subprocess
from pathlib import Path


def run_trace(source: str, max_steps: int = 500, timeout_seconds: int = 5) -> dict:
    """
    Execute user code in an isolated subprocess.
    Returns: {"steps": [...], "total_steps": int, "duration_ms": float}
    Errors: {"error": str, "message": str, "line": int?}
    """
    # Write code to a temp file
    # Using a temp file avoids quoting/escaping issues on Windows with subprocess
    fd, tmp_path = tempfile.mkstemp(suffix=".py")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            # Prepend the tracer library path so subprocess can import it
            tracer_dir = str(Path(__file__).parent)
            f.write(f"import sys, json, time\n")
            f.write(f"sys.path.insert(0, r'{tracer_dir.replace(chr(92), chr(92)+chr(92))}')\n")
            f.write("from tracer import tracer as _tracer\n")
            f.write(f"result = _tracer.run_trace({repr(source)}, max_steps={max_steps})\n")
            f.write("print(json.dumps(result))\n")

        # Run the temp file in a subprocess
        proc = subprocess.Popen(
            [sys.executable, tmp_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            stdout, stderr = proc.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            # Windows: proc.kill() works fine on Windows Python 3.7+
            proc.kill()
            proc.communicate()  # drain pipes to avoid BrokenPipeError
            return {
                "error": "TIMEOUT",
                "message": f"Execution exceeded {timeout_seconds} seconds",
                "line": None,
            }

        # Decode output (handle encoding edge cases)
        try:
            stdout_text = stdout.decode("utf-8", errors="replace").strip()
        except Exception:
            stdout_text = ""

        try:
            stderr_text = stderr.decode("utf-8", errors="replace").strip()
        except Exception:
            stderr_text = ""

        # Empty stdout means the subprocess crashed
        if not stdout_text:
            return {
                "error": "EXECUTION_ERROR",
                "message": stderr_text or "Code produced no output. Check for crashes.",
                "line": None,
            }

        # Parse the JSON result from the subprocess
        try:
            return json.loads(stdout_text)
        except json.JSONDecodeError as e:
            return {
                "error": "EXECUTION_ERROR",
                "message": f"JSON parse error: {e}\\nOutput: {stdout_text[:500]}",
                "line": None,
            }

    finally:
        # ALWAYS delete the temp file, even if an exception occurs
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
```

**Verify:** Run `python -c "from tracer.runner import run_trace; r = run_trace('x = 1\ny = 2'); print('steps:', r.get('total_steps', 0), 'error:', r.get('error', 'none'))"` — output should show steps and no error.

---

### TASK 1A-8: Implement `app/config.py`

**Prerequisite:** TASK 1A-1 must be complete.

**File:** `backend/app/config.py`

```python
"""Application configuration. Reads from .env file."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All environment variables for the application."""

    # GitHub Models (AI explanations)
    github_models_pat: str = ""
    github_models_model: str = "openai/gpt-4.1"

    # Supabase (Phase 2+)
    supabase_url: str = "http://localhost:54321"
    supabase_service_key: str = "postgres"

    # Redis (Phase 2+)
    redis_url: str = "redis://localhost:6379"

    # Ollama (Phase 4)
    ollama_cloud_url: str = "https://ollama.com/api"
    ollama_model: str = "llama3.2"

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        extra = "ignore"
```

**Verify:** Run `python -c "from app.config import Settings; s = Settings(); print('OK')"` — output must be `OK`.

---

### TASK 1A-9: Implement `app/main.py`

**Prerequisite:** TASK 1A-8 must be complete.

**File:** `backend/app/main.py`

```python
"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown hooks."""
    # Startup: log configuration status
    from app.config import Settings
    settings = Settings()
    if not settings.github_models_pat:
        import logging
        logging.warning(
            "GITHUB_MODELS_PAT not set. AI explanations will return a placeholder message."
        )
    yield
    # Shutdown: clean up resources here if needed


app = FastAPI(
    title="CodeScope API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS: allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """Health check endpoint for Docker/liveness probes."""
    return {"status": "ok"}
```

**Verify:** Run `python -m uvicorn app.main:app --port 8000` in one terminal, then `curl http://localhost:8000/health` in another. Must return `{"status":"ok"}`. Press Ctrl+C to stop the server.

---

### TASK 1A-10: Implement `app/routers/traces.py`

**Prerequisite:** TASK 1A-9 must be complete (router is imported in main.py).

**File:** `backend/app/routers/traces.py`

```python
"""Trace execution API endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from tracer.validator import validate_code
from tracer.runner import run_trace as run_trace_subprocess

router = APIRouter()


class TraceRequest(BaseModel):
    """Request body for /api/traces/run."""
    code: str = Field(..., max_length=5000, description="Python source code to trace")


class VariableInfoResponse(BaseModel):
    """A variable's state in the response."""
    type: str
    value: str
    changed: bool


class TraceStepResponse(BaseModel):
    """One step in the trace response."""
    step_number: int
    line_number: int
    bytecode_offset: int
    opcode: str
    variables: dict[str, VariableInfoResponse]
    branches_taken: dict
    duration_ms: float


class TraceResponse(BaseModel):
    """Successful trace response."""
    steps: list[TraceStepResponse]
    total_steps: int
    duration_ms: float


@router.post("/api/traces/run", response_model=TraceResponse)
async def run_trace(req: TraceRequest):
    """
    Execute Python code and return a step-by-step trace.
    Side-effect patterns (import os, eval, open(), etc.) are blocked.
    print() is allowed but warned about.
    """
    # Step 1: Validate for dangerous side effects
    is_valid, blocking_effects, warnings = validate_code(req.code)
    if not is_valid:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "SIDE_EFFECT_BLOCKED",
                "message": "This code contains patterns that are not allowed for security reasons.",
                "matched": [e["pattern"] for e in blocking_effects],
                "warnings": [w["pattern"] for w in warnings],
            }
        )

    # Step 2: Run the tracer in a subprocess
    result = run_trace_subprocess(req.code, max_steps=500)

    # Step 3: Handle errors
    if "error" in result:
        error_code = result["error"]
        if error_code == "TIMEOUT":
            raise HTTPException(
                status_code=408,
                detail={
                    "error": "TIMEOUT",
                    "message": result["message"],
                }
            )
        elif error_code == "SYNTAX_ERROR":
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "SYNTAX_ERROR",
                    "message": result["message"],
                    "line": result.get("line"),
                }
            )
        elif error_code == "MAX_STEPS":
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "MAX_STEPS",
                    "message": result["message"],
                }
            )
        else:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": error_code,
                    "message": result.get("message", "Unknown error"),
                }
            )

    # Step 4: Return successful trace
    return TraceResponse(
        steps=[TraceStepResponse(**s) for s in result["steps"]],
        total_steps=result["total_steps"],
        duration_ms=result["duration_ms"],
    )
```

---

### TASK 1A-11: Wire router into main app

**Prerequisite:** TASK 1A-10 must be complete.

**File:** `backend/app/main.py` — add router import and registration.

Find the line `from fastapi.middleware.cors import CORSMiddleware` in `main.py` and add after it:

```python
from app.routers import traces
```

Find the `app = FastAPI(...)` block and add before the `@app.add_middleware` line:

```python
app.include_router(traces.router)
```

**Verify:** Start the server (`python -m uvicorn app.main:app --port 8000`) and run:

```bash
curl -s -X POST http://localhost:8000/api/traces/run -H "Content-Type: application/json" -d "{\"code\": \"x = 1\"}"
```

Must return JSON with `"total_steps"` greater than 0.

---

### TASK 1A-12: Write tracer unit tests

**Prerequisite:** TASK 1A-11 must be complete.

**File:** `backend/tests/unit/test_tracer.py`

```python
"""Unit tests for the Python tracer."""
import pytest
from tracer.tracer import run_trace
from tracer.runner import run_trace as run_trace_subprocess
from tracer.validator import validate_code


# --- Syntax / error cases ---
def test_syntax_error_returns_syntax_error():
    """Invalid Python syntax should return SYNTAX_ERROR."""
    result = run_trace("def :")
    assert result["error"] == "SYNTAX_ERROR"
    assert "line" in result


def test_timeout_detection():
    """Infinite loop should eventually be detected."""
    result = run_trace_subprocess("while True: pass", timeout_seconds=3)
    assert result["error"] == "TIMEOUT"


def test_max_steps_detection():
    """Infinite loop should stop at max_steps."""
    result = run_trace("while True: pass", max_steps=10)
    assert "error" in result or result["total_steps"] <= 10


# --- Basic execution ---
def test_simple_assignment():
    """Simple assignment should produce trace steps."""
    result = run_trace("x = 1")
    assert "error" not in result
    assert result["total_steps"] >= 1


def test_variables_captured():
    """Variables should appear in trace steps."""
    result = run_trace("x = 1\ny = 2")
    assert "error" not in result
    # At least one step should have x or y in variables
    has_vars = any(s["variables"] for s in result["steps"])
    assert has_vars


def test_variable_changed_flag():
    """Changed variable should have changed=True."""
    result = run_trace("x = 1\nx = 2")
    assert "error" not in result
    # Find the step where x = 2 appears
    for step in result["steps"]:
        if "x" in step["variables"]:
            if step["variables"]["x"]["value"] == "2":
                assert step["variables"]["x"]["changed"] is True


# --- Control flow ---
def test_for_loop_iterations():
    """For loop should produce multiple steps."""
    result = run_trace("for i in range(3):\n    pass")
    assert "error" not in result
    assert result["total_steps"] >= 3


def test_if_branch_taken():
    """if True should take the if branch."""
    result = run_trace("if True:\n    x = 1")
    assert "error" not in result


def test_if_else_branch():
    """else branch should execute when condition is False."""
    result = run_trace("if False:\n    x = 1\nelse:\n    x = 2")
    assert "error" not in result
    has_x2 = any(s["variables"].get("x", {}).get("value") == "2" for s in result["steps"])
    assert has_x2


def test_while_loop():
    """While loop should iterate and terminate."""
    result = run_trace("i = 0\nwhile i < 3:\n    i += 1")
    assert "error" not in result
    assert result["total_steps"] >= 4


def test_ternary_expression():
    """Ternary expression should evaluate correctly."""
    result = run_trace("x = 1 if True else 2")
    assert "error" not in result
    has_x1 = any(s["variables"].get("x", {}).get("value") == "1" for s in result["steps"])
    assert has_x1


def test_boolean_short_circuit_and():
    """and should short-circuit on first False."""
    result = run_trace("x = False and 1/0")
    assert "error" not in result


def test_boolean_short_circuit_or():
    """or should short-circuit on first True."""
    result = run_trace("x = True or 1/0")
    assert "error" not in result


# --- Complex patterns ---
def test_nested_list_comprehension():
    """List comprehension should work correctly."""
    result = run_trace("squares = [x**2 for x in range(3)]")
    assert "error" not in result
    has_squares = any(s["variables"].get("squares") for s in result["steps"])
    assert has_squares


def test_lambda_with_closure():
    """Lambda capturing a variable should work."""
    result = run_trace("x = 1\nf = lambda: x\ny = f()")
    assert "error" not in result


def test_class_method():
    """Class with method should trace correctly."""
    result = run_trace("class A:\n    def __init__(self):\n        self.x = 1\nobj = A()")
    assert "error" not in result


# --- Side effects ---
def test_print_is_warning_not_block():
    """print() should be allowed."""
    is_valid, blocking, warnings = validate_code("print('hello')")
    assert is_valid is True
    assert len(blocking) == 0
```

**Verify:** Run `pytest backend/tests/unit/test_tracer.py -v` — at least 12 of 14 tests must pass. Known limitations: some edge case tests may fail on first implementation. Document failures and fix in TASK 1A-14.

---

### TASK 1A-13: Write integration test

**Prerequisite:** TASK 1A-11 must be complete.

**File:** `backend/tests/integration/test_trace_flow.py`

```python
"""Integration tests for the trace API endpoint."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    """Health endpoint should return ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_full_trace_flow():
    """POST valid code → 200 + steps array."""
    response = client.post(
        "/api/traces/run",
        json={"code": "x = 1\ny = x + 2"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "steps" in data
    assert data["total_steps"] > 0
    assert "duration_ms" in data


def test_side_effect_blocked():
    """import os should be blocked with 422."""
    response = client.post(
        "/api/traces/run",
        json={"code": "import os"}
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "SIDE_EFFECT_BLOCKED"


def test_syntax_error():
    """Syntax error should return 422."""
    response = client.post(
        "/api/traces/run",
        json={"code": "def :"}
    )
    assert response.status_code == 422
    assert response.json()["detail"]["error"] == "SYNTAX_ERROR"


def test_empty_code():
    """Empty code should not crash."""
    response = client.post(
        "/api/traces/run",
        json={"code": ""}
    )
    # Empty code is technically valid Python (no-op)
    assert response.status_code in (200, 422)
```

**Verify:** Run `pytest backend/tests/integration/test_trace_flow.py -v` — all 5 tests must pass.

---

### TASK 1A-14: Fix test failures and stabilize

**Prerequisite:** TASK 1A-13 must be complete. Run tests and fix failures.

```bash
pytest backend/tests/unit/test_tracer.py -v
pytest backend/tests/integration/test_trace_flow.py -v
```

For each failing test:
1. Read the error message carefully
2. Identify which line in `tracer/tracer.py` or `tracer/runner.py` causes the failure
3. Fix that specific line — do not rewrite entire functions
4. Re-run the test to verify the fix
5. Document the fix in a comment in the test

**Phase 1A gate:** All tests pass with 0 failures, 0 errors.

---

## Phase 1B: Frontend

### TASK 1B-1: Create Next.js project

**Prerequisite:** TASK 1A-14 must be complete.

Open a terminal and run:

```bash
cd C:\Users\quoct\codescope
npx create-next-app@latest frontend --typescript --app --no-tailwind --no-eslint --no-src-dir
cd frontend
npm install @monaco-editor/react react-markdown remark-gfm highlight.js lucide-react
```

**Success indicator:** `frontend/package.json` exists with `next`, `react`, `@monaco-editor/react` listed.

---

### TASK 1B-2: Create frontend directory structure

**Prerequisite:** TASK 1B-1 must be complete.

Create these directories:
```
frontend/app/tracer/
frontend/components/editor/
frontend/components/tracer/
frontend/components/llm/
frontend/components/ui/
frontend/hooks/
frontend/lib/
frontend/types/
```

Create these files (empty placeholders):
```
frontend/.env.local         → NEXT_PUBLIC_API_URL=http://localhost:8000
frontend/app/globals.css    → (keep default)
frontend/app/layout.tsx    → (keep default, add dark theme class to body)
frontend/app/page.tsx       → redirect to /tracer
frontend/app/tracer/page.tsx → (main tracer page — implement in TASK 1B-11)
```

**`frontend/.env.local`:**
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

**`frontend/app/layout.tsx`** — modify the default to add a dark body class:
```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CodeScope",
  description: "Visualize Python code execution step by step",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="dark">{children}</body>
    </html>
  );
}
```

**`frontend/app/page.tsx`** — redirect to tracer:
```tsx
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/tracer");
}
```

**`frontend/app/globals.css`** — add dark theme basics:
```css
:root {
  --bg: #0d1117;
  --surface: #161b22;
  --border: #30363d;
  --text: #e6edf3;
  --text-muted: #8b949e;
  --accent: #1f6feb;
  --accent-hover: #388bfd;
  --danger: #f85149;
  --success: #3fb950;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body.dark {
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
```

**Verify:** Run `npm run dev` in the frontend directory, visit `http://localhost:3000`, and verify it redirects to `/tracer` with a blank page.

---

### TASK 1B-3: Implement `types/trace.ts`

**Prerequisite:** TASK 1B-2 must be complete.

**File:** `frontend/types/trace.ts`

```typescript
export interface VariableInfo {
  type: string;
  value: string;
  changed: boolean;
}

export interface TraceStep {
  step_number: number;
  line_number: number;
  bytecode_offset: number;
  opcode: string;
  variables: Record<string, VariableInfo>;
  branches_taken: Record<string, unknown>;
  duration_ms: number;
}

export interface TraceResponse {
  steps: TraceStep[];
  total_steps: number;
  duration_ms: number;
}

export class TraceError extends Error {
  constructor(
    public code: string,
    public detail: unknown
  ) {
    super(code);
    this.name = "TraceError";
  }
}
```

---

### TASK 1B-4: Implement `lib/api.ts`

**Prerequisite:** TASK 1B-3 must be complete.

**File:** `frontend/lib/api.ts`

```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function runTrace(code: string) {
  const res = await fetch(`${API_BASE}/api/traces/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code }),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new TraceError(err.detail?.error ?? "UNKNOWN", err.detail);
  }
  return res.json() as Promise<TraceResponse>;
}

// Import TraceError at runtime to avoid circular deps
import { TraceError, type TraceResponse } from "@/types/trace";
export type { TraceResponse };
```

**Verify:** No runtime check possible yet — will be verified in TASK 1B-11.

---

### TASK 1B-5: Implement `components/ui/Button.tsx`

**Prerequisite:** TASK 1B-2 must be complete.

**File:** `frontend/components/ui/Button.tsx`

```typescript
import { ButtonHTMLAttributes } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger";
  size?: "sm" | "md" | "lg";
}

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  children,
  disabled,
  ...props
}: ButtonProps) {
  const base = "inline-flex items-center justify-center rounded font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2";
  const variants = {
    primary: "bg-[#1f6feb] text-white hover:bg-[#388bfd] focus:ring-[#1f6feb]",
    secondary: "bg-[#21262d] text-[#e6edf3] border border-[#30363d] hover:bg-[#30363d] focus:ring-[#30363d]",
    danger: "bg-[#f85149] text-white hover:bg-[#ff6b61] focus:ring-[#f85149]",
  };
  const sizes = {
    sm: "px-2 py-1 text-xs",
    md: "px-3 py-1.5 text-sm",
    lg: "px-4 py-2 text-base",
  };
  const disabledStyle = disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer";

  return (
    <button
      className={`${base} ${variants[variant]} ${sizes[size]} ${disabledStyle} ${className}`}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
}
```

---

### TASK 1B-6: Implement `components/ui/Modal.tsx`

**Prerequisite:** TASK 1B-2 must be complete.

**File:** `frontend/components/ui/Modal.tsx`

```typescript
import { ReactNode, useEffect } from "react";

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
}

export function Modal({ isOpen, onClose, title, children }: ModalProps) {
  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 50,
        background: "rgba(0,0,0,0.6)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        style={{
          background: "#161b22", border: "1px solid #30363d",
          borderRadius: 8, padding: 24, maxWidth: 480, width: "90%",
        }}
      >
        {title && (
          <h2 style={{ color: "#e6edf3", marginBottom: 16, fontSize: 18, fontWeight: 600 }}>
            {title}
          </h2>
        )}
        {children}
      </div>
    </div>
  );
}
```

---

### TASK 1B-7: Implement `components/ui/ErrorBoundary.tsx`

**Prerequisite:** TASK 1B-2 must be complete.

**File:** `frontend/components/ui/ErrorBoundary.tsx`

```typescript
import { Component, ReactNode } from "react";

interface Props { children: ReactNode; fallback?: ReactNode; }
interface State { hasError: boolean; message: string; }

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, message: "" };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message };
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <div style={{ padding: 16, color: "#f85149", background: "#f8514915", borderRadius: 6 }}>
          <strong>Something went wrong</strong>
          <p style={{ fontSize: 13, marginTop: 4 }}>{this.state.message}</p>
        </div>
      );
    }
    return this.props.children;
  }
}
```

---

### TASK 1B-8: Implement `components/editor/CodeEditor.tsx`

**Prerequisite:** TASK 1B-4 must be complete (needs `runTrace` import).

**File:** `frontend/components/editor/CodeEditor.tsx`

**CRITICAL: Monaco must be lazy-loaded with next/dynamic. Never import it statically.**

```typescript
import { useRef, useEffect } from "react";
import dynamic from "next/dynamic";

// Monaco is ~5MB — lazy load so it's NOT in the initial bundle
const MonacoSkeleton = () => (
  <div style={{ height: "100%", background: "#1e1e1e", borderRadius: 4, padding: 16 }}>
    {[...Array(10)].map((_, i) => (
      <div key={i} style={{
        height: 14, background: "#2d2d2d", borderRadius: 2,
        marginBottom: 12, width: ["35%", "70%", "55%", "80%", "45%", "65%", "50%", "75%", "40%", "60%"][i],
        animation: "pulse 1.5s ease-in-out infinite",
      }} />
    ))}
    <style>{`@keyframes pulse { 0%,100%{opacity:.4}50%{opacity:.7} }`}</style>
  </div>
);

const MonacoEditor = dynamic(
  () => import("@monaco-editor/react").then((mod) => mod.default),
  { ssr: false, loading: () => <MonacoSkeleton /> }
);

interface CodeEditorProps {
  value: string;
  onChange?: (value: string) => void;
  onLineClick?: (lineNumber: number, lineContent: string) => void;
  readOnly?: boolean;
  currentLine?: number | null;
}

export function CodeEditor({
  value,
  onChange,
  onLineClick,
  readOnly = false,
  currentLine = null,
}: CodeEditorProps) {
  const editorRef = useRef<Parameters<Parameters<typeof MonacoEditor>[0]["onMount"]>[0] | null>(null);
  const decorationsRef = useRef<string[]>([]);

  function handleMount(
    editor: Parameters<Parameters<typeof MonacoEditor>[0]["onMount"]>[0]
  ) {
    editorRef.current = editor;

    // Click handler for "Why is this here?"
    if (onLineClick) {
      editor.onMouseDown((e) => {
        const lineNumber = e.target.position?.lineNumber;
        if (lineNumber) {
          const lineContent = editor.getModel()?.getLineContent(lineNumber) ?? "";
          onLineClick(lineNumber, lineContent);
        }
      });
    }
  }

  // Update line highlight when currentLine changes
  useEffect(() => {
    const editor = editorRef.current;
    if (!editor) return;

    const model = editor.getModel();
    if (!model) return;

    const newDecorations = editor.deltaDecorations(
      decorationsRef.current,
      currentLine != null ? [{
        range: { startLineNumber: currentLine, startColumn: 1, endLineNumber: currentLine, endColumn: 1 },
        options: {
          isWholeLine: true,
          className: "trace-current-line",
          glyphMarginClassName: undefined,
          linesDecorationsClassName: "trace-current-line-gutter",
        },
      }] : []
    );
    decorationsRef.current = newDecorations;
  }, [currentLine]);

  return (
    <>
      <style>{`
        .trace-current-line { background: #1F6FEB22 !important; }
        .trace-current-line-gutter {
          background: #1F6FEB;
          width: 4px !important;
          margin-left: 3px;
          border-radius: 2px;
        }
      `}</style>
      <MonacoEditor
        height="100%"
        language="python"
        theme="vs-dark"
        value={value}
        onChange={(v) => onChange?.(v ?? "")}
        onMount={handleMount}
        options={{
          readOnly,
          fontFamily: "'JetBrains Mono', 'Fira Code', Consolas, monospace",
          fontSize: 14,
          lineHeight: 22,
          minimap: { enabled: false },
          wordWrap: "off",
          lineNumbers: "on",
          scrollBeyondLastLine: false,
          automaticLayout: true,
          glyphMargin: true,
          folding: false,
          renderLineHighlight: "none",
        }}
      />
    </>
  );
}
```

---

### TASK 1B-9: Implement `hooks/useTrace.ts`

**Prerequisite:** TASK 1B-8 must be complete (needs `TraceStep` type).

**File:** `frontend/hooks/useTrace.ts`

**CRITICAL: Use requestAnimationFrame, NOT setInterval. Cancel on cleanup.**

```typescript
import { useState, useEffect, useRef, useCallback } from "react";
import type { TraceStep } from "@/types/trace";

const INTERVALS: Record<number, number> = {
  0.5: 1500,
  1: 750,
  2: 375,
  5: 150,
};

interface UseTraceOptions {
  steps: TraceStep[];
  autoPlay?: boolean;
}

interface UseTraceReturn {
  currentStep: number;
  isPlaying: boolean;
  speed: number;
  play: () => void;
  pause: () => void;
  stepForward: () => void;
  stepBackward: () => void;
  setSpeed: (s: 0.5 | 1 | 2 | 5) => void;
  reset: () => void;
  jumpToEnd: () => void;
}

export function useTrace({ steps, autoPlay = false }: UseTraceOptions): UseTraceReturn {
  const [currentStep, setCurrentStep] = useState(0);
  const [isPlaying, setIsPlaying] = useState(autoPlay);
  const [speed, setSpeedState] = useState<0.5 | 1 | 2 | 5>(1);

  const rafIdRef = useRef<number>(0);
  const lastTimestampRef = useRef<number>(0);
  const isPlayingRef = useRef(isPlaying);

  // Keep isPlayingRef in sync with state
  useEffect(() => { isPlayingRef.current = isPlaying; }, [isPlaying]);

  // rAF animation loop
  useEffect(() => {
    if (!isPlaying || steps.length === 0) return;

    function tick(timestamp: number) {
      if (!isPlayingRef.current) return;

      if (lastTimestampRef.current === 0) {
        lastTimestampRef.current = timestamp;
      }

      const elapsed = timestamp - lastTimestampRef.current;
      const interval = INTERVALS[speed];

      if (elapsed >= interval) {
        setCurrentStep((prev) => {
          if (prev < steps.length - 1) {
            lastTimestampRef.current = timestamp;
            return prev + 1;
          } else {
            // End of trace — pause
            setIsPlaying(false);
            return prev;
          }
        });
      }

      rafIdRef.current = requestAnimationFrame(tick);
    }

    rafIdRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafIdRef.current) {
        cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = 0;
      }
    };
  }, [isPlaying, steps.length, speed]);

  // Pause when tab is hidden
  useEffect(() => {
    const handler = () => {
      if (document.hidden) {
        setIsPlaying(false);
      }
    };
    document.addEventListener("visibilitychange", handler);
    return () => document.removeEventListener("visibilitychange", handler);
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Don't trigger if user is typing in an input
      if ((e.target as HTMLElement).tagName === "INPUT") return;

      switch (e.key) {
        case " ":
          e.preventDefault();
          setIsPlaying((p) => !p);
          break;
        case "ArrowRight":
          e.preventDefault();
          setCurrentStep((p) => Math.min(p + 1, steps.length - 1));
          break;
        case "ArrowLeft":
          e.preventDefault();
          setCurrentStep((p) => Math.max(p - 1, 0));
          break;
        case "Home":
          e.preventDefault();
          setCurrentStep(0);
          break;
        case "End":
          e.preventDefault();
          setCurrentStep(steps.length - 1);
          break;
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [steps.length]);

  // Reset when steps change (new trace)
  useEffect(() => {
    setCurrentStep(0);
    setIsPlaying(autoPlay);
    lastTimestampRef.current = 0;
  }, [steps, autoPlay]);

  const play = useCallback(() => {
    if (currentStep >= steps.length - 1) setCurrentStep(0);
    setIsPlaying(true);
  }, [currentStep, steps.length]);

  const pause = useCallback(() => {
    setIsPlaying(false);
    lastTimestampRef.current = 0;
  }, []);

  const stepForward = useCallback(() => {
    setCurrentStep((p) => Math.min(p + 1, steps.length - 1));
  }, [steps.length]);

  const stepBackward = useCallback(() => {
    setCurrentStep((p) => Math.max(p - 1, 0));
  }, []);

  const setSpeed = useCallback((s: 0.5 | 1 | 2 | 5) => {
    setSpeedState(s);
  }, []);

  const reset = useCallback(() => {
    setCurrentStep(0);
    setIsPlaying(false);
    lastTimestampRef.current = 0;
  }, []);

  const jumpToEnd = useCallback(() => {
    setCurrentStep(steps.length - 1);
    setIsPlaying(false);
    lastTimestampRef.current = 0;
  }, [steps.length]);

  return {
    currentStep,
    isPlaying,
    speed,
    play,
    pause,
    stepForward,
    stepBackward,
    setSpeed,
    reset,
    jumpToEnd,
  };
}
```

---

### TASK 1B-10: Implement VariablePanel + AnimationControls

**Prerequisite:** TASK 1B-9 must be complete.

**File:** `frontend/components/tracer/VariablePanel.tsx`

```typescript
import type { TraceStep, VariableInfo } from "@/types/trace";

const TYPE_COLORS: Record<string, string> = {
  int: "#3b82f6",
  str: "#22c55e",
  list: "#a855f7",
  dict: "#f97316",
  tuple: "#a855f7",
  set: "#f97316",
  bool: "#f59e0b",
  float: "#3b82f6",
  NoneType: "#6b7280",
  function: "#6b7280",
};

interface VariablePanelProps {
  currentStep: TraceStep | null;
  totalSteps: number;
}

export function VariablePanel({ currentStep, totalSteps }: VariablePanelProps) {
  if (!currentStep || totalSteps === 0) {
    return (
      <div style={{ padding: 24, color: "#8b949e", textAlign: "center" }}>
        <div style={{ fontSize: 32, marginBottom: 8 }}>▶</div>
        <p>Run the trace to see variable states</p>
      </div>
    );
  }

  const variables = Object.entries(currentStep.variables ?? {});

  return (
    <>
      <style>{`
        @keyframes var-pulse {
          0% { background: #f9731622; }
          100% { background: transparent; }
        }
        .var-changed { animation: var-pulse 0.4s ease-out; }
      `}</style>
      <div style={{ padding: 16 }}>
        <div style={{ fontSize: 12, color: "#8b949e", marginBottom: 12, fontFamily: "monospace" }}>
          STEP {currentStep.step_number + 1} / {totalSteps} · LINE {currentStep.line_number}
        </div>
        {variables.length === 0 ? (
          <p style={{ color: "#8b949e", fontSize: 13 }}>No variables in scope</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {variables.map(([name, info]) => (
              <VariableCard key={name} name={name} info={info} />
            ))}
          </div>
        )}
      </div>
    </>
  );
}

function VariableCard({ name, info }: { name: string; info: VariableInfo }) {
  const color = TYPE_COLORS[info.type] ?? "#8b949e";
  const displayValue = info.value.length > 80 ? info.value.slice(0, 80) + "…" : info.value;

  return (
    <div
      className={info.changed ? "var-changed" : ""}
      style={{
        background: "#0d1117",
        border: "1px solid #30363d",
        borderRadius: 6,
        padding: "10px 12px",
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 13,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
        <span style={{ color: "#e6edf3", fontWeight: 500 }}>{name}</span>
        <span
          style={{
            background: color + "22",
            color: color,
            border: `1px solid ${color}44`,
            borderRadius: 4,
            padding: "1px 6px",
            fontSize: 11,
          }}
        >
          {info.type}
        </span>
      </div>
      <div style={{ color: "#8b949e", wordBreak: "break-all" }}>{displayValue}</div>
    </div>
  );
}
```

**File:** `frontend/components/tracer/AnimationControls.tsx`

```typescript
interface AnimationControlsProps {
  isPlaying: boolean;
  currentStep: number;
  totalSteps: number;
  speed: number;
  onPlay: () => void;
  onPause: () => void;
  onStepForward: () => void;
  onStepBackward: () => void;
  onReset: () => void;
  onJumpToEnd: () => void;
  onSpeedChange: (s: 0.5 | 1 | 2 | 5) => void;
}

const SPEEDS: Array<0.5 | 1 | 2 | 5> = [0.5, 1, 2, 5];

export function AnimationControls({
  isPlaying,
  currentStep,
  totalSteps,
  speed,
  onPlay,
  onPause,
  onStepForward,
  onStepBackward,
  onReset,
  onJumpToEnd,
  onSpeedChange,
}: AnimationControlsProps) {
  const atStart = currentStep === 0;
  const atEnd = currentStep === totalSteps - 1 || totalSteps === 0;

  const btnStyle: React.CSSProperties = {
    display: "inline-flex", alignItems: "center", justifyContent: "center",
    width: 36, height: 36, borderRadius: 6,
    background: "#21262d", border: "1px solid #30363d",
    color: "#e6edf3", cursor: "pointer", fontSize: 14,
    transition: "background 0.15s",
  };

  return (
    <div
      style={{
        display: "flex", alignItems: "center", gap: 8,
        padding: "12px 16px",
        background: "#161b22", borderTop: "1px solid #30363d",
      }}
    >
      {/* Play/Pause */}
      <button
        style={btnStyle}
        onClick={isPlaying ? onPause : onPlay}
        aria-label={isPlaying ? "Pause" : "Play"}
        title={isPlaying ? "Pause (Space)" : "Play (Space)"}
      >
        {isPlaying ? "⏸" : "▶"}
      </button>

      {/* Step Back */}
      <button
        style={{ ...btnStyle, opacity: atStart ? 0.4 : 1 }}
        onClick={onStepBackward}
        disabled={atStart}
        aria-label="Step backward"
        title="Step backward (←)"
      >
        ⏮
      </button>

      {/* Step Forward */}
      <button
        style={{ ...btnStyle, opacity: atEnd ? 0.4 : 1 }}
        onClick={onStepForward}
        disabled={atEnd}
        aria-label="Step forward"
        title="Step forward (→)"
      >
        ⏭
      </button>

      {/* Reset */}
      <button
        style={btnStyle}
        onClick={onReset}
        aria-label="Reset"
        title="Reset (Home)"
      >
        ↺
      </button>

      {/* Speed selector */}
      <div style={{ display: "flex", gap: 2, marginLeft: 8 }}>
        {SPEEDS.map((s) => (
          <button
            key={s}
            onClick={() => onSpeedChange(s)}
            style={{
              padding: "4px 8px",
              borderRadius: 4,
              background: speed === s ? "#1f6feb" : "#21262d",
              border: "1px solid",
              borderColor: speed === s ? "#1f6feb" : "#30363d",
              color: "#e6edf3",
              cursor: "pointer",
              fontSize: 12,
              fontFamily: "monospace",
            }}
            title={`Speed ${s}x`}
          >
            {s}×
          </button>
        ))}
      </div>

      {/* Step counter */}
      <div style={{
        marginLeft: "auto", color: "#8b949e", fontSize: 13,
        fontFamily: "monospace",
      }}>
        Step {currentStep + 1} / {totalSteps || 1}
      </div>
    </div>
  );
}
```

---

### TASK 1B-11: Implement `app/tracer/page.tsx`

**Prerequisite:** All TASK 1B-* must be complete.

**File:** `frontend/app/tracer/page.tsx`

```typescript
"use client";

import { useState, useCallback } from "react";
import { CodeEditor } from "@/components/editor/CodeEditor";
import { VariablePanel } from "@/components/tracer/VariablePanel";
import { AnimationControls } from "@/components/tracer/AnimationControls";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { ErrorBoundary } from "@/components/ui/ErrorBoundary";
import { useTrace } from "@/hooks/useTrace";
import { runTrace } from "@/lib/api";
import type { TraceResponse, TraceStep } from "@/types/trace";

const DEFAULT_CODE = `# Paste or type Python code here
def fib(n):
    if n <= 1:
        return n
    return fib(n - 1) + fib(n - 2)

result = fib(5)
`;

export default function TracerPage() {
  const [code, setCode] = useState(DEFAULT_CODE);
  const [traceResult, setTraceResult] = useState<TraceResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showWarningModal, setShowWarningModal] = useState(false);
  const [warningPatterns, setWarningPatterns] = useState<string[]>([]);

  const { currentStep, isPlaying, speed, play, pause, stepForward, stepBackward, setSpeed, reset, jumpToEnd } =
    useTrace({ steps: traceResult?.steps ?? [], autoPlay: false });

  const currentTraceStep: TraceStep | null =
    traceResult?.steps[currentStep] ?? null;

  async function handleTrace() {
    if (!code.trim()) return;

    setIsLoading(true);
    setError(null);

    try {
      const result = await runTrace(code);
      setTraceResult(result);
      setError(null);
    } catch (err) {
      const traceErr = err as { code?: string; detail?: { error?: string; matched?: string[]; warnings?: string[] } };
      if (traceErr.code === "SIDE_EFFECT_BLOCKED") {
        setWarningPatterns(traceErr.detail?.matched ?? []);
        setShowWarningModal(true);
      } else {
        setError(traceErr.detail?.error ?? String(err));
      }
      setTraceResult(null);
    } finally {
      setIsLoading(false);
    }
  }

  const isEmpty = !code.trim();
  const isLoadingOrEmpty = isLoading || isEmpty;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100vh", background: "#0d1117" }}>
      {/* Header */}
      <header style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "12px 16px", background: "#161b22",
        borderBottom: "1px solid #30363d",
      }}>
        <h1 style={{ fontSize: 18, fontWeight: 600, color: "#e6edf3" }}>CodeScope</h1>
        <div style={{ display: "flex", gap: 8 }}>
          <Button
            variant="primary"
            onClick={handleTrace}
            disabled={isLoadingOrEmpty}
            aria-label="Run trace"
          >
            {isLoading ? "Tracing…" : "▶ Trace"}
          </Button>
        </div>
      </header>

      {/* Main content: editor (60%) + panel (40%) */}
      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        {/* Left: Monaco Editor */}
        <div style={{ flex: "0 0 60%", borderRight: "1px solid #30363d", position: "relative" }}>
          <ErrorBoundary
            fallback={<div style={{ padding: 16, color: "#f85149" }}>Editor failed to load</div>}
          >
            <CodeEditor
              value={code}
              onChange={setCode}
              currentLine={currentTraceStep?.line_number ?? null}
              readOnly={isLoading}
            />
          </ErrorBoundary>

          {/* Error bar */}
          {error && (
            <div style={{
              position: "absolute", bottom: 0, left: 0, right: 0,
              background: "#f8514922", borderTop: "1px solid #f85149",
              color: "#f85149", padding: "8px 16px", fontSize: 13,
            }}>
              Error: {error}
            </div>
          )}
        </div>

        {/* Right: Variable Panel */}
        <div style={{ flex: "0 0 40%", overflowY: "auto" }}>
          <ErrorBoundary
            fallback={<div style={{ padding: 16, color: "#f85149" }}>Panel failed</div>}
          >
            <VariablePanel
              currentStep={currentTraceStep}
              totalSteps={traceResult?.total_steps ?? 0}
            />
          </ErrorBoundary>
        </div>
      </div>

      {/* Bottom: Animation Controls */}
      <AnimationControls
        isPlaying={isPlaying}
        currentStep={currentStep}
        totalSteps={traceResult?.total_steps ?? 0}
        speed={speed}
        onPlay={play}
        onPause={pause}
        onStepForward={stepForward}
        onStepBackward={stepBackward}
        onReset={reset}
        onJumpToEnd={jumpToEnd}
        onSpeedChange={setSpeed}
      />

      {/* Warning Modal: side effects detected */}
      <Modal
        isOpen={showWarningModal}
        onClose={() => setShowWarningModal(false)}
        title="Code Blocked"
      >
        <p style={{ color: "#e6edf3", marginBottom: 16 }}>
          This code contains patterns that are not allowed for security reasons:
        </p>
        <ul style={{ color: "#f85149", marginBottom: 16, paddingLeft: 20 }}>
          {warningPatterns.map((p) => (
            <li key={p} style={{ marginBottom: 4 }}>{p}</li>
          ))}
        </ul>
        <p style={{ color: "#8b949e", fontSize: 13, marginBottom: 16 }}>
          <code>print()</code> is allowed. All other file/network/system operations are blocked.
        </p>
        <Button variant="secondary" onClick={() => setShowWarningModal(false)}>
          OK
        </Button>
      </Modal>
    </div>
  );
}
```

**Verify:** Run the backend (`python -m uvicorn app.main:app --port 8000`) and frontend (`npm run dev`). Open `http://localhost:3000/tracer`. Type `x = 1` and click "Trace". Variable panel should show `x = 1`.

---

## Phase 1C: AI Explanations (GitHub Models)

### TASK 1C-1: Implement `app/services/github_models.py`

**Prerequisite:** TASK 1A-14 must be complete.

**File:** `backend/app/services/github_models.py`

**IMPORTANT: Use GitHub Models API, NOT Ollama.**

```python
"""
GitHub Models API client for AI explanations.
API: POST https://models.github.ai/inference/chat/completions
Auth: Bearer <GITHUB_MODELS_PAT>
Model: openai/gpt-4.1 (or your preferred model from the catalog)
"""
import httpx
import json
import structlog
from app.config import Settings

logger = structlog.get_logger()
settings = Settings()


SYSTEM_PROMPT = """You are a Python code educator. Explain why a specific line of code exists,
given the current execution context.

Current line: {line_content}
Current variable state: {locals}

Explain in 2-3 sentences. Be precise. Do not explain what the code does
generally — explain WHY this specific line is necessary given the current
state. Include a short code snippet if helpful.

Respond ONLY with the explanation. No preamble like "The line..." needed."""


async def stream_explain(
    code: str,
    line_number: int,
    line_content: str,
    locals_dict: dict,
) -> AsyncGenerator[str, None]:
    """
    Stream tokens from GitHub Models API.
    Yields one token at a time.
    Raises httpx.HTTPStatusError on failure.
    """
    if not settings.github_models_pat:
        # Fallback: return a placeholder message
        placeholder = (
            f"AI explanations are disabled. "
            f"Set GITHUB_MODELS_PAT in backend/.env to enable. "
            f"Line {line_number}: {line_content}"
        )
        for word in placeholder.split():
            yield word + " "
        return

    # Build messages
    system_msg = SYSTEM_PROMPT.format(
        line_content=line_content,
        locals=json.dumps(locals_dict, indent=2),
    )

    messages = [
        {"role": "system", "content": system_msg},
        {
            "role": "user",
            "content": f"Explain this line from the code:\n```python\n{line_content}\n```\nCode context (first 20 lines):\n{code[:1000]}",
        },
    ]

    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
        response = await client.post(
            "https://models.github.ai/inference/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.github_models_pat}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2026-03-10",
                "Content-Type": "application/json",
            },
            json={
                "model": settings.github_models_model,
                "messages": messages,
                "max_tokens": 200,
                "stream": True,
                "temperature": 0.3,
            },
        )
        response.raise_for_status()

        # Stream the response
        async for line in response.aiter_lines():
            if not line.strip():
                continue
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    choices = data.get("choices", [])
                    if choices:
                        delta = choices[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                except json.JSONDecodeError:
                    pass


from typing import AsyncGenerator
```

---

### TASK 1C-2: Implement `app/routers/llm.py`

**Prerequisite:** TASK 1C-1 must be complete.

**File:** `backend/app/routers/llm.py`

```python
"""AI explanation endpoints using GitHub Models."""
from fastapi import APIRouter, Query, HTTPException
from sse_starlette.sse import EventSourceResponse
import json
import structlog

from app.services.github_models import stream_explain

router = APIRouter()
logger = structlog.get_logger()


@router.get("/api/llm/explain/stream")
async def stream_explanation(
    code: str = Query(..., max_length=5000),
    line_number: int = Query(..., ge=1),
    line_content: str = Query(..., max_length=500),
    locals_json: str = Query(..., max_length=2000),
):
    """
    Stream an AI explanation for a specific line of code.
    Returns Server-Sent Events (SSE) with token-by-token streaming.
    """
    # Validate JSON payload before parsing
    try:
        locals_dict = json.loads(locals_json)
    except json.JSONDecodeError:
        raise HTTPException(422, "locals_json must be valid JSON")

    async def event_generator():
        try:
            async for token in stream_explain(code, line_number, line_content, locals_dict):
                yield {
                    "event": "message",
                    "data": json.dumps({"token": token, "provider": "github_models"}),
                }
            yield {"event": "done", "data": ""}
        except Exception as e:
            logger.error("llm_stream_error", error=str(e))
            yield {
                "event": "error",
                "data": json.dumps({"message": str(e)}),
            }

    return EventSourceResponse(event_generator())
```

Add to `backend/app/main.py`:
```python
from app.routers import llm
app.include_router(llm.router)
```

---

### TASK 1C-3: Implement `hooks/useStreamingExplanation.ts`

**Prerequisite:** TASK 1B-11 must be complete.

**File:** `frontend/hooks/useStreamingExplanation.ts`

```typescript
import { useState, useEffect, useRef, useCallback } from "react";

type State = "idle" | "connecting" | "streaming" | "done" | "error";

interface UseStreamingExplanationOptions {
  code: string;
  lineNumber: number;
  lineContent: string;
  locals: Record<string, unknown>;
}

interface UseStreamingExplanationReturn {
  text: string;
  state: State;
  error: string | null;
  provider: string | null;
  start: (options: UseStreamingExplanationOptions) => void;
  stop: () => void;
  retry: () => void;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const MAX_RETRIES = 3;
const RETRY_DELAYS = [1000, 2000, 4000]; // exponential backoff

export function useStreamingExplanation(): UseStreamingExplanationReturn {
  const [text, setText] = useState("");
  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState<string | null>(null);
  const [provider, setProvider] = useState<string | null>(null);

  const esRef = useRef<EventSource | null>(null);
  const retryCountRef = useRef(0);
  const optionsRef = useRef<UseStreamingExplanationOptions | null>(null);

  function stop() {
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
  }

  function start(options: UseStreamingExplanationOptions) {
    stop();
    optionsRef.current = options;
    retryCountRef.current = 0;
    setText("");
    setError(null);
    setState("connecting");

    const query = new URLSearchParams({
      code: options.code,
      line_number: String(options.lineNumber),
      line_content: options.lineContent,
      locals_json: JSON.stringify(options.locals),
    });

    const es = new EventSource(`${API_BASE}/api/llm/explain/stream?${query}`);
    esRef.current = es;

    es.addEventListener("message", (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.token) {
          setText((prev) => prev + data.token);
          setState("streaming");
        }
        if (data.provider) {
          setProvider(data.provider);
        }
      } catch {
        // Ignore malformed messages
      }
    });

    es.addEventListener("done", () => {
      setState("done");
      stop();
    });

    es.addEventListener("error", () => {
      stop();
      if (retryCountRef.current < MAX_RETRIES) {
        retryCountRef.current++;
        setState("connecting");
        setTimeout(() => {
          if (optionsRef.current) start(optionsRef.current);
        }, RETRY_DELAYS[retryCountRef.current - 1]);
      } else {
        setState("error");
        setError("Failed to get explanation. Please try again.");
        retryCountRef.current = 0;
      }
    });
  }

  function retry() {
    retryCountRef.current = 0;
    if (optionsRef.current) start(optionsRef.current);
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => stop();
  }, []);

  return { text, state, error, provider, start, stop, retry };
}
```

---

### TASK 1C-4: Implement `components/llm/ExplanationPanel.tsx`

**Prerequisite:** TASK 1C-3 must be complete.

**File:** `frontend/components/llm/ExplanationPanel.tsx`

```typescript
import { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import hljs from "highlight.js/lib/core";
import python from "highlight.js/lib/languages/python";
import { useStreamingExplanation } from "@/hooks/useStreamingExplanation";

hljs.registerLanguage("python", python);

interface ExplanationPanelProps {
  code: string;
  lineNumber: number;
  lineContent: string;
  locals: Record<string, unknown>;
  onClose: () => void;
}

export function ExplanationPanel({
  code,
  lineNumber,
  lineContent,
  locals,
  onClose,
}: ExplanationPanelProps) {
  const { text, state, error, provider, start, retry } = useStreamingExplanation();
  const hasStarted = useRef(false);

  useEffect(() => {
    if (!hasStarted.current) {
      hasStarted.current = true;
      start({ code, lineNumber, lineContent, locals });
    }
  }, [code, lineNumber, lineContent, locals, start]);

  return (
    <>
      <style>{`
        @keyframes blink { 0%,100%{opacity:1}50%{opacity:0} }
        .blink-cursor::after { content: '|'; animation: blink 1s step-end infinite; color: #1f6feb; }
        .md-content code { background: #21262d; padding: 2px 6px; border-radius: 4px; font-size: 13px; }
        .md-content pre { background: #21262d; padding: 12px; border-radius: 6px; overflow-x: auto; margin: 12px 0; }
        .md-content pre code { background: none; padding: 0; }
      `}</style>
      <div style={{
        background: "#161b22", borderTop: "1px solid #30363d",
        height: 280, display: "flex", flexDirection: "column",
      }}>
        {/* Header */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "12px 16px", borderBottom: "1px solid #30363d",
        }}>
          <div>
            <span style={{ color: "#e6edf3", fontWeight: 600, fontSize: 14 }}>
              Why is this here?
            </span>
            {provider && (
              <span style={{ marginLeft: 8, fontSize: 12, color: "#8b949e" }}>
                🤖 {provider}
              </span>
            )}
          </div>
          <button
            onClick={onClose}
            style={{
              background: "none", border: "none", color: "#8b949e",
              cursor: "pointer", fontSize: 18, lineHeight: 1,
            }}
            aria-label="Close explanation"
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: "auto", padding: "12px 16px" }}>
          {state === "error" ? (
            <div style={{ textAlign: "center", padding: 24 }}>
              <p style={{ color: "#f85149", marginBottom: 12 }}>{error}</p>
              <button
                onClick={retry}
                style={{
                  background: "#1f6feb", color: "white", border: "none",
                  borderRadius: 6, padding: "8px 16px", cursor: "pointer",
                }}
              >
                Try Again
              </button>
            </div>
          ) : (
            <div className="md-content" style={{ color: "#e6edf3", fontSize: 14, lineHeight: 1.6 }}>
              {text === "" && state === "connecting" ? (
                <span style={{ color: "#8b949e" }}>Thinking…</span>
              ) : (
                <div className={state === "streaming" ? "blink-cursor" : ""}>
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      code({ className, children, ...props }) {
                        const match = /language-(\w+)/.exec(className || "");
                        const isInline = !match;
                        if (isInline) {
                          return <code {...props}>{children}</code>;
                        }
                        const highlighted = hljs.highlight(children as string, { language: match[1] }).value;
                        return (
                          <pre>
                            <code
                              className={`hljs language-${match[1]}`}
                              dangerouslySetInnerHTML={{ __html: highlighted }}
                            />
                          </pre>
                        );
                      },
                    }}
                  >
                    {text}
                  </ReactMarkdown>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Code snippet reference */}
        {lineContent && (
          <div style={{
            padding: "8px 16px", borderTop: "1px solid #21262d",
            fontFamily: "monospace", fontSize: 12, color: "#8b949e",
            background: "#0d1117",
          }}>
            <span style={{ color: "#6e7681" }}>Line {lineNumber}: </span>
            <span style={{ color: "#e6edf3" }}>{lineContent}</span>
          </div>
        )}
      </div>
    </>
  );
}
```

---

## Testing Checklist

After completing all tasks, verify each item:

**Phase 1A:**
- [ ] `pytest backend/tests/unit/test_validator.py -v` — all pass
- [ ] `pytest backend/tests/unit/test_tracer.py -v` — all pass
- [ ] `pytest backend/tests/integration/test_trace_flow.py -v` — all pass
- [ ] `curl -X POST http://localhost:8000/api/traces/run -d '{"code":"x=1"}'` — returns steps

**Phase 1B:**
- [ ] `http://localhost:3000/tracer` loads without crash
- [ ] Monaco editor renders with skeleton loading state
- [ ] Clicking "Trace" with `x=1` shows variable panel with `x`
- [ ] Space bar plays/pauses animation
- [ ] ArrowLeft at step 0 does not crash
- [ ] Orange pulse fires when variable changes

**Phase 1C:**
- [ ] Clicking a line in Monaco opens the explanation panel
- [ ] SSE tokens stream word-by-word
- [ ] "Try Again" appears on error
- [ ] Panel closes on × button

---

## Quick Reference: GitHub Models API

| Item | Value |
|---|---|
| Base URL | `https://models.github.ai` |
| Endpoint | `POST /inference/chat/completions` |
| Auth | `Authorization: Bearer <GITHUB_MODELS_PAT>` |
| Headers | `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2026-03-10` |
| Model format | `{publisher}/{model_name}` (e.g., `openai/gpt-4.1`) |
| List models | `GET https://models.github.ai/catalog/models` |
| Streaming | Set `"stream": true` in request, iterate `data: ...` lines |
| PAT scope | `models` (generate at github.com/settings/tokens) |

---

## Phase 1A/1B/1C Gate Criteria

| Phase | Gate | How to verify |
|---|---|---|
| 1A | All pytest tests pass (0 failures) | `pytest backend/ -v` |
| 1B | Manual smoke tests (10 items above) | Browser + DevTools |
| 1C | SSE completes with non-empty text | Browser, click a line |
