# CodeScope Deep Architectural & Performance Analysis

This document provides a deep architectural, security, performance, and usability review of **CogniTrace** (Python/FastAPI backend + React/Vite frontend). 

---

## Analysis Summary

| Finding ID | Component | Vulnerability / Issue | Severity | Priority | Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CT-01** | Backend Core | `httpx.AsyncClient` Connection Pool Churning | **High** | Critical | Register a single `httpx.AsyncClient` in lifespan and share via dependency injection. |
| **CT-02** | Tracer | Uniform Trace Step Durations (Flat Profiling) | **Medium** | High | Measure elapsed time per event inside `tracer_callback` rather than distributing total time. |
| **CT-03** | Database | Nested `IN (SELECT...)` subqueries in Postgres RLS | **Medium** | Medium | Refactor subquery-based RLS policies to use high-performance `EXISTS` clauses. |
| **CT-04** | Analyzer | Broad Non-Boolean Implicit Truthiness Warnings | **Low** | Medium | Adjust AST rules to reduce false-positive warnings on idiomatic checks (`if items:`). |
| **CT-05** | Frontend | Monaco Editor Key Input Character Dropouts | **Low** | Medium | Configure editor settings and E2E scripts to bypass quick-suggestions overlay blockages. |
| **CT-06** | Review Queue | Punishing SM-2 "Hard" Review Interval Reset | **Low** | Low | Introduce a "soft reset" or scale quality map to prevent rapid SRS repetition resets. |

---

## Detailed Findings & Resolutions

### CT-01: `httpx.AsyncClient` Connection Pool Churning (High Severity)

#### Description
Throughout the backend codebase, asynchronous requests to Supabase (and other APIs) spin up a new `httpx.AsyncClient` inside the request context:
- `backend/app/routers/auth.py`
- `backend/app/routers/traces.py`
- `backend/app/routers/review.py`
- `backend/app/dependencies.py`
- `backend/app/main.py`

#### Impact
Using `async with httpx.AsyncClient()` on every request prevents HTTP connection pooling. For each backend action:
1. A socket is opened.
2. A TCP handshake is performed.
3. A TLS negotiation (SSL handshake) is completed (taking 20-50ms).
4. The socket is closed.

Under heavy load, this causes **socket exhaustion** (too many sockets in `TIME_WAIT`), increased database request times, and significant CPU overhead.

#### Recommended Refactoring
We should instantiate a single `httpx.AsyncClient` during FastAPI lifespan startup, store it in `app.state`, and yield it as a dependency.

##### 1. Refactor `backend/app/main.py`
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create a single client with connection pooling
    limits = httpx.Limits(max_keepalive_connections=20, max_connections=100)
    app.state.http_client = httpx.AsyncClient(limits=limits, timeout=10.0)
    
    yield
    
    # Shutdown: Close client cleanly
    await app.state.http_client.aclose()
```

##### 2. Refactor `backend/app/dependencies.py`
Create a FastAPI dependency to fetch the client:
```python
from fastapi import Request

async def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client
```

##### 3. Inject into Routers
Instead of creating clients:
```python
@router.get("/due")
async def get_due_reviews(
    client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
    authorization: str = Header(None)
):
    resp = await client.get(..., headers={"Authorization": f"Bearer {token}"})
```

---

### CT-02: Uniform Trace Step Durations (Medium Severity)

#### Description
In `backend/tracer/tracer.py`, the total execution time of the user code is evenly divided among all trace steps:
```python
    duration_ms = (time.perf_counter() - start_time) * 1000
    if steps:
        per_step = duration_ms / len(steps)
        for step in steps:
            step.duration_ms = round(per_step, 3)
```

#### Impact
This presents misleading performance profiling to learners. A fast assignment (`x = 10`) is represented as taking identical time to a slow calculation (`sum(range(10000))`) or a complex nested function call.

#### Recommended Refactoring
Capture high-precision timestamps inside the tracer's callback to record line-by-line profiling.

```python
def run_trace(source: str, max_steps: int = 500, initial_namespace: dict = None) -> dict:
    ...
    # Keep track of the timestamp when the callback last entered
    last_timestamp = time.perf_counter()

    def tracer_callback(frame, event, arg):
        nonlocal last_timestamp
        ...
        if event == "line":
            current_time = time.perf_counter()
            # Calculate the time taken to run the previous step
            elapsed_ms = (current_time - last_timestamp) * 1000
            last_timestamp = current_time
            
            # Associate execution duration with the prior step
            if steps:
                steps[-1].duration_ms = round(elapsed_ms, 3)
            
            step = TraceStep(
                step_number=len(steps),
                line_number=line_no,
                bytecode_offset=bytecode_offset,
                opcode=opcode,
                variables=variables,
                branches_taken=branches_taken,
                duration_ms=0.0, # Will be filled by the next step's execution time
                call_depth=_get_call_depth(frame),
            )
            steps.append(step)
