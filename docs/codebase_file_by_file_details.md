# CodeScope — Detailed File-by-File Codebase Walkthrough

This document provides a highly technical, file-by-file breakdown of the core Python backend modules of the CodeScope tutoring system. Use this as a guide to explain the exact inputs, outputs, and design choices of each file to your supervisor.

---

## 📂 1. Dynamic Tracing & Sandboxing (Subsystem: `backend/tracer/`)

### 📄 File: [runner.py](file:///c:/Users/quoct/codescope/backend/tracer/runner.py)
*   **Purpose**: Safely executes untrusted, student-submitted code in an isolated operating system process.
*   **Core Function**: `run_trace(source: str, max_steps: int = 500, initial_namespace: dict = None, timeout_seconds: int = 5) -> dict`
*   **Key Logic**:
    1.  **Temp File Generation**: Uses `tempfile.mkstemp(suffix=".py")` to write a wrapper execution script.
    2.  **OS Security Boundaries**: Writes a block wrapped in `try...except ImportError` to invoke `resource.setrlimit`. It sets `RLIMIT_AS` (virtual memory address space) to **256MB** and `RLIMIT_CPU` (CPU time limit) to **4 seconds** to prevent memory leaks or compute exhaustion.
    3.  **Namespace Capture**: Serializes `initial_namespace` to JSON and injects it. Restores `sys.stdout` to an in-memory buffer (`io.StringIO()`) so prints in user code don't pollute the final JSON output.
    4.  **Subprocess Spawning**: Invokes `subprocess.Popen([sys.executable, tmp_path])` and waits with a 5-second `communicate()` timeout.
    5.  **Cleanup**: Uses `os.unlink()` in a `finally` block to guarantee temp files are deleted even on crashes.
*   **Supervisor Talking Points**: 
    > *"This file is the boundary of our execution sandbox. By offloading execution to a separate subprocess and enforcing limits on CPU and RAM, we ensure that infinite loops or memory leaks in user code never crash the FastAPI backend."*

---

### 📄 File: [tracer.py](file:///c:/Users/quoct/codescope/backend/tracer/tracer.py)
*   **Purpose**: Captures execution states step-by-step using CPython frames and generates interactive tutor questions.
*   **Core Functions**:
    *   `run_trace(source: str, max_steps: int, initial_namespace: dict) -> dict`
    *   `tracer_callback(frame, event, arg)`
    *   `generate_tutor_checkpoints(steps: list, code: str) -> list`
*   **Key Logic**:
    1.  **Abstract Syntax Tree Parsing**: Before running the code, `_build_jump_map` parses the code using `ast.walk` to find control branches (`ast.If`, `ast.For`, `ast.While`, `ast.BoolOp`).
    2.  **Bytecode Mapping**: Uses the standard `dis` library (`_build_opcode_map`) to map bytecode offsets to human-readable names (e.g. `COMPARE_OP`, `POP_JUMP_IF_FALSE`).
    3.  **Trace Registration**: Calls `sys.settrace(tracer_callback)`. The callback intercepts `'line'` and `'return'` events inside frames matching the source file name `<codescope>`.
    4.  **Namespace Differencing**: For each step, it records local variables, comparing their representations with the previous step to mark modified variables (`changed = True`).
    5.  **Checkpoint Synthesis**: `generate_tutor_checkpoints` generates multiple-choice questions dynamically. If the code crashes, it creates an `exception_prediction` checkpoint. Otherwise, it generates `branch_prediction` (asking if a condition evaluates to True) or `variable_prediction` checkpoints.
*   **Supervisor Talking Points**: 
    > *"By tracking `sys.settrace()` events and mapping them back to compiler offsets, we compile a chronological list of states. We also evaluate conditional branches in the runtime namespace to track whether loops iterate or skip."*

---

### 📄 File: [validator.py](file:///c:/Users/quoct/codescope/backend/tracer/validator.py)
*   **Purpose**: Validates code structure prior to execution.
*   **Core Function**: `validate_code(source: str) -> tuple[bool, list, list]`
*   **Key Logic**:
    *   Walks the parsed AST tree.
    *   Applies a blacklist check against `Import` and `ImportFrom` nodes. Any import containing `os`, `subprocess`, `sys`, `socket`, `requests`, etc. is flagged.
    *   Detects references to unsafe functions like `open()`, `eval()`, or attribute references mapping to private object components (dunder methods like `__subclasses__`).
*   **Supervisor Talking Points**:
    > *"This serves as our static guardrail. We parse the code structure into syntax trees and filter out any dangerous methods before we pass the payload to the subprocess runner."*

---

## 📂 2. Static Code Quality Analyzers (Subsystem: `backend/analyzers/`)

### 📄 File: [static_analysis.py](file:///c:/Users/quoct/codescope/backend/analyzers/static_analysis.py)
*   **Purpose**: Runs static analysis on user code to detect logic bugs that common code generators (like Copilot) introduce.
*   **Core Function**: `analyze_code(source_code: str) -> list[Annotation]`
*   **Checks Performed**:
    1.  **Missing None Guards**: Checks if variables assigned value from functions that can return `None` (like dict get or find) are dereferenced without an preceding `if variable is not None` guard.
    2.  **Mutable Default Arguments**: Detects signatures like `def process(items=[])` where modifications to the list persist across multiple invocations.
    3.  **Aggressive Filters**: Checks list comprehensions with filters that might result in empty returns under normal inputs.
    4.  **Implicit Truthiness Checks**: Identifies comparisons like `if list_var == []` suggesting standard `if not list_var` conventions.