```

---

### CT-03: Nested `IN (SELECT...)` in Postgres RLS Policies (Medium Severity)

#### Description
In `backend/migrations/V006__fix_rls_policies.sql`, Row-Level Security (RLS) policies use subqueries inside `IN` clauses to check authorization:
```sql
CREATE POLICY "own_traces" ON traces FOR ALL
    USING (user_id IN (SELECT id FROM profiles WHERE user_id = auth.uid()));
```

#### Impact
PostgreSQL processes RLS policies on a **per-row** basis for target select queries. An `IN (SELECT ...)` subquery requires a scan of the profiles table. If `traces` or `explanations` grows large, this results in significant query planning overhead and nested loop scans, dramatically reducing API performance.

#### Recommended Refactoring
Replace `IN (SELECT...)` subqueries with structured `EXISTS` clauses, which allow the Postgres query planner to stop matching immediately upon finding the first valid reference.

```sql
-- Traces
CREATE POLICY "own_traces" ON traces FOR ALL
    USING (EXISTS (
        SELECT 1 FROM profiles 
        WHERE profiles.id = traces.user_id 
          AND profiles.user_id = auth.uid()
    ));

-- Review Cards
CREATE POLICY "own_cards" ON review_cards FOR ALL
    USING (EXISTS (
        SELECT 1 FROM profiles 
        WHERE profiles.id = review_cards.user_id 
          AND profiles.user_id = auth.uid()
    ));
```

---

### CT-04: Broad Non-Boolean Implicit Truthiness Warnings (Low Severity)

#### Description
In `backend/analyzers/static_analysis.py`, `_check_implicit_truthiness` flags variables in conditional conditions that do not look like booleans.

#### Impact
This heuristic is too broad. Standard, highly-idiomatic Python code regularly checks collection status or truthiness via implicit checks (e.g. `if items:`). 
Flagging these idiomatic expressions as dynamic warnings increases user noise.

#### Recommended Refactoring
Demote this pattern to `low` severity.

```python
    annotations.append(
        Annotation(
            line=node.lineno,
            severity="low", # Demoted from medium
            pattern_id="implicit_truthiness",
            message=(
                f"`if {name}:` is True for any non-empty sequence/number. "
                f"Ensure this matches your logic."
            ),
            suggestion=f"If checking for a non-empty sequence, verify; otherwise make explicit: if {name} is not None:",
        )
    )
```

---

### CT-05: Monaco Editor space drops (Low Severity)

#### Description
During rapid, programmatic typing in Monaco Editor (under E2E test runs), raw spaces can occasionally get dropped due to event listeners reacting to Monaco's intellisense dropdown overlays. 

#### Impact
Requires automated E2E tests to write syntax like `if(x>5):` (avoiding spaces) rather than standard PEP 8 spacing (`if x > 5:`).

#### Recommended Refactoring
Configure the Monaco Editor wrapper in `frontend/components/editor/CodeEditor.tsx` to disable aggressive autolayout, context dropdowns, and quick suggestions.

```typescript
const editorOptions = {
  automaticLayout: true,
  quickSuggestions: { other: false, comments: false, strings: false },
  wordBasedSuggestions: "off",
  parameterHints: { enabled: false },
  suggestOnTriggerCharacters: false,
};
```

---

### CT-06: Punishing SM-2 "Hard" Review Interval Reset (Low Severity)

#### Description
In `backend/app/routers/review.py`, quality ratings less than 3 (which include `again` = 1, and `hard` = 2) force a complete reset of the review interval back to 1 day and repetitions back to 0:
```python
    if quality < 3:
        # Failed — reset to 1 day
        new_interval = 1
        new_repetitions = 0
```

#### Impact
Resetting a card that has been successfully reviewed 10 times back to 0 repetitions because of a single slip-up creates a "learning bottleneck" (too many duplicate reviews).

#### Recommended Refactoring
Change SM-2 rating mapping to treat "hard" (quality 2) as a **soft-fail**. Instead of resetting repetitions to 0, reduce repetitions by half, and compute a shorter interval (e.g., half the current interval, but not below 1 day).

```python
    if quality < 2: # Only "again" (quality 1) does a hard reset
        new_interval = 1
        new_repetitions = 0
    elif quality == 2: # "hard" does a soft deduction
        new_repetitions = max(1, repetitions // 2)
        new_interval = max(1, round(interval_days * 0.5))
    else:
        # standard SM-2 logic
```