*   **Supervisor Talking Points**:
    > *"This file runs Phase 0 checks. Instead of checking runtime values, it parses AST declarations to detect anti-patterns and code quality problems, providing actionable warnings to students."*

---

## 📂 3. Web Service & API Endpoints (Subsystem: `backend/app/routers/` & `backend/api/`)

### 📄 File: [routes.py](file:///c:/Users/quoct/codescope/backend/api/routes.py)
*   **Purpose**: Exposes the static analysis check route for CodeScope's Phase 0 operations.
*   **Endpoints**: `POST /api/analyze`
*   **Core Logic**: Accepts code inputs, runs `analyze_code()` from the analyzers subsystem, and maps results to a standardized schema list (line, message, severity, suggestion).

---

### 📄 File: [traces.py](file:///c:/Users/quoct/codescope/backend/app/routers/traces.py)
*   **Purpose**: Manages execution requests, trace records database management, and sharing dashboards.
*   **Endpoints**:
    *   `POST /traces/run`: Invokes sandboxed subprocess execution.
    *   `GET /dashboard`: Aggregates user's streak statistics, due review cards, and past traces in a single query.
    *   `POST /traces`: Saves code structures and serialized steps in Supabase for fast frontend replays.
    *   `POST /traces/{trace_id}/share`: Generates custom token share URLs, allowing password protection and expiration dates.
*   **Key Design Patterns**:
    *   Integrates rate limiting dependencies (`slowapi`) limiting anonymous submissions.
    *   Offloads heavy subprocess calls to async thread execution pools using `run_with_concurrency_limit`.
*   **Supervisor Talking Points**:
    > *"This router is the entry point for the execution subsystem. It handles user state management, rate limits free accounts, and stores trace execution steps to Supabase so that trace replays load instantly."*

---

### 📄 File: [llm.py](file:///c:/Users/quoct/codescope/backend/app/routers/llm.py)
*   **Purpose**: Streams grounded explanations and performs misconception analysis.
*   **Endpoints**:
    *   `GET /explain/stream`: Serves Server-Sent Events (SSE) streaming token packets for dynamic reading.
    *   `POST /diagnose`: Diagnoses incorrect checkpoint submissions.
*   **Key Logic**:
    *   **SSE Stream**: Uses `EventSourceResponse` from `sse-starlette` to feed a generator. It yields serialized data chunks containing token strings and provider info (e.g. `Ollama`, `GitHub Models`).
    *   **Misconception Pipeline**: When a student predicts a checkpoint incorrectly, the backend uses `llm_router.diagnose_misconception` to analyze the error. If authorized, the backend automatically writes a card to Supabase to schedule reviews on this tag.

---

### 📄 File: [review.py](file:///c:/Users/quoct/codescope/backend/app/routers/review.py)
*   **Purpose**: Schedules review cards and assesses recall challenges.
*   **Core Functions**:
    *   `sm2_calculate(quality: int, easiness_factor: float, interval_days: int, repetitions: int) -> tuple`
    *   `GET /due`: Fetches card listings due for review today.
    *   `POST /grade`: Evaluates student solutions using automated LLM checks.
    *   `POST /{card_id}`: Updates a card's SM-2 intervals.
*   **Key Logic**:
    *   **Custom SM-2 Algorithm**: Quality is mapped to values 0-5. For rating `Hard` ($q=2$), repetitions and intervals are halved ($Rep = Rep / 2, I = I \times 0.5$) instead of resetting to 0 and 1 day, which helps keep cards in rotation.
    *   **Challenge Integration**: If card has a tagged misconception, it requests the LLM to generate a customized **Code Repair Challenge** based on the code trace.
*   **Supervisor Talking Points**:
    > *"We modified the classic SM-2 algorithm to introduce a 'Soft-Fail' recovery. Standard SM-2 penalizes failure heavily by resetting intervals. By simply halving parameters for 'Hard' ratings, we keep students engaged with difficult topics."*

---

## 📂 4. Services (Subsystem: `backend/app/services/`)

### 📄 File: [llm_router.py](file:///c:/Users/quoct/codescope/backend/app/services/llm_router.py)
*   **Purpose**: Configures multi-tier LLM integrations, explanation caching, and structured prompts.
*   **Core Methods**:
    *   `stream_explain(...)`: Streams explanations via Server-Sent Events.
    *   `diagnose_misconception(...)`: Formats mismatched predictions to detect user logic errors.
*   **Key Logic**:
    *   **Content-Addressed Cache**: Hashes parameters `SHA-256(code + line_number + variable_state)` to check for cached answers before querying the LLM, reducing latency to <10ms on cached lines.
    *   **Router Fallback**: Uses a three-tier connection model (Ollama Cloud primary -> Local Ollama fallback -> OpenAI/Claude public API backup).
