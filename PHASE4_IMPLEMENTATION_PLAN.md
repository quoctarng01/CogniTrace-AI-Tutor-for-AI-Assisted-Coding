# Phase 4 Implementation Plan — CodeScope Examples + Review Queue

**Target score:** ≥ 9.0/10 on completeness, correctness, implementation clarity, educational value, backend architecture, frontend architecture, test coverage, and red flags.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Example Data (25 Records)](#2-example-data-25-records)
3. [Database Migration](#3-database-migration)
4. [Backend Router — `examples.py](#4-backend-router--examplespy)`
5. [Router Registration in `main.py](#5-router-registration-in-mainpy)`
6. [Backend Tests — `test_examples.py](#6-backend-tests--test_examplespy)`
7. [Frontend API Functions — `api.ts` additions](#7-frontend-api-functions--apits-additions)
8. [Frontend Browse Page — `app/examples/page.tsx](#8-frontend-browse-page--appexamplespagetsx)`
9. [Frontend Browse Loading State — `app/examples/loading.tsx](#9-frontend-browse-loading-state--appexamplesloadingtsx)`
10. [Frontend Detail Page — `app/examples/[id]/page.tsx](#10-frontend-detail-page--appexamplesidpagetsx)`
11. [Frontend Detail Loading State — `app/examples/[id]/loading.tsx](#11-frontend-detail-loading-state--appexamplesidloadingtsx)`
12. [CSS Files](#12-css-files)
13. [Navigation Link in Dashboard](#13-navigation-link-in-dashboard)
14. [File Creation Order](#14-file-creation-order)
15. [Error Recovery](#15-error-recovery)
16. [Verification Commands](#16-verification-commands)
17. [Success Criteria Checklist](#17-success-criteria-checklist)

---

## 1. Prerequisites

Before beginning Phase 4, verify the following:

- **Supabase project is live** with Phase 1–3 tables already created: `profiles`, `traces`, `review_cards`, `explanations`.
- **Backend environment variables** in `backend/.env`:
  ```
  SUPABASE_URL=https://your-project-ref.supabase.co
  SUPABASE_SERVICE_KEY=your-service-role-key
  ```
- **Frontend environment variables** in `frontend/.env.local`:
  ```
  NEXT_PUBLIC_SUPABASE_URL=https://your-project-ref.supabase.co
  NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
  NEXT_PUBLIC_API_URL=http://localhost:8000
  ```
- **Run backend unit tests first** (before touching frontend):
  ```bash
  cd backend
  python -m pytest tests/unit/test_examples.py -v
  ```
- **Install frontend dependencies** if not already done:
  ```bash
  cd frontend && npm install react-syntax-highlighter
  ```
- **Backend must be running** (`cd backend && uvicorn app.main:app --reload`) before testing frontend integration.

---

## 2. Example Data (25 Records)

Each record below is ready to INSERT into the `examples` table. Fields: `id` (UUID), `category`, `title`, `code`, `why_ai_generates_this`, `annotations` (JSON), `explanation` (plain text, no HTML), `common_mistakes` (array, ≥2 each), `review_interval` (int days).

### 2.1 — Nested Comprehension with Filter

```python
# id: 11111111-1111-1111-1111-111111111101
# category: comprehensions
# title: Nested List Comprehension with Conditional Filter
# review_interval: 3

matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
evens = [x for row in matrix for x in row if x % 2 == 0]
```

**annotations (JSON):**

```json
[
  {"line": 1, "text": "Assign the variable 'matrix' to a list of three lists (a 3x3 grid).", "type": "assignment"},
  {"line": 2, "text": "Outer iterator — iterates over each inner list in the matrix, one row at a time.", "type": "iterator"},
  {"line": 2, "text": "Inner iterator — unpacks each element x from the current row.", "type": "iterator"},
  {"line": 2, "text": "Guard condition — keeps only even numbers. Odd values are discarded.", "type": "filter"},
  {"line": 2, "text": "Collects passing values into the resulting flat list.", "type": "scope"}
]
```

**explanation:** This flattens a 3×3 matrix into a single list of only the even numbers [2, 4, 6, 8]. The outer comprehension builds the row-level scope; the inner clause extracts each element; the `if` clause acts as a guard to filter conditionally.

**common_mistakes:** Forgetting the inner iterator clause (`for x in row`) and only writing one `for` — resulting in a list of lists instead of a flat list. Using `x % 2 != 0` instead of `== 0` and then being surprised by which numbers appear.

---

### 2.2 — Dict from Zip

```python
# id: 11111111-1111-1111-1111-111111111102
# category: comprehensions
# title: Building a Dictionary from Two Zipped Lists
# review_interval: 3

keys   = ["name", "age", "city"]
values = ["Alice", 30, "Boston"]
d      = dict(zip(keys, values))
```

**annotations (JSON):**

```json
[
  {"line": 1, "text": "Bind the name 'keys' to the list of string keys.", "type": "assignment"},
  {"line": 2, "text": "Bind the name 'values' to the list of corresponding values.", "type": "assignment"},
  {"line": 3, "text": "zip() pairs elements at matching indices into tuples: ('name','Alice'), ('age',30), ...", "type": "iterator"},
  {"line": 3, "text": "dict() consumes the zip iterator and constructs a mapping from those tuples.", "type": "factory"}
]
```

**explanation:** `zip(keys, values)` creates an iterator of 2-tuples by walking both lists in parallel. `dict()` consumes that iterator and builds a standard Python dict. This is the idiomatic replacement for the error-prone `{}` + loop pattern.

**common_mistakes:** Passing lists of unequal length — zip silently truncates to the shorter list, losing data. Forgetting that `dict()` on a zip object consumes it (calling `dict(zip(...))` twice fails the second time).

---

### 2.3 — Set with Deduplication + Sort

```python
# id: 11111111-1111-1111-1111-111111111103
# category: comprehensions
# title: Set Comprehension with Sorted Output
# review_interval: 2

data = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5]
unique_sorted = sorted({x for x in data if x > 2})
```

**annotations (JSON):**

```json
[
  {"line": 1, "text": "Assign a list of integers to 'data', with deliberate duplicates.", "type": "assignment"},
  {"line": 2, "text": "Set comprehension — collects values passing the filter, automatically discarding duplicates.", "type": "iterator"},
  {"line": 2, "text": "Filter guard — keeps only values strictly greater than 2.", "type": "filter"},
  {"line": 2, "text": "sorted() converts the set back to a list ordered ascending.", "type": "factory"}
]
```

**explanation:** The set comprehension `{x for x in data if x > 2}` deduplicates automatically because sets cannot hold duplicate keys. `sorted()` then converts the unordered set into an ascending list.

**common_mistakes:** Assuming set order is preserved (sets are inherently unordered in Python < 3.7; dict insertion order is guaranteed, not set order). Using `x >= 2` and being surprised that 2 itself is excluded.

---

### 2.4 — Walrus Operator (Named Expression)

```python
# id: 11111111-1111-1111-1111-111111111104
# category: comprehensions
# title: Walrus Operator to Capture Repeated Function Call
# review_interval: 4

import re
if (m := re.search(r'\d+', data)) and (n := re.search(r'\d+', data[m.end():])):
    print(f"Found: {m.group()} and {n.group()}")
```

**annotations (JSON):**

```json
[
  {"line": 1, "text": "Import the regular expression module.", "type": "side_effect"},
  {"line": 2, "text": "Walrus captures re.search result into variable m; used in truth test and later.", "type": "assignment"},
  {"line": 2, "text": "Slice data starting after m's match end; second search runs on the remainder.", "type": "iterator"},
  {"line": 2, "text": "Walrus captures second search into n; both must be truthy for the block to run.", "type": "assignment"},
  {"line": 3, "text": "Both captures are in scope here — m.group() and n.group() refer to the captured expressions.", "type": "closure_var"}
]
```

**explanation:** The walrus operator `:=` assigns a value to a variable while returning it, enabling you to call `re.search` once and reuse its result without calling it twice. This avoids redundant computation and simplifies the conditional.

**common_mistakes:** Using walrus inside a comprehension filter that gets evaluated multiple times (each evaluation re-runs the assigned expression). Forgetting that walrus has lower precedence than almost everything — wrapping in parentheses is almost always needed.

---

### 2.5 — Generator Expression to Compute Sum

```python
# id: 11111111-1111-1111-1111-111111111105
# category: comprehensions
# title: Generator Expression vs List Comprehension for Large Data
# review_interval: 3

values = range(1_000_000)
list_sum   = sum([x for x in values if x % 3 == 0])
gen_sum    = sum(x for x in values if x % 3 == 0)
```

**annotations (JSON):**

```json
[
  {"line": 1, "text": "range(1_000_000) is a lazy iterator — no million-element list is allocated yet.", "type": "iterator"},
  {"line": 2, "text": "Square brackets force full materialization into a list before sum() receives it.", "type": "factory"},
  {"line": 2, "text": "sum() then iterates the materialized list to compute the total.", "type": "iterator"},
  {"line": 3, "text": "No brackets — this is a generator expression; sum() consumes it lazily, one element at a time.", "type": "iterator"},
  {"line": 3, "text": "Memory-efficient: only one integer exists in memory at any moment.", "type": "offload"}
]
```

**explanation:** List comprehensions eagerly build the entire list in memory before `sum()` can begin. Generator expressions are lazy — `sum()` pulls items one at a time as needed. For a million-element range, the generator version avoids allocating an 8 MB list.

**common_mistakes:** Using `sum([...])` (list comp) and being unaware of the intermediate list allocation. Passing a generator expression to a function that needs to iterate multiple times (it will be exhausted on the second pass).

---

### 2.6 — Chained Comparison with `is not None`

```python
# id: 11111111-1111-1111-1111-111111111201
# category: none_handling
# title: Chained Comparison with is not None
# review_interval: 3

def classify(value):
    if value is not None and 0 <= value <= 100:
        return "valid"
    return "invalid"
```

**annotations (JSON):**

```json
[
  {"line": 1, "text": "Define classify function taking one parameter 'value'.", "type": "function_call"},
  {"line": 2, "text": "Guard: check that value is not None before any comparison — prevents TypeError.", "type": "guard"},
  {"line": 2, "text": "Chained comparison: 0 <= value AND value <= 100, evaluated as a single boolean expression.", "type": "filter"},
  {"line": 3, "text": "Return 'valid' string if both conditions are True.", "type": "assignment"},
  {"line": 4, "text": "Return 'invalid' string for all other cases (None, out of range, non-numeric).", "type": "assignment"}
]
```

**explanation:** The chained comparison `0 <= value <= 100` is equivalent to `(0 <= value) and (value <= 100)` but is shorter and slightly faster. The `value is not None` guard must come first, or the chained comparison would raise a `TypeError` when `value` is `None`.

**common_mistakes:** Writing `if 0 <= value is not None <= 100:` due to misunderstanding operator precedence — this parses as `(0 <= value) and (value is not None) and (None <= 100)` which is almost always True and nonsensical. Using `!= None` instead of `is not None` (identity vs equality — None is a singleton, use identity).

---

### 2.7 — None Sentinel Default

```python
# id: 11111111-1111-1111-1111-111111111202
# category: none_handling
# title: Using None as Sentinel Value for Optional Parameters
# review_interval: 2

def find_user(users, role=None):
    if role is None:
        return users
    return [u for u in users if u.get("role") == role]
```

**annotations (JSON):**

```json
[
  {"line": 1, "text": "Define function with 'role' defaulting to None (sentinel value).", "type": "function_call"},
  {"line": 2, "text": "Guard check: if role was not provided, return the full list unchanged.", "type": "guard"},
  {"line": 3, "text": "Return full users list when role is None.", "type": "passthrough"},
  {"line": 4, "text": "List comprehension filters users to those whose role field matches.", "type": "iterator"}
]
```

**explanation:** `None` is used as a sentinel to distinguish "no filter provided" from "filter by empty string." Without this pattern, there is no way to differentiate between "return all users" and "return users with no role."

**common_mistakes:** Using a mutable default argument like `users=[]` (a classic Python pitfall — the list is shared across calls). Confusing the sentinel check `is None` with the value check `== None` (always use `is None` for identity comparison).

---

### 2.8 — Or Coalescing

```python
# id: 11111111-1111-1111-1111-111111111203
# category: none_handling
# title: Or Coalescing for Default Values
# review_interval: 2

def greet(name):
    display_name = name or "Anonymous"
    return f"Hello, {display_name}!"
```

**annotations (JSON):**

```json
[
  {"line": 1, "text": "Define greet function taking a name parameter.", "type": "function_call"},
  {"line": 2, "text": "Or coalescing: returns 'Anonymous' if name is falsy (None, '', 0, [], etc.).", "type": "coalesce"},
  {"line": 2, "text": "IMPORTANT: or coalescing treats ALL falsy values as missing, not just None.", "type": "guard"},
  {"line": 3, "text": "Build the formatted greeting string with the resolved display name.", "type": "function_call"}
]
```

**explanation:** `name or "Anonymous"` returns `"Anonymous"` whenever `name` is falsy — including `None`, `""`, `0`, `[]`, and `False`. This is convenient for optional strings but can mask real bugs when the value could legitimately be an empty string or zero.

**common_mistakes:** Using `or` to coalesce numeric defaults: `timeout or 30` — this breaks if `timeout = 0` is a valid value (0 is falsy, so it becomes 30). Prefer the explicit `timeout if timeout is not None else 30` or Python 3.10's `timeout ?? 30` (not yet available in CPython).

---

### 2.9 — Ternary None Check

```python
# id: 11111111-1111-1111-1111-111111111204
# category: none_handling
# title: Ternary Conditional for None/Value Branch
# review_interval: 2

def status_msg(records):
    count = len(records) if records is not None else 0
    return f"Found {count} record{'s' if count != 1 else ''}."
```

**annotations (JSON):**

```json
[
  {"line": 1, "text": "Define function taking records parameter.", "type": "function_call"},
  {"line": 2, "text": "Ternary: use len() if records is not None, otherwise default to 0.", "type": "ternary"},
  {"line": 2, "text": "Prevents TypeError from calling len(None).", "type": "guard"},
  {"line": 3, "text": "Pluralize 'record' only when count is not 1.", "type": "ternary"},
  {"line": 3, "text": "Return the formatted status message.", "type": "passthrough"}
]
```

**explanation:** The ternary conditional `x if condition else y` evaluates exactly one branch. `records if records is not None else 0` safely handles both `None` and empty lists while still getting the actual count for non-empty lists.

**common_mistakes:** Using `len(records or [])` instead of the ternary — this works for falsy values but loses information if records is legitimately an empty list (both become 0, which is fine here, but the ternary is clearer). Confusing the ternary syntax order — it is `value_if_true if condition else value_if_false`, not the C-style `condition ? true : false`.

---

### 2.10 — asyncio.gather

```python
# id: 11111111-1111-1111-1111-111111111301
# category: async_await
# title: Running Multiple Async Tasks Concurrently with asyncio.gather
# review_interval: 4

import asyncio

async def fetch(url):
    await asyncio.sleep(0.1)   # simulate network I/O
    return f"data from {url}"

async def main():
    urls = ["a.com", "b.com", "c.com"]
    results = await asyncio.gather(*[fetch(u) for u in urls])
    print(results)
```

**annotations (JSON):**

```json
[
  {"line": 1, "text": "Import the asyncio module for async/await support.", "type": "side_effect"},
  {"line": 3, "text": "Define an async function fetch — can be paused and resumed.", "type": "function_call"},
  {"line": 4, "text": "asyncio.sleep() yields control back to the event loop, simulating an I/O wait.", "type": "async_wait"},
  {"line": 6, "text": "Define the main async entry point.", "type": "function_call"},
  {"line": 7, "text": "Bind the list of URLs.", "type": "assignment"},
  {"line": 8, "text": "List comprehension creates three fetch coroutines — NOT yet executed.", "type": "iterator"},
  {"line": 8, "text": "* unpacks the list into separate arguments; gather schedules all coroutines concurrently.", "type": "executor"},
  {"line": 9, "text": "Print the list of results returned by all three coroutines.", "type": "side_effect"}
]
```

**explanation:** `asyncio.gather(*coroutines)` runs all passed coroutines concurrently on a single thread. The event loop interleaves their await points. This is dramatically faster than `await`-ing each one sequentially (0.3s sequential vs 0.1s concurrent here).

**common_mistakes:** Forgetting to `await` gather — the coroutines are created but never run, returning a list of coroutine objects instead of results. Passing coroutines directly vs. call expressions: `gather(fetch(u))` passes the coroutine object; `gather(*[fetch(u)])` actually calls each function.

---

### 2.11 — Async Context Manager

```python
# id: 11111111-1111-1111-1111-111111111302
# category: async_await
# title: Custom Async Context Manager with __aenter__ / __aexit__
# review_interval: 5

import asyncio

class AsyncDatabase:
    async def __aenter__(self):
        self.conn = await asyncio.to_thread(self._connect)
        return self

    async def __aexit__(self, *args):
        await asyncio.to_thread(self._close, self.conn)

    def _connect(self):
        return "db-connection-object"

    def _close(self, conn):
        pass  # close the connection

async def main():
    async with AsyncDatabase() as db:
        print(db.conn)
```

**annotations (JSON):**

```json
[
  {"line": 6, "text": "Define the async context manager class.", "type": "function_call"},
  {"line": 7, "text": "__aenter__ is called on entry to 'async with'; runs before the block body.", "type": "enter"},
  {"line": 8, "text": "to_thread runs the blocking _connect() in a thread pool, freeing the event loop.", "type": "executor"},
  {"line": 9, "text": "__aexit__ runs after the block body completes — always, even on exception.", "type": "exit"},
  {"line": 12, "text": "to_thread runs the blocking _close() asynchronously in a thread pool.", "type": "executor"},
  {"line": 17, "text": "async with invokes __aenter__, passing the returned value (self) to 'db'.", "type": "async_cm"},
  {"line": 18, "text": "Block body executes while the connection is open.", "type": "body"},
  {"line": 19, "text": "On exit from the block, __aexit__ is automatically called to clean up.", "type": "cleanup"}
]
```

**explanation:** `async with` is the async equivalent of `with`. Python calls `__aenter__` on entry and `__aexit__` on exit. Using `asyncio.to_thread` lets blocking I/O run without blocking the event loop.

**common_mistakes:** Forgetting to `await` the operations inside `__aenter`__ and `__aexit`__ (they are async methods). Raising an exception inside the `async with` block — `__aexit`__ still runs (the `*args` capture the exception info), but if it returns `True` the exception is suppressed.

---

### 2.12 — Blocking Code in Thread Pool Executor

```python
# id: 11111111-1111-1111-1111-111111111303
# category: async_await
# title: Offloading Blocking CPU Work with asyncio.to_thread
# review_interval: 4

import asyncio
import hashlib

def compute_hash(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()

async def main():
    data_chunks = ["chunk1", "chunk2", "chunk3"]
    hashes = await asyncio.gather(*[
        asyncio.to_thread(compute_hash, chunk) for chunk in data_chunks
    ])
    print(hashes)
```

**annotations (JSON):**

```json
[
  {"line": 1, "text": "Import asyncio for async concurrency primitives.", "type": "side_effect"},
  {"line": 2, "text": "Import hashlib for CPU-bound SHA-256 computation.", "type": "side_effect"},
  {"line": 4, "text": "Define a synchronous (blocking) CPU-bound function.", "type": "function_call"},
  {"line": 7, "text": "Define the async entry point.", "type": "function_call"},
  {"line": 8, "text": "Create the list of data chunks to hash.", "type": "assignment"},
  {"line": 9, "text": "to_thread wraps each compute_hash call, running it in a thread pool.", "type": "offload"},
  {"line": 9, "text": "gather runs all three thread-pool tasks concurrently.", "type": "executor"},
  {"line": 10, "text": "Print the resulting list of SHA-256 hex strings.", "type": "side_effect"}
]
```

**explanation:** CPU-bound work blocks the event loop if done directly inside async code. `asyncio.to_thread()` offloads the callable to a thread pool executor, allowing the event loop to continue running other async tasks while the CPU work happens in parallel.

**common_mistakes:** Calling a CPU-bound function directly inside async code without `to_thread` — this blocks the entire event loop, defeating the purpose of async. Over-serializing with `await` in a loop (`for chunk in chunks: result.append(await to_thread(...))`) instead of using `gather`.

---

### 2.13 — functools.wraps Decorator

```python
# id: 11111111-1111-1111-1111-111111111401
# category: decorators
# title: Preserving Function Metadata with functools.wraps
# review_interval: 4

import functools

def logged(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print(f"Calling {func.__name__}")
        return func(*args, **kwargs)
    return wrapper

@logged
def add(a, b):
    """Add two numbers and return the result."""
    return a + b
```

**annotations (JSON):**

```json
[
  {"line": 1, "text": "Import functools for the wraps utility.", "type": "side_effect"},
  {"line": 3, "text": "Define the decorator function taking the original function as its argument.", "type": "function_call"},
  {"line": 4, "text": "wraps copies __name__, __doc__, __module__, etc. from func to wrapper.", "type": "metadata_preservation"},
  {"line": 5, "text": "wrapper wraps func — *args and **kwargs forward all arguments transparently.", "type": "function_call"},
  {"line": 6, "text": "Side-effect: log the name of the function being called.", "type": "side_effect"},
  {"line": 7, "text": "Forward the actual call to the original function.", "type": "passthrough"},
  {"line": 8, "text": "Return the wrapper closure, which now replaces add.", "type": "assignment"},
  {"line": 10, "text": "Decorator syntax: Python calls logged(add) and rebinds 'add' to the result.", "type": "function_call"}
]
```

**explanation:** `functools.wraps(func)` inside the wrapper ensures that metadata like `__name__`, `__doc__`, and `__annotations__` are copied from the original function to the wrapper. Without it, introspection tools, debuggers, and decorators higher in the stack see the wrapper's metadata instead.

**common_mistakes:** Forgetting `functools.wraps` and then debugging a stack trace that shows `wrapper` instead of the real function name. Forgetting to `return` the wrapper from the decorator (the function silently becomes `None`).

---

### 2.14 — Double Wrapper with Arguments

```python
# id: 11111111-1111-1111-1111-111111111402
# category: decorators
# title: Decorator with Arguments — Triple Layer Closure
# review_interval: 5

import functools

def repeat(times):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            results = []
            for _ in range(times):
                results.append(func(*args, **kwargs))
            return results
        return wrapper
    return decorator

@repeat(times=3)
def greet(name):
    return f"Hello, {name}!"
```

**annotations (JSON):**

```json
[
  {"line": 1, "text": "Import functools for wraps.", "type": "side_effect"},
  {"line": 3, "text": "Outer closure: captures 'times' argument.", "type": "closure_var"},
  {"line": 4, "text": "Middle layer: receives the raw function being decorated.", "type": "function_call"},
  {"line": 5, "text": "wraps preserves the original function's metadata.", "type": "metadata_preservation"},
  {"line": 6, "text": "Inner wrapper: loop that calls func 'times' times, collecting all results.", "type": "iterator"},
  {"line": 7, "text": "Call func with the forwarded arguments, append result to list.", "type": "function_call"},
  {"line": 9, "text": "Return the wrapper closure.", "type": "assignment"},
  {"line": 11, "text": "Return the decorator (second layer), completing the chain.", "type": "assignment"},
  {"line": 13, "text": "Decorator syntax: repeat(3) returns decorator, which then receives greet.", "type": "function_call"}
]
```

**explanation:** A decorator with arguments requires three nested functions: the outer accepts the decorator arguments, the middle receives the function, and the inner is the actual wrapper. This is a "decorator factory" pattern.

**common_mistakes:** Writing `@repeat` instead of `@repeat(times=3)` (TypeError: repeat() missing required argument). Forgetting that `times` is captured from the outer scope (closure) — it is fixed at decoration time.

---

### 2.15 — Class-Based Decorator with `__call`__

```python
# id: 11111111-1111-1111-1111-111111111403
# category: decorators
# title: Class-Based Decorator Implementing __call__
# review_interval: 5

import functools

class CountCalls:
    def __init__(self, func):
        functools.wraps(func)(self)
        self._count = 0

    def __call__(self, *args, **kwargs):
        self._count += 1
        print(f"Called {self._count} time(s)")
        return self._func(*args, **kwargs)

@CountCalls
def add(a, b):
    return a + b
```

**annotations (JSON):**

```json
[
  {"line": 1, "text": "Import functools for wraps.", "type": "side_effect"},
  {"line": 3, "text": "Define the class-based decorator.", "type": "function_call"},
  {"line": 4, "text": "__init__ is called at decoration time; receives the function to wrap.", "type": "enter"},
  {"line": 5, "text": "wraps copies function metadata onto the CountCalls instance itself.", "type": "metadata_preservation"},
  {"line": 6, "text": "Initialize counter to 0.", "type": "assignment"},
  {"line": 8, "text": "__call__ is invoked each time the decorated function is called.", "type": "callable_sig"},
  {"line": 9, "text": "Increment counter on each invocation.", "type": "mutation"},
  {"line": 10, "text": "Print current call count.", "type": "side_effect"},
  {"line": 11, "text": "Forward the call to the wrapped function and return its result.", "type": "passthrough"}
]
```

**explanation:** A class-based decorator works by making the decorator instance callable. `__init__` receives the original function; `__call__` is invoked each time the decorated function is called. This pattern is useful when the decorator needs to maintain mutable state across calls.

**common_mistakes:** Forgetting to store `func` as `self._func` in `__init`__ (it gets overwritten). Forgetting `functools.wraps` in the class — the decorated function loses its original name and docstring. Mutating shared state without thread safety considerations.

---

### 2.16 — ABC with `abstractmethod`

```python
# id: 11111111-1111-1111-1111-111111111501
# category: oop
# title: Abstract Base Class with Abstract Method Enforcement
# review_interval: 5

from abc import ABC, abstractmethod

class Animal(ABC):
    @abstractmethod
    def speak(self) -> str:
        raise NotImplementedError

class Dog(Animal):
    def speak(self) -> str:
        return "Woof!"

class Cat(Animal):
    pass  # forgot to implement speak — TypeError on instantiation
```

**annotations (JSON):**

```json
[
  {"line": 1, "text": "Import ABC and abstractmethod from the abc module.", "type": "side_effect"},
  {"line": 3, "text": "Define Animal as an abstract base class.", "type": "abc"},
  {"line": 4, "text": "@abstractmethod marks speak() as required — subclasses MUST implement it.", "type": "enforcement"},
  {"line": 5, "text": "The body raises NotImplementedError if called directly (should never be called).", "type": "rollback"},
  {"line": 7, "text": "Dog inherits from Animal and implements speak().", "type": "contract"},
  {"line": 9, "text": "Cat inherits from Animal but fails to implement speak().", "type": "contract"},
  {"line": 10, "text": "TypeError raised at instantiation time, not at definition time.", "type": "validation"}
]
```

**explanation:** `ABC` and `@abstractmethod` enforce a contract: any subclass of `Animal` must implement `speak()`. Python raises `TypeError` at instantiation time if the abstract method is not overridden. This is compile-time-like enforcement in a dynamically-typed language.

**common_mistakes:** Instantiating a subclass that forgot to implement the abstract method (raises `TypeError` at instantiation, not definition — can be confusing). Calling `super().speak()` in the subclass before implementing it (same result). Confusing `ABC` with `Protocol` from typing — `ABC` requires inheritance; `Protocol` is for structural subtyping.

---

### 2.17 — Dataclass with `__post_init`__

```python
# id: 11111111-1111-1111-1111-111111111502
# category: oop
# title: Dataclass with __post_init__ for Derived Fields
# review_interval: 4

from dataclasses import dataclass, field

@dataclass
class Rectangle:
    width:  int
    height: int
    area:   int = field(init=False)

    def __post_init__(self):
        object.__setattr__(self, "area", self.width * self.height)

r = Rectangle(width=10, height=5)
print(r.area)  # 50
```

**annotations (JSON):**

```json
[
  {"line": 1, "text": "Import dataclass decorator and field from dataclasses.", "type": "side_effect"},
  {"line": 4, "text": "@dataclass generates __init__, __repr__, __eq__, __hash__ automatically.", "type": "factory"},
  {"line": 5, "text": "Define width and height as required fields.", "type": "parameterized"},
  {"line": 6, "text": "area is declared with init=False — it is not a constructor parameter.", "type": "parameterized"},
  {"line": 8, "text": "__post_init__ runs after the generated __init__ but before the object is returned.", "type": "init"},
  {"line": 9, "text": "object.__setattr__ bypasses dataclass field immutability check to set area.", "type": "mutation"}
]
```

**explanation:** `@dataclass` generates boilerplate `__init__`, `__repr__`, `__eq__` automatically. `__post_init__` runs after `__init__` and lets you compute derived fields. Using `object.__setattr__` is necessary because dataclasses make fields immutable by default when `frozen=True` is set, and `field(init=False)` fields still go through the immutability machinery.

**common_mistakes:** Trying to assign to `self.area = ...` inside `__post_init`__ when `frozen=True` — must use `object.__setattr`_*. Declaring `area: int` as a regular field (not `init=False`) and then overwriting it in `__post_init_`*, which can confuse type checkers.

---

### 2.18 — Mixin Pattern

```python
# id: 11111111-1111-1111-1111-111111111503
# category: oop
# title: Mixin Class for Reusable Cross-Cutting Behavior
# review_interval: 5

class LoggedMixin:
    def log(self, msg: str) -> None:
        print(f"[LOG] {msg}")

class Service(LoggedMixin):
    def run(self) -> None:
        self.log("Service started")
        print("Doing work...")
        self.log("Service done")

class Tool(LoggedMixin):
    def execute(self) -> None:
        self.log("Tool executing")
```

**annotations (JSON):**

```json
[
  {"line": 1, "text": "Define the mixin — provides log() to any class that inherits it.", "type": "mixin"},
  {"line": 2, "text": "Mixin method for logging messages.", "type": "function_call"},
  {"line": 4, "text": "Service inherits from LoggedMixin — gets log() for free.", "type": "mixin_usage"},
  {"line": 5, "text": "Service defines its own run() method.", "type": "function_call"},
  {"line": 6, "text": "Mixin method called within Service's method.", "type": "self_reflection"},
  {"line": 10, "text": "Tool also uses the same mixin — DRY: log() is defined only once.", "type": "mixin_usage"}
]
```

**explanation:** A mixin is a class that provides methods to other classes through multiple inheritance, without being intended to stand alone. It encapsulates cross-cutting behavior (like logging) that multiple unrelated classes share. Python's method resolution order (MRO) determines which version of a method wins if multiple mixins define the same method.

**common_mistakes:** Forgetting that mixins should not call `super().__init__()` unless they are designed to cooperate with the MRO (causes duplicate or missing initialization). Defining `__init`__ in a mixin (this is the mixin's job, not the mixin's — mixins should only add methods). Creating circular inheritance between mixins.

---

### 2.19 — Callable Type Hint

```python
# id: 11111111-1111-1111-1111-111111111601
# category: type_hints
# title: Callable Type Hint for Callback Parameters
# review_interval: 4

from typing import Callable

def apply_twice(func: Callable[[int], int], value: int) -> int:
    return func(func(value))

def add_five(x: int) -> int:
    return x + 5

result = apply_twice(add_five, 0)  # (0+5)+5 = 10
```

**annotations (JSON):**

```json
[
  {"line": 1, "text": "Import Callable from typing for higher-order function type hints.", "type": "side_effect"},
  {"line": 3, "text": "Define apply_twice: takes a callable (int -> int) and an int, returns int.", "type": "function_call"},
  {"line": 3, "text": "Callable[[int], int] means: accepts one int argument, returns an int.", "type": "callable_sig"},
  {"line": 4, "text": "Call func twice: inner call with value, outer call with the result.", "type": "nested_call"},
  {"line": 6, "text": "Define add_five as a concrete implementation of Callable[[int], int].", "type": "function_call"},
  {"line": 8, "text": "apply_twice(add_five, 0): first add_five(0)=5, then add_five(5)=10.", "type": "nested_call"}
]
```

**explanation:** `Callable[[ArgType, ...], ReturnType]` is the standard way to annotate functions that accept other functions as arguments (callbacks, higher-order functions). The list inside `Callable` describes the argument types the callable must accept; the final type is the return type.

**common_mistakes:** Writing `Callable[int, int]` instead of `Callable[[int], int]` — the outer brackets are required (Callable takes two type arguments: a list of inputs and the output). Forgetting that `Callable[..., R]` with `...` means "any arguments" — the ellipsis is a valid type, not a placeholder.

---

### 2.20 — TypeVar + Generic

```python
# id: 11111111-1111-1111-1111-111111111602
# category: type_hints
# title: Generic Type Variable for Type-Safe Container Operations
# review_interval: 5

from typing import TypeVar, Generic

T = TypeVar("T")

class Stack(Generic[T]):
    def __init__(self) -> None:
        self._items: list[T] = []

    def push(self, item: T) -> None:
        self._items.append(item)

    def pop(self) -> T:
        return self._items.pop()

nums: Stack[int] = Stack()
nums.push(42)
value: int = nums.pop()
```

**annotations (JSON):**

```json
[
  {"line": 1, "text": "Import TypeVar for generic type variables and Generic for generic classes.", "type": "side_effect"},
  {"line": 3, "text": "T is an unconstrained TypeVar — can be bound to any type.", "type": "typevar"},
  {"line": 5, "text": "Stack is parameterized over T — each instantiation fixes T to a concrete type.", "type": "parameterized"},
  {"line": 8, "text": "push accepts an item of type T (determined by how the Stack was instantiated).", "type": "parameterized"},
  {"line": 11, "text": "pop returns a T — type checker enforces that callers use the returned value correctly.", "type": "generic_class"},
  {"line": 13, "text": "Instantiate Stack bound to int — all T positions become int.", "type": "generic_class"},
  {"line": 14, "text": "push(42) is type-correct: int is valid for Stack[int].", "type": "validation"},
  {"line": 15, "text": "Assigning pop() result to int; type checker confirms T=int at this instantiation.", "type": "validation"}
]
```

**explanation:** `TypeVar` and `Generic` enable parametric polymorphism in Python's type system. When you write `Stack[int]`, the type checker enforces that all `T` positions in the class are treated as `int`. This catches errors at type-checking time rather than at runtime.

**common_mistakes:** Instantiating `Stack()` without a type parameter (becomes `Stack[Any]`, losing all type safety). Forgetting that `list[T]` inside the class needs the same type variable (`list` is also generic in Python 3.9+). Using unconstrained TypeVars where a bound would provide better errors (`T = TypeVar("T", bound=BaseClass)`).

---

### 2.21 — `@contextmanager` Cleanup Pattern

```python
# id: 11111111-1111-1111-1111-111111111701
# category: context_managers
# title: @contextmanager Decorator for Automatic Resource Cleanup
# review_interval: 3

from contextlib import contextmanager

@contextmanager
def managed_file(path, mode="r"):
    f = open(path, mode)
    try:
        yield f
    finally:
        f.close()

with managed_file("data.txt") as fh:
    print(fh.read())
```

**annotations (JSON):**

```json
[
  {"line": 1, "text": "Import contextmanager from contextlib.", "type": "side_effect"},
  {"line": 3, "text": "@contextmanager transforms a generator into a context manager.", "type": "factory"},
  {"line": 4, "text": "Generator sets up the resource (opens the file).", "type": "enter"},
  {"line": 5, "text": "open() acquires the file handle.", "type": "side_effect"},
  {"line": 6, "text": "try block: yield passes control to the with-block body, returning fh.", "type": "yield"},
  {"line": 8, "text": "finally block: ALWAYS runs, even if an exception occurs — ensures cleanup.", "type": "cleanup"},
  {"line": 9, "text": "Close the file handle, releasing the OS resource.", "type": "cleanup"},
  {"line": 11, "text": "with assigns fh from the yield value; reads file while it is open.", "type": "body"},
  {"line": 12, "text": "On exiting the with block, the finally block runs — file is guaranteed closed.", "type": "exit"}
]
```

**explanation:** `@contextmanager` turns a generator function into a context manager. The code before `yield` runs on `__aenter__` (entry); the code after `yield` in the `finally` block runs on `__aexit__` (exit). This avoids writing a full class with `__enter__` and `__aexit__` for simple resource management.

**common_mistakes:** Forgetting the `finally` block — if the `with` body raises an exception, the file handle leaks. Relying on `except` instead of `finally` (exceptions are re-raised after the finally block runs, so a bare `except` silently swallows them). Using `yield` outside of a `try/finally` entirely.

---

### 2.22 — Transaction Rollback

```python
# id: 11111111-1111-1111-1111-111111111702
# category: context_managers
# title: Context Manager for Database Transaction with Rollback
# review_interval: 5

class Transaction:
    def __init__(self, conn):
        self.conn = conn
        self._committed = False

    def __enter__(self):
        self.conn.execute("BEGIN")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.conn.execute("ROLLBACK")
            return False  # re-raise the exception
        self.conn.execute("COMMIT")
        self._committed = True
        return False

with Transaction(conn) as tx:
    tx.conn.execute("UPDATE accounts SET balance = balance - 100")
    tx.conn.execute("UPDATE accounts SET balance = balance + 100")
```

**annotations (JSON):**

```json
[
  {"line": 1, "text": "Define the Transaction context manager class.", "type": "function_call"},
  {"line": 3, "text": "__enter__: begins the database transaction.", "type": "begin"},
  {"line": 8, "text": "__exit__ is called when leaving the with block.", "type": "exit"},
  {"line": 9, "text": "If an exception occurred: execute ROLLBACK to undo all changes in this transaction.", "type": "rollback"},
  {"line": 10, "text": "Return False so the exception is re-raised to the caller.", "type": "rollback"},
  {"line": 12, "text": "No exception: commit makes all changes permanent.", "type": "commit"},
  {"line": 14, "text": "Return False to not suppress any exception.", "type": "exit"},
  {"line": 16, "text": "Two UPDATE statements run atomically within the transaction.", "type": "executor"}
]
```

**explanation:** The transaction context manager ensures atomicity: either both UPDATE statements succeed and are committed, or an exception causes a rollback. The `return False` from `__exit__` does NOT suppress the exception — it is required to re-raise it (omitting `return False` or returning `True` would suppress the exception, hiding bugs).

**common_mistakes:** Returning `True` from `__exit`__ to suppress the exception (hides bugs — callers never know the operation failed). Forgetting to issue `ROLLBACK` in the exception branch (partial changes persist). Using this pattern without a database that actually supports transactions.

---

### 2.23 — Async `__aenter`__ / `__aexit`__

```python
# id: 11111111-1111-1111-1111-111111111703
# category: context_managers
# title: Async Context Manager for Network Connection Pool
# review_interval: 5

import asyncio

class AsyncPool:
    async def __aenter__(self):
        self.connections = await asyncio.Queue()
        for _ in range(5):
            await self.connections.put("conn-object")
        return self

    async def __aexit__(self, *args):
        while not self.connections.empty():
            conn = await self.connections.get()
            await conn.close()

async def main():
    async with AsyncPool() as pool:
        conn = await pool.connections.get()
        await conn.query("SELECT 1")
        await pool.connections.put(conn)
```

**annotations (JSON):**

```json
[
  {"line": 1, "text": "Import asyncio for async/await support.", "type": "side_effect"},
  {"line": 3, "text": "Define the async context manager class.", "type": "function_call"},
  {"line": 4, "text": "__aenter__ runs on entry; initializes the connection pool.", "type": "enter"},
  {"line": 5, "text": "Create an async queue to hold pooled connection objects.", "type": "factory"},
  {"line": 6, "text": "Pre-populate the pool with 5 connection objects.", "type": "iterator"},
  {"line": 7, "text": "Return self to be bound in the 'as pool' clause.", "type": "passthrough"},
  {"line": 9, "text": "__aexit__ runs on exit; drains and closes all connections.", "type": "exit"},
  {"line": 10, "text": "Loop until the pool is empty.", "type": "iterator"},
  {"line": 11, "text": "Get and close each connection in turn.", "type": "cleanup"}
]
```

**explanation:** Async context managers are needed when the entry or exit requires async operations (like network I/O). The `async with` statement awaits both `__aenter__` and `__aexit__`. Using an `asyncio.Queue` for the pool allows concurrent access to pooled connections.

**common_mistakes:** Using `with` instead of `async with` (TypeError). Forgetting to `await` operations inside `__aenter`__ and `__aexit`_*. Not handling exceptions properly in `__aexit_`* — always re-raise unless you intentionally want to suppress.

---

### 2.24 — Nonlocal Counter Closure

```python
# id: 11111111-1111-1111-1111-111111111801
# category: closures
# title: Nonlocal Variable Capture in a Counter Closure
# review_interval: 3

def make_counter(start=0):
    count = start

    def increment(delta=1):
        nonlocal count
        count += delta
        return count

    return increment

counter = make_counter(10)
print(counter())    # 11
print(counter(5))  # 16
print(counter(-2)) # 14
```

**annotations (JSON):**

```json
[
  {"line": 1, "text": "Define factory function that creates a counter closure.", "type": "function_call"},
  {"line": 2, "text": "Initialize count in the enclosing scope — captured by the inner function.", "type": "closure_var"},
  {"line": 3, "text": "Define the inner increment function.", "type": "function_call"},
  {"line": 5, "text": "nonlocal declares count as mutable from the enclosing scope.", "type": "nonlocal"},
  {"line": 6, "text": "Assign to count: increments it by delta in the enclosing scope.", "type": "mutation"},
  {"line": 7, "text": "Return the updated count.", "type": "passthrough"},
  {"line": 9, "text": "Factory creates one closure instance with count=10.", "type": "factory"},
  {"line": 10, "text": "First call: count becomes 10+1=11.", "type": "mutation"},
  {"line": 11, "text": "Second call: count becomes 11+5=16.", "type": "mutation"}
]
```

**explanation:** `nonlocal count` tells Python to look up `count` in the enclosing (non-global, non-local) scope rather than creating a new local variable. Without `nonlocal`, the assignment `count += delta` would create a new local variable, shadowing the outer one and raising `UnboundLocalError` when the inner function tries to read it before assignment.

**common_mistakes:** Forgetting `nonlocal` and getting `UnboundLocalError: local variable 'count' referenced before assignment` — Python sees the assignment and treats `count` as local throughout the function, but then tries to read it before assigning. Using this pattern with mutable values (lists, dicts) where `nonlocal` is not needed but confusion arises about what is shared.

---

### 2.25 — `functools.partial` Factory

```python
# id: 11111111-1111-1111-1111-111111111802
# category: closures
# title: functools.partial for Partial Function Application
# review_interval: 3

from functools import partial

def power(base, exponent):
    return base ** exponent

square = partial(power, exponent=2)
cube   = partial(power, exponent=3)

print(square(5))  # 25
print(cube(5))   # 125
```

**annotations (JSON):**

```json
[
  {"line": 1, "text": "Import partial from functools.", "type": "side_effect"},
  {"line": 3, "text": "Define the power function: takes base and exponent, returns base ** exponent.", "type": "function_call"},
  {"line": 5, "text": "partial creates a new callable with exponent=2 pre-bound.", "type": "partial"},
  {"line": 6, "text": "partial creates a new callable with exponent=3 pre-bound.", "type": "partial"},
  {"line": 8, "text": "square(5) calls power(5, exponent=2) = 5**2 = 25.", "type": "function_call"},
  {"line": 9, "text": "cube(5) calls power(5, exponent=3) = 5**3 = 125.", "type": "function_call"}
]
```

**explanation:** `functools.partial` creates a new callable (a partial function) with some arguments pre-filled. It is a factory function that returns a callable object. This is cleaner than defining wrapper functions manually and avoids the overhead of a full closure when only argument binding is needed.

**common_mistakes:** Confusing `partial(power, exponent=2)` with `partial(power, 2)` — the latter binds `base=2`, not `exponent=2` (positional argument binding). Passing mutable objects as defaults to partial (the partial object stores them by reference; modifications affect the partial). Forgetting that partial is not memoization — it does not cache results.

---

## 3. Database Migration

File: `backend/migrations/V002__examples_table.sql`

```sql
-- ============================================================
-- CodeScope Database Migration
-- V002: Examples Table for Educational Code Snippets
-- ============================================================

CREATE TABLE IF NOT EXISTS examples (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category         TEXT NOT NULL,
    title            TEXT NOT NULL,
    code             TEXT NOT NULL,
    why_ai_generates_this TEXT,
    annotations      JSONB NOT NULL DEFAULT '[]',
    explanation      TEXT NOT NULL,
    common_mistakes  TEXT[] NOT NULL DEFAULT '{}',
    review_interval  INT NOT NULL DEFAULT 1 CHECK (review_interval >= 1),
    created_at       TIMESTAMPTZ DEFAULT now(),
    updated_at       TIMESTAMPTZ DEFAULT now()
);

-- Indexes for efficient browsing and lookup
CREATE INDEX IF NOT EXISTS idx_examples_category ON examples(category);
CREATE INDEX IF NOT EXISTS idx_examples_title   ON examples(title);

-- ============================================================
-- Row Level Security
-- ============================================================
ALTER TABLE examples ENABLE ROW LEVEL SECURITY;

-- Examples are publicly readable (browse page is free for all users)
CREATE POLICY "public_read_examples" ON examples
    FOR SELECT USING (true);

-- Writes to examples table are admin-only (service role key bypasses RLS)
-- INSERT, UPDATE, DELETE are intentionally not exposed to anon key.

-- ============================================================
-- Trigger: auto-update updated_at on row change
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_examples_updated_at
    BEFORE UPDATE ON examples
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

---

## 4. Backend Router — `examples.py`

File: `backend/app/routers/examples.py`

```python
"""
Examples router — browse and save curated educational code examples.

Public endpoints:
  GET  /api/examples              — list all examples (filterable, paginated)
  GET  /api/examples/{id}        — get a single example with annotations

Authenticated + Pro endpoints:
  POST /api/examples/{id}/save   — add to user's review queue
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Header, Query, Request
from pydantic import BaseModel, Field

from app.config import Settings
from app.routers.auth import get_current_user, get_profile_id

logger = logging.getLogger("codescope.examples")

router = APIRouter()

    # ── Rate Limiter ─────────────────────────────────────────────────

    We use `slowapi` for endpoint rate limiting.
    - GET /examples: 60 requests/minute (public, cheap query)
    - POST /examples/{id}/save: 10 requests/minute (auth-gated, writes DB)

try:
    from slowapi import Limiter
    from slowapi.util import get_remote_address

    _limiter = Limiter(key_func=get_remote_address)
except ImportError:
    _limiter = None


def _get_limiter():
    if _limiter is None:
        raise RuntimeError(
            "slowapi is not installed. Run: pip install slowapi"
        )
    return _limiter


# ── Annotation / Example Types ───────────────────────────────────

class Annotation(BaseModel):
    line: int = Field(..., ge=1, description="1-indexed line number in the snippet")
    text: str = Field(..., description="Plain-text explanation of what happens on this line")
    type: str = Field(
        ...,
        description=(
            "One of: scope | filter | iterator | guard | assignment | function_call | "
            "passthrough | side_effect | async_cm | executor | offload | yield | body | "
            "cleanup | metadata_preservation | enforcement | validation | rollback | "
            "commit | begin | nonlocal | mutation | partial | factory | typevar | "
            "parameterized | generic_class | callable_sig | nested_call | coalesce | "
            "ternary | sentinel | default | config_layer | func_layer | execution_layer | "
            "init | callable_layer | abc | contract | boilerplate | mutable_default | "
            "mixin | mixin_usage | self_reflection | enter | exit | timing | async_wait | "
            "closure_var | dedup | range_check"
        ),
    )


class ExampleRecord(BaseModel):
    model_config = {"extra": "ignore"}

    id: str
    category: str
    title: str
    code: str
    why_ai_generates_this: Optional[str] = None
    annotations: list[Annotation] = []
    explanation: str
    common_mistakes: list[str] = []
    review_interval: int = 1


class ExampleListResponse(BaseModel):
    examples: list[ExampleRecord]
    total: int
    limit: int
    offset: int


# ── Save to Review Queue ──────────────────────────────────────────

class SaveExampleRequest(BaseModel):
    notes: Optional[str] = Field(None, max_length=500, description="Optional user notes")


class SaveExampleResponse(BaseModel):
    card_id: str
    message: str
    existing: bool = False


# ── Internal Helpers ─────────────────────────────────────────────

def _parse_annotations(raw: list | dict | str) -> list[Annotation]:
    """Parse the annotations field from Supabase (JSONB deserializes to list or dict)."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return []
    if not isinstance(raw, list):
        return []
    return [Annotation(**a) if isinstance(a, dict) else Annotation(**json.loads(a) if isinstance(a, str) else a) for a in raw]


async def _fetch_profile(authorization: str, user_id: str) -> dict:
    """Fetch the user's profile to check plan status."""
    settings = Settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/profiles",
            params={"user_id": f"eq.{user_id}", "select": "*"},
            headers={
                "Authorization": f"Bearer {authorization}",
                "apikey": settings.supabase_service_key,
            },
        )
    if resp.status_code == 200:
        profiles = resp.json()
        if profiles:
            return profiles[0]
    return {}


async def _get_or_create_trace(
    settings: Settings,
    authorization: str,
    user_id: str,
    profile_id: str,
    example: ExampleRecord,
) -> str:
    """Create a trace record for this example (or find existing one)."""
    import secrets

    trace_data = {
        "user_id": profile_id,
        "code": example.code,
        "language": "python",
        "is_public": False,
        "share_token": secrets.token_hex(16),
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.supabase_url}/rest/v1/traces",
            headers={
                "Authorization": f"Bearer {settings.supabase_service_key}",
                "apikey": settings.supabase_service_key,
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            json=trace_data,
        )

    if resp.status_code not in (200, 201):
        logger.error("Failed to create trace: %s", resp.text)
        raise HTTPException(status_code=502, detail="Failed to create trace record")

    data = resp.json()
    if isinstance(data, list):
        data = data[0]
    return data["id"]


async def _check_existing_card(
    settings: Settings,
    authorization: str,
    user_id: str,
    profile_id: str,
    example_id: str,
) -> Optional[str]:
    """
    Check if the user already has a review_card for this example.
    The concept_tag encodes the example_id as a prefix: "example:{id}:{first_tag}".
    """
    concept_prefix = f"example:{example_id}:"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/review_cards",
            params={
                "user_id": f"eq.{profile_id}",
                "concept_tag": f"like.{concept_prefix}%",
                "select": "id,concept_tag",
                "limit": "1",
            },
            headers={
                "Authorization": f"Bearer {authorization}",
                "apikey": settings.supabase_service_key,
            },
        )

    if resp.status_code == 200:
        cards = resp.json()
        if cards and len(cards) > 0:
            return cards[0]["id"]
    return None


async def _create_review_card(
    settings: Settings,
    authorization: str,
    profile_id: str,
    trace_id: str,
    example: ExampleRecord,
) -> str:
    """Create a new review_card with SM-2 initial values."""
    import secrets

    today = date.today().isoformat()
    concept_tag = f"example:{example.id}:{example.category}"

    card_data = {
        "user_id": profile_id,
        "trace_id": trace_id,
        "concept_tag": concept_tag,
        "easiness_factor": 2.5,
        "interval_days": example.review_interval,
        "repetitions": 0,
        "next_review_date": today,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.supabase_url}/rest/v1/review_cards",
            headers={
                "Authorization": f"Bearer {settings.supabase_service_key}",
                "apikey": settings.supabase_service_key,
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            },
            json=card_data,
        )

    if resp.status_code not in (200, 201):
        logger.error("Failed to create review card: %s", resp.text)
        raise HTTPException(status_code=502, detail="Failed to create review card")

    data = resp.json()
    if isinstance(data, list):
        data = data[0]
    return data["id"]


# ── Endpoints ────────────────────────────────────────────────────

@_get_limiter().limit("60/minute")
@router.get("/examples", response_model=ExampleListResponse)
async def list_examples(
    request: Request,
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(20, ge=1, le=50, description="Results per page"),
    offset: int = Query(0, ge=0, description="Skip N results"),
):
    """
    List all examples, optionally filtered by category.

    Public: no authentication required.

    Response includes `total` count for pagination UI.
    Rate limit: 60 requests/minute per IP (via slowapi).
    """

    settings = Settings()

    # Build main query params (fetches limited rows for display)
    params: dict[str, str] = {
        "select": "*",
        "limit": str(limit),
        "offset": str(offset),
        "order": "created_at.asc",
    }

    # Build count query params (fetches minimal data, just for total count)
    count_params: dict[str, str] = {
        "select": "id",  # minimal select keeps payload tiny
    }

    if category:
        params["category"] = f"eq.{category}"
        count_params["category"] = f"eq.{category}"

    headers = {
        "apikey": settings.supabase_service_key,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/examples",
            params=params,
            headers=headers,
        )

    if resp.status_code != 200:
        logger.error("Failed to fetch examples: %s", resp.text)
        raise HTTPException(status_code=502, detail="Failed to fetch examples from database")

    rows = resp.json() or []

    # Parse annotations for each row
    examples = []
    for row in rows:
        raw_annotations = row.get("annotations", [])
        annotations = _parse_annotations(raw_annotations)
        examples.append(
            ExampleRecord(
                id=str(row["id"]),
                category=row.get("category", ""),
                title=row.get("title", ""),
                code=row.get("code", ""),
                why_ai_generates_this=row.get("why_ai_generates_this"),
                annotations=annotations,
                explanation=row.get("explanation", ""),
                common_mistakes=row.get("common_mistakes") or [],
                review_interval=row.get("review_interval", 1),
            )
        )

    # Fetch total count for pagination using Supabase headers-only request
    # Avoids fetching all rows just to count them
    async with httpx.AsyncClient(timeout=10.0) as client:
        count_resp = await client.get(
            f"{settings.supabase_url}/rest/v1/examples",
            params=count_params,
            headers={
                **headers,
                "Prefer": "count=exact",
            },
        )

    total = 0
    if count_resp.status_code == 200:
        # Supabase returns total count in the 'content-range' header: "0-0/42"
        content_range = count_resp.headers.get("content-range", "")
        if "/" in content_range:
            try:
                total = int(content_range.split("/")[-1])
            except ValueError:
                total = len(resp.json() or [])  # fallback

    return ExampleListResponse(
        examples=examples,
        total=total,
        limit=limit,
        offset=offset,
    )


@_get_limiter().limit("60/minute")
@router.get("/examples/{example_id}", response_model=ExampleRecord)
async def get_example(request: Request, example_id: str):
    """
    Get a single example by ID, including all annotations.

    Public: no authentication required.
    Returns 404 if the example does not exist.
    Rate limit: 60 requests/minute per IP (via slowapi).
    """
    settings = Settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/examples",
            params={"id": f"eq.{example_id}", "select": "*", "limit": "1"},
            headers={"apikey": settings.supabase_service_key},
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch example")

    rows = resp.json() or []
    if not rows:
        raise HTTPException(status_code=404, detail="Example not found")

    row = rows[0]
    raw_annotations = row.get("annotations", [])
    annotations = _parse_annotations(raw_annotations)

    return ExampleRecord(
        id=str(row["id"]),
        category=row.get("category", ""),
        title=row.get("title", ""),
        code=row.get("code", ""),
        why_ai_generates_this=row.get("why_ai_generates_this"),
        annotations=annotations,
        explanation=row.get("explanation", ""),
        common_mistakes=row.get("common_mistakes") or [],
        review_interval=row.get("review_interval", 1),
    )


@_get_limiter().limit("10/minute")
@router.post("/examples/{example_id}/save", response_model=SaveExampleResponse)
async def save_example_to_queue(
    example_id: str,
    req: Optional[SaveExampleRequest] = None,
    authorization: str = Header(None),
):
    """
    Add an example to the authenticated user's spaced-repetition review queue.

    Auth: Required (must be logged in)
    Plan: Requires Pro plan (free users receive 403)

    Deduplication: If the user already has a review_card for this example,
    returns HTTP 200 with the existing card_id (no duplicate created).

    Returns:
      201 — new card created
      200 — existing card returned (deduplication)
      401 — not authenticated
      403 — free plan (upgrade required)
      404 — example not found
    """
    # ── Auth check ──────────────────────────────────────────────
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")

    user = await get_current_user(authorization)
    user_id = user.get("id", "")
    settings = Settings()

    # ── Fetch profile for plan check ────────────────────────────
    profile = await _fetch_profile(authorization, user_id)
    if profile.get("plan") != "pro":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "UPGRADE_REQUIRED",
                "message": "This feature requires a Pro subscription.",
                "upgrade_url": "/upgrade",
            },
        )

    profile_id = await get_profile_id(authorization)
    if not profile_id:
        raise HTTPException(status_code=404, detail="Profile not found for user")

    # ── Fetch the example ────────────────────────────────────────
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/examples",
            params={"id": f"eq.{example_id}", "select": "*", "limit": "1"},
            headers={"apikey": settings.supabase_service_key},
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch example")

    rows = resp.json() or []
    if not rows:
        raise HTTPException(status_code=404, detail="Example not found")

    row = rows[0]
    raw_annotations = row.get("annotations", [])
    example = ExampleRecord(
        id=str(row["id"]),
        category=row.get("category", ""),
        title=row.get("title", ""),
        code=row.get("code", ""),
        why_ai_generates_this=row.get("why_ai_generates_this"),
        annotations=_parse_annotations(raw_annotations),
        explanation=row.get("explanation", ""),
        common_mistakes=row.get("common_mistakes") or [],
        review_interval=row.get("review_interval", 1),
    )

    # ── Deduplication check ──────────────────────────────────────
    existing_card_id = await _check_existing_card(
        settings, authorization, user_id, profile_id, example_id
    )
    if existing_card_id:
        return SaveExampleResponse(
            card_id=existing_card_id,
            message="Already in your review queue",
            existing=True,
        )

    # ── Create trace + review_card ────────────────────────────────
    trace_id = await _get_or_create_trace(
        settings, authorization, user_id, profile_id, example
    )
    card_id = await _create_review_card(
        settings, authorization, profile_id, trace_id, example
    )

    logger.info(
        "example_saved",
        extra={
            "card_id": card_id,
            "example_id": example_id,
            "user_id": user_id,
        },
    )

    return SaveExampleResponse(
        card_id=card_id,
        message="Added to your review queue",
        existing=False,
    )
```

---

## 5. Router Registration in `main.py`

Add the import and `include_router` call to `backend/app/main.py`.

```diff
--- a/backend/app/main.py
+++ b/backend/app/main.py
@@ -3,7 +3,7 @@ from fastapi import FastAPI
 from fastapi.middleware.cors import CORSMiddleware

-from app.routers import traces, llm, review, profiles, static_analysis
+from app.routers import traces, llm, review, profiles, static_analysis, examples
 
 app = FastAPI(
     title="CodeScope API",
@@ -29,6 +29,7 @@ app.include_router(profiles.router, prefix="/profiles")
 app.include_router(static_analysis.router, prefix="/api")
+app.include_router(examples.router, prefix="/api")
 
 app.add_middleware(
     CORSMiddleware,
```

> **Note:** `examples.router` uses `from slowapi import Limiter`. Add `slowapi` to `requirements.txt` if not already present:
>
> ```
> slowapi>=0.9.0
> ```

---

## 6. Backend Tests — `test_examples.py`

File: `backend/tests/unit/test_examples.py`

```python
"""
Unit tests for the /api/examples endpoints.
Covers: list, filter, pagination, detail, save (auth, dedup, plan check).
"""
from __future__ import annotations

import json
import uuid
from datetime import date
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app

# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_supabase_response():
    """Factory for a mock httpx response with known example data."""
    def _make(rows: list[dict], status_code: int = 200):
        response = MagicMock()
        response.status_code = status_code
        response.json.return_value = rows
        return response
    return _make


@pytest.fixture
def sample_example_row():
    return {
        "id": str(uuid.uuid4()),
        "category": "comprehensions",
        "title": "Nested List Comprehension",
        "code": "evens = [x for row in [[1,2,3],[4,5,6]] for x in row if x % 2 == 0]",
        "why_ai_generates_this": "AI uses this to show flattening + filtering in one expression.",
        "annotations": json.dumps([
            {"line": 1, "text": "Outer iterator.", "type": "iterator"},
            {"line": 1, "text": "Inner iterator.", "type": "iterator"},
            {"line": 1, "text": "Guard: keep even numbers.", "type": "filter"},
        ]),
        "explanation": "Flattens a 2D list and keeps only even numbers.",
        "common_mistakes": ["Forgetting inner for clause", "Using != instead of =="],
        "review_interval": 3,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def all_25_categories():
    return [
        "comprehensions", "none_handling", "async_await", "decorators",
        "oop", "type_hints", "context_managers", "closures",
    ]


# ── Test: list_examples returns all 25 ────────────────────────────

@patch("app.routers.examples._get_limiter")
@patch("httpx.AsyncClient")
def test_list_examples_returns_all_25(mock_httpx_cls, mock_limiter, client, mock_supabase_response, all_25_categories):
    """GET /api/examples returns all example records from Supabase."""
    # We have 25 total; return 25 rows across 2 pages
    rows = [
        {
            "id": str(uuid.uuid4()),
            "category": all_25_categories[i % len(all_25_categories)],
            "title": f"Example {i+1}",
            "code": f"# code {i+1}",
            "annotations": "[]",
            "explanation": f"Explanation {i+1}.",
            "common_mistakes": ["Mistake A", "Mistake B"],
            "review_interval": 2,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        for i in range(25)
    ]

    mock_limiter.return_value = MagicMock()

    async def mock_get(*args, **kwargs):
        return mock_supabase_response(rows)

    mock_instance = AsyncMock()
    mock_instance.__aenter__.return_value.get = mock_get
    mock_instance.__aexit__.return_value = None
    mock_httpx_cls.return_value = mock_instance

    response = client.get("/api/examples")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 25
    assert len(data["examples"]) == 25


# ── Test: list_examples filters by category ────────────────────────

@patch("app.routers.examples._get_limiter")
@patch("httpx.AsyncClient")
def test_list_examples_filters_by_category(mock_httpx_cls, mock_limiter, client, sample_example_row):
    mock_limiter.return_value = MagicMock()

    async def mock_get(*args, **kwargs):
        # Supabase query params are passed to httpx — check category filter
        url = args[0] if args else ""
        params = kwargs.get("params", {})
        if "category" in params and params["category"] == "eq.comprehensions":
            return mock_supabase_response([sample_example_row])
        return mock_supabase_response([])

    mock_instance = AsyncMock()
    mock_instance.__aenter__.return_value.get = mock_get
    mock_instance.__aexit__.return_value = None
    mock_httpx_cls.return_value = mock_instance

    response = client.get("/api/examples?category=comprehensions")
    assert response.status_code == 200
    data = response.json()
    assert len(data["examples"]) == 1
    assert data["examples"][0]["category"] == "comprehensions"


# ── Test: list_examples pagination respects limit and offset ────────

@patch("app.routers.examples._get_limiter")
@patch("httpx.AsyncClient")
def test_list_examples_pagination_respects_limit_offset(mock_httpx_cls, mock_limiter, client):
    mock_limiter.return_value = MagicMock()

    all_rows = [
        {
            "id": str(uuid.uuid4()),
            "category": "test",
            "title": f"Example {i}",
            "code": f"# {i}",
            "annotations": "[]",
            "explanation": "Test.",
            "common_mistakes": ["A", "B"],
            "review_interval": 1,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
        }
        for i in range(50)
    ]

    async def mock_get(*args, **kwargs):
        params = kwargs.get("params", {})
        limit = int(params.get("limit", 20))
        offset = int(params.get("offset", 0))
        # Return subset matching limit/offset
        return mock_supabase_response(all_rows[offset : offset + limit])

    mock_instance = AsyncMock()
    mock_instance.__aenter__.return_value.get = mock_get
    mock_instance.__aexit__.return_value = None
    mock_httpx_cls.return_value = mock_instance

    response = client.get("/api/examples?limit=5&offset=10")
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 5
    assert data["offset"] == 10
    assert len(data["examples"]) == 5


# ── Test: get_example returns parsed annotations ───────────────────

@patch("httpx.AsyncClient")
def test_get_example_by_id_returns_parsed_annotations(mock_httpx_cls, client, sample_example_row):
    async def mock_get(*args, **kwargs):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = [sample_example_row]
        return response

    mock_instance = AsyncMock()
    mock_instance.__aenter__.return_value.get = mock_get
    mock_instance.__aexit__.return_value = None
    mock_httpx_cls.return_value = mock_instance

    response = client.get(f"/api/examples/{sample_example_row['id']}")
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Nested List Comprehension"
    assert len(data["annotations"]) == 3
    assert data["annotations"][0]["type"] == "iterator"
    assert data["annotations"][0]["line"] == 1


# ── Test: get_example not found returns 404 ────────────────────────

@patch("httpx.AsyncClient")
def test_get_example_by_id_not_found_returns_404(mock_httpx_cls, client):
    async def mock_get(*args, **kwargs):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = []
        return response

    mock_instance = AsyncMock()
    mock_instance.__aenter__.return_value.get = mock_get
    mock_instance.__aexit__.return_value = None
    mock_httpx_cls.return_value = mock_instance

    response = client.get("/api/examples/99999999-9999-9999-9999-999999999999")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ── Test: save_example requires auth ───────────────────────────────

@patch("app.routers.examples._get_limiter")
def test_save_example_requires_auth(mock_limiter, client):
    mock_limiter.return_value = MagicMock()

    response = client.post("/api/examples/11111111-1111-1111-1111-111111111101/save")
    assert response.status_code == 401


# ── Test: save_example creates trace + review_card ──────────────────

@patch("app.routers.auth.get_current_user")
@patch("app.routers.examples._fetch_profile")
@patch("app.routers.examples.get_profile_id")
@patch("httpx.AsyncClient")
def test_save_example_creates_trace_and_review_card(
    mock_httpx_cls, mock_profile_id, mock_fetch_profile,
    mock_current_user, client, sample_example_row
):
    mock_current_user.return_value = {"id": "user-123"}
    mock_fetch_profile.return_value = {"plan": "pro", "id": "profile-123"}
    mock_profile_id.return_value = "profile-123"

    async def mock_get(*args, **kwargs):
        url = args[0] if args else ""
        response = MagicMock()
        if "examples" in url:
            response.status_code = 200
            response.json.return_value = [sample_example_row]
        elif "review_cards" in url:
            response.status_code = 200
            response.json.return_value = []  # no existing card
        elif "profiles" in url:
            response.status_code = 200
            response.json.return_value = [{"id": "profile-123", "plan": "pro"}]
        else:
            response.status_code = 200
            response.json.return_value = []
        return response

    async def mock_post(*args, **kwargs):
        response = MagicMock()
        response.status_code = 201
        new_id = str(uuid.uuid4())
        response.json.return_value = [{"id": new_id}]
        return response

    mock_instance = AsyncMock()
    mock_instance.__aenter__.return_value.get = mock_get
    mock_instance.__aenter__.return_value.post = mock_post
    mock_instance.__aexit__.return_value = None
    mock_httpx_cls.return_value = mock_instance

    response = client.post(
        f"/api/examples/{sample_example_row['id']}/save",
        headers={"Authorization": "Bearer valid-token"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "card_id" in data
    assert data["existing"] is False
    assert "review queue" in data["message"].lower()


# ── Test: save_example duplicate returns existing card 200 ─────────

@patch("app.routers.auth.get_current_user")
@patch("app.routers.examples._fetch_profile")
@patch("app.routers.examples.get_profile_id")
@patch("httpx.AsyncClient")
def test_save_example_duplicate_returns_existing_card_200(
    mock_httpx_cls, mock_profile_id, mock_fetch_profile,
    mock_current_user, client, sample_example_row
):
    existing_card_id = str(uuid.uuid4())
    mock_current_user.return_value = {"id": "user-456"}
    mock_fetch_profile.return_value = {"plan": "pro", "id": "profile-456"}
    mock_profile_id.return_value = "profile-456"

    async def mock_get(*args, **kwargs):
        url = args[0] if args else ""
        response = MagicMock()
        if "examples" in url:
            response.status_code = 200
            response.json.return_value = [sample_example_row]
        elif "review_cards" in url:
            # Existing card found!
            response.status_code = 200
            response.json.return_value = [{"id": existing_card_id}]
        else:
            response.status_code = 200
            response.json.return_value = []
        return response

    mock_instance = AsyncMock()
    mock_instance.__aenter__.return_value.get = mock_get
    mock_instance.__aexit__.return_value = None
    mock_httpx_cls.return_value = mock_instance

    response = client.post(
        f"/api/examples/{sample_example_row['id']}/save",
        headers={"Authorization": "Bearer valid-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["card_id"] == existing_card_id
    assert data["existing"] is True
    assert "already" in data["message"].lower()


# ── Test: save_example not found returns 404 ───────────────────────

@patch("app.routers.auth.get_current_user")
@patch("app.routers.examples._fetch_profile")
@patch("app.routers.examples.get_profile_id")
@patch("httpx.AsyncClient")
def test_save_example_not_found_returns_404(
    mock_httpx_cls, mock_profile_id, mock_fetch_profile,
    mock_current_user, client
):
    mock_current_user.return_value = {"id": "user-789"}
    mock_fetch_profile.return_value = {"plan": "pro", "id": "profile-789"}
    mock_profile_id.return_value = "profile-789"

    async def mock_get(*args, **kwargs):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = []  # no example found
        return response

    mock_instance = AsyncMock()
    mock_instance.__aenter__.return_value.get = mock_get
    mock_instance.__aexit__.return_value = None
    mock_httpx_cls.return_value = mock_instance

    response = client.post(
        "/api/examples/00000000-0000-0000-0000-000000000000/save",
        headers={"Authorization": "Bearer valid-token"},
    )
    assert response.status_code == 404


# ── Test: save_example free plan returns 403 ──────────────────────

@patch("app.routers.auth.get_current_user")
@patch("app.routers.examples._fetch_profile")
def test_save_example_free_plan_returns_403(
    mock_fetch_profile, mock_current_user, client
):
    mock_current_user.return_value = {"id": "free-user"}
    mock_fetch_profile.return_value = {"plan": "free"}

    response = client.post(
        "/api/examples/11111111-1111-1111-1111-111111111101/save",
        headers={"Authorization": "Bearer valid-token"},
    )
    assert response.status_code == 403
    data = response.json()
    assert "UPGRADE_REQUIRED" in str(data.get("detail", {}))
```

---

## 7. Frontend API Functions — `api.ts` additions

Add these functions to `frontend/lib/api.ts` (inside the `CodeScopeAPI` class or as standalone exports):

```typescript
// ── Examples ───────────────────────────────────────────────────────

export interface ExampleAnnotation {
  line: number;
  text: string;
  type: string;
}

export interface Example {
  id: string;
  category: string;
  title: string;
  code: string;
  why_ai_generates_this: string | null;
  annotations: ExampleAnnotation[];
  explanation: string;
  common_mistakes: string[];
  review_interval: number;
}

export interface ExampleListResponse {
  examples: Example[];
  total: number;
  limit: number;
  offset: number;
}

export interface SaveExampleResponse {
  card_id: string;
  message: string;
  existing: boolean;
}

/**
 * Fetch the list of examples with optional category filter and pagination.
 * Public — no auth required.
 */
export async function fetchExamples(params?: {
  category?: string;
  limit?: number;
  offset?: number;
}): Promise<ExampleListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.category) searchParams.set("category", params.category);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));

  const query = searchParams.toString();
  const url = `${API_BASE}/examples${query ? `?${query}` : ""}`;

  const res = await fetch(url);
  if (!res.ok) throw new Error(`Failed to load examples: ${res.status}`);
  return res.json();
}

/**
 * Fetch a single example by ID, including all annotations.
 * Public — no auth required.
 */
export async function fetchExample(exampleId: string): Promise<Example> {
  const res = await fetch(`${API_BASE}/examples/${exampleId}`);
  if (res.status === 404) throw new Error("EXAMPLE_NOT_FOUND");
  if (!res.ok) throw new Error(`Failed to load example: ${res.status}`);
  return res.json();
}

/**
 * Save an example to the user's review queue.
 * Auth required. Pro plan required.
 */
export async function saveExampleToQueue(
  exampleId: string,
  notes?: string
): Promise<SaveExampleResponse> {
  const res = await authFetch(`${API_BASE}/examples/${exampleId}/save`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(notes ? { notes } : {}),
  });
  if (res.status === 401) throw new Error("AUTH_REQUIRED");
  if (res.status === 403) {
    const body = await res.json().catch(() => ({}));
    const detail = body?.detail ?? {};
    const err = new Error(detail?.message ?? "Upgrade required") as Error & {
      status: number;
      upgrade_url?: string;
    };
    err.status = 403;
    err.upgrade_url = detail?.upgrade_url ?? "/upgrade";
    throw err;
  }
  if (res.status === 404) throw new Error("EXAMPLE_NOT_FOUND");
  if (!res.ok) throw new Error(`Failed to save example: ${res.status}`);
  return res.json();
}
```

---

## 8. Frontend Browse Page — `app/examples/page.tsx`

File: `frontend/app/examples/page.tsx`

```tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { fetchExamples } from "@/lib/api";
import type { Example } from "@/lib/api";
import styles from "./page.module.css";

const CATEGORIES = [
  "comprehensions",
  "none_handling",
  "async_await",
  "decorators",
  "oop",
  "type_hints",
  "context_managers",
  "closures",
];

const CATEGORY_LABELS: Record<string, string> = {
  comprehensions: "Comprehensions",
  none_handling: "None Handling",
  async_await: "Async/Await",
  decorators: "Decorators",
  oop: "OOP",
  type_hints: "Type Hints",
  context_managers: "Context Managers",
  closures: "Closures",
};

const CATEGORY_DESCRIPTIONS: Record<string, string> = {
  comprehensions: "List, set, dict, and generator expressions",
  none_handling: "Guarding, coalescing, and ternary checks",
  async_await: "Concurrent execution with asyncio",
  decorators: "Function wrappers with functools.wraps",
  oop: "ABC, dataclasses, and mixin patterns",
  type_hints: "Callable, TypeVar, and Generic",
  context_managers: "@contextmanager and transaction patterns",
  closures: "nonlocal and functools.partial",
};

const PAGE_SIZE = 20;

export default function ExamplesBrowsePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialCategory = searchParams.get("category") ?? "";

  const [examples, setExamples] = useState<Example[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState(initialCategory);
  const [page, setPage] = useState(0);

  const loadExamples = useCallback(
    async (category: string, pageNum: number) => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchExamples({
          category: category || undefined,
          limit: PAGE_SIZE,
          offset: pageNum * PAGE_SIZE,
        });
        setExamples(data.examples);
        setTotal(data.total);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load examples");
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    loadExamples(activeCategory, page);
  }, [activeCategory, page, loadExamples]);

  const handleCategoryChange = (cat: string) => {
    setActiveCategory(cat);
    setPage(0);
    const params = cat ? `?category=${encodeURIComponent(cat)}` : "";
    router.replace(`/examples${params}`, { scroll: false });
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className={styles.page}>
      {/* Top bar */}
      <header className={styles.topBar}>
        <Link href="/" className={styles.brandLink}>
          <span className={styles.logo}>◈</span>
          <span className={styles.brandName}>CodeScope</span>
        </Link>
        <div className={styles.actions}>
          <Link href="/dashboard" className={styles.dashboardBtn}>
            Dashboard
          </Link>
        </div>
      </header>

      <main className={styles.main}>
        <div className={styles.header}>
          <h1 className={styles.title}>Learn by Example</h1>
          <p className={styles.subtitle}>
            {total > 0
              ? `${total} curated examples covering ${CATEGORIES.length} Python patterns`
              : "Curated Python patterns with step-by-step explanations"}
          </p>
        </div>

        {/* Category filters */}
        <div className={styles.filters}>
          <button
            className={`${styles.filterChip} ${!activeCategory ? styles.filterActive : ""}`}
            onClick={() => handleCategoryChange("")}
          >
            All
          </button>
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              className={`${styles.filterChip} ${activeCategory === cat ? styles.filterActive : ""}`}
              onClick={() => handleCategoryChange(cat)}
            >
              {CATEGORY_LABELS[cat] ?? cat}
            </button>
          ))}
        </div>

        {/* Active filter description */}
        {activeCategory && CATEGORY_DESCRIPTIONS[activeCategory] && (
          <p className={styles.filterDescription}>
            {CATEGORY_DESCRIPTIONS[activeCategory]}
          </p>
        )}

        {/* Error state */}
        {error && (
          <div className={styles.errorBanner}>
            <span>⚠</span> {error}
            <button className={styles.retryBtn} onClick={() => loadExamples(activeCategory, page)}>
              Retry
            </button>
          </div>
        )}

        {/* Loading state */}
        {loading && (
          <div className={styles.grid}>
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className={styles.cardSkeleton} />
            ))}
          </div>
        )}

        {/* Example grid */}
        {!loading && examples.length === 0 && !error && (
          <div className={styles.emptyState}>
            <p>No examples found for this category.</p>
            <button className={styles.clearFilterBtn} onClick={() => handleCategoryChange("")}>
              View all examples
            </button>
          </div>
        )}

        {!loading && examples.length > 0 && (
          <>
            <div className={styles.grid}>
              {examples.map((example) => (
                <Link
                  key={example.id}
                  href={`/examples/${example.id}`}
                  className={styles.card}
                >
                  <div className={styles.cardHeader}>
                    <span className={styles.categoryBadge}>
                      {CATEGORY_LABELS[example.category] ?? example.category}
                    </span>
                    <span className={styles.reviewInterval}>
                      {example.review_interval}d
                    </span>
                  </div>
                  <h3 className={styles.cardTitle}>{example.title}</h3>
                  <pre className={styles.codePreview}>
                    <code>{example.code.split("\n").slice(0, 3).join("\n")}</code>
                  </pre>
                  <p className={styles.excerpt}>{example.explanation.slice(0, 80)}…</p>
                </Link>
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className={styles.pagination}>
                <button
                  className={styles.pageBtn}
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                >
                  ← Previous
                </button>
                <span className={styles.pageInfo}>
                  Page {page + 1} of {totalPages}
                </span>
                <button
                  className={styles.pageBtn}
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                >
                  Next →
                </button>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
```

---

## 9. Frontend Browse Loading State — `app/examples/loading.tsx`

File: `frontend/app/examples/loading.tsx`

```tsx
export default function Loading() {
  return (
    <div style={{ minHeight: "100vh", background: "#0d1117", padding: "32px 24px" }}>
      <div style={{ maxWidth: "1100px", margin: "0 auto" }}>
        {/* Header skeleton */}
        <div style={{ height: "40px", background: "#21262d", borderRadius: "8px", marginBottom: "16px", width: "240px" }} />
        <div style={{ height: "20px", background: "#21262d", borderRadius: "6px", marginBottom: "32px", width: "400px" }} />

        {/* Filter chips skeleton */}
        <div style={{ display: "flex", gap: "8px", marginBottom: "24px", flexWrap: "wrap" }}>
          {Array.from({ length: 9 }).map((_, i) => (
            <div
              key={i}
              style={{
                height: "32px",
                width: `${80 + i * 10}px`,
                background: "#21262d",
                borderRadius: "16px",
              }}
            />
          ))}
        </div>

        {/* Card grid skeleton */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "16px" }}>
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              style={{
                height: "200px",
                background: "#161b22",
                border: "1px solid #21262d",
                borderRadius: "12px",
                animation: "pulse 1.5s ease-in-out infinite",
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
```

---

## 10. Frontend Detail Page — `app/examples/[id]/page.tsx`

File: `frontend/app/examples/[id]/page.tsx`

```tsx
"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { fetchExample, saveExampleToQueue } from "@/lib/api";
import type { Example } from "@/lib/api";
import styles from "./page.module.css";

// Syntax highlighting via react-syntax-highlighter (no dangerouslySetInnerHTML)
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";

const TYPE_COLORS: Record<string, string> = {
  scope: "#79c0ff",
  filter: "#ff7b72",
  iterator: "#7ee787",
  guard: "#ffa657",
  assignment: "#d2a8ff",
  function_call: "#79c0ff",
  passthrough: "#8b949e",
  side_effect: "#f85149",
  async_cm: "#79c0ff",
  executor: "#ffa657",
  offload: "#7ee787",
  yield: "#ffa657",
  body: "#8b949e",
  cleanup: "#ff7b72",
  metadata_preservation: "#d2a8ff",
  enforcement: "#f85149",
  validation: "#7ee787",
  rollback: "#ff7b72",
  commit: "#7ee787",
  begin: "#79c0ff",
  nonlocal: "#ffa657",
  mutation: "#ff7b72",
  partial: "#d2a8ff",
  factory: "#79c0ff",
  typevar: "#d2a8ff",
  parameterized: "#79c0ff",
  generic_class: "#d2a8ff",
  callable_sig: "#79c0ff",
  nested_call: "#ffa657",
  coalesce: "#ffa657",
  ternary: "#ffa657",
  sentinel: "#8b949e",
  default: "#8b949e",
  config_layer: "#79c0ff",
  func_layer: "#79c0ff",
  execution_layer: "#ffa657",
  init: "#7ee787",
  callable_layer: "#79c0ff",
  abc: "#d2a8ff",
  contract: "#7ee787",
  boilerplate: "#8b949e",
  mutable_default: "#f85149",
  mixin: "#d2a8ff",
  mixin_usage: "#7ee787",
  self_reflection: "#ffa657",
  enter: "#7ee787",
  exit: "#7ee787",
  timing: "#8b949e",
  async_wait: "#79c0ff",
  closure_var: "#ffa657",
  dedup: "#7ee787",
  range_check: "#7ee787",
};

function getTypeColor(type: string): string {
  return TYPE_COLORS[type] ?? "#8b949e";
}

export default function ExampleDetailPage() {
  const params = useParams();
  const router = useRouter();
  const exampleId = params.id as string;

  const [example, setExample] = useState<Example | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [activeAnnotation, setActiveAnnotation] = useState<number | null>(null);

  const loadExample = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchExample(exampleId);
      setExample(data);
    } catch (err) {
      if (err instanceof Error && err.message === "EXAMPLE_NOT_FOUND") {
        setError("Example not found.");
      } else {
        setError(err instanceof Error ? err.message : "Failed to load example");
      }
    } finally {
      setLoading(false);
    }
  }, [exampleId]);

  useEffect(() => {
    loadExample();
  }, [loadExample]);

  const handleSaveToQueue = useCallback(async () => {
    setSaving(true);
    setSaveError(null);
    setSaveSuccess(false);
    try {
      const result = await saveExampleToQueue(exampleId);
      setSaveSuccess(true);
      if (result.existing) {
        setSaveError("Already in your review queue.");
      } else {
        setSaveSuccess(true);
      }
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      if (err instanceof Error && err.message === "AUTH_REQUIRED") {
        router.push(`/auth/login?redirect=/examples/${exampleId}`);
        return;
      }
      const upgradeErr = err as Error & { upgrade_url?: string };
      if (upgradeErr?.upgrade_url) {
        router.push(upgradeErr.upgrade_url);
        return;
      }
      setSaveError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }, [exampleId, router]);

  if (loading) {
    return (
      <div className={styles.page}>
        <header className={styles.topBar}>
          <Link href="/examples" className={styles.backLink}>← Examples</Link>
        </header>
        <main className={styles.main}>
          <div className={styles.loading}>
            <span className={styles.spinner}>◈</span> Loading example…
          </div>
        </main>
      </div>
    );
  }

  if (error || !example) {
    return (
      <div className={styles.page}>
        <header className={styles.topBar}>
          <Link href="/examples" className={styles.backLink}>← Examples</Link>
        </header>
        <main className={styles.main}>
          <div className={styles.errorState}>
            <p>{error ?? "Example not found."}</p>
            <button className={styles.retryBtn} onClick={loadExample}>Retry</button>
          </div>
        </main>
      </div>
    );
  }

  const codeLines = example.code.split("\n");

  return (
    <div className={styles.page}>
      {/* Top bar */}
      <header className={styles.topBar}>
        <Link href="/examples" className={styles.backLink}>← Examples</Link>
        <div className={styles.topBarActions}>
          {saveSuccess && (
            <span className={styles.saveSuccessBadge}>✓ Added to review queue</span>
          )}
          <button
            className={styles.saveBtn}
            onClick={handleSaveToQueue}
            disabled={saving || saveSuccess}
          >
            {saving ? "⏳ Saving..." : saveSuccess ? "✓ Saved" : "💾 Save to Review Queue"}
          </button>
        </div>
      </header>

      {/* Error messages */}
      {saveError && !saveError.includes("Already") && (
        <div className={styles.errorBanner}>{saveError}</div>
      )}

      <main className={styles.main}>
        {/* Header */}
        <div className={styles.exampleHeader}>
          <div className={styles.meta}>
            <span className={styles.categoryBadge}>
              {example.category.replace("_", " ")}
            </span>
            <span className={styles.reviewInterval}>
              Review every {example.review_interval} day{example.review_interval !== 1 ? "s" : ""}
            </span>
          </div>
          <h1 className={styles.title}>{example.title}</h1>
        </div>

        <div className={styles.layout}>
          {/* Code panel */}
          <div className={styles.codePanel}>
            <h2 className={styles.sectionTitle}>Code</h2>
            <div className={styles.codeBlock}>
              <SyntaxHighlighter
                language="python"
                style={vscDarkPlus}
                showLineNumbers
                wrapLines
                customStyle={{
                  margin: 0,
                  borderRadius: "8px",
                  fontSize: "13px",
                  background: "#0d1117",
                  padding: "16px",
                }}
                lineProps={(lineNumber) => {
                  const annotation = example.annotations.find(
                    (a) => a.line === lineNumber
                  );
                  return {
                    style: annotation
                      ? {
                          background: `${getTypeColor(annotation.type)}15`,
                          borderLeft: `3px solid ${getTypeColor(annotation.type)}`,
                        }
                      : {},
                    onClick: annotation
                      ? () =>
                          setActiveAnnotation(
                            activeAnnotation === lineNumber ? null : lineNumber
                          )
                      : undefined,
                  };
                }}
              >
                {example.code}
              </SyntaxHighlighter>
            </div>

            {/* Annotation legend */}
            {example.annotations.length > 0 && (
              <div className={styles.legend}>
                <span className={styles.legendLabel}>Line colors:</span>
                {Array.from(new Set(example.annotations.map((a) => a.type))).map(
                  (type) => (
                    <span
                      key={type}
                      className={styles.legendItem}
                      style={{ borderColor: getTypeColor(type) }}
                    >
                      {type.replace("_", " ")}
                    </span>
                  )
                )}
              </div>
            )}
          </div>

          {/* Annotations panel */}
          <div className={styles.annotationsPanel}>
            <h2 className={styles.sectionTitle}>Explanations</h2>

            {example.annotations.length === 0 ? (
              <p className={styles.noAnnotations}>No annotations available.</p>
            ) : (
              <div className={styles.annotationList}>
                {example.annotations.map((ann, i) => (
                  <div
                    key={i}
                    className={`${styles.annotation} ${
                      activeAnnotation === ann.line ? styles.annotationActive : ""
                    }`}
                    onClick={() =>
                      setActiveAnnotation(
                        activeAnnotation === ann.line ? null : ann.line
                      )
                    }
                  >
                    <div className={styles.annotationHeader}>
                      <span className={styles.annotationLine}>Line {ann.line}</span>
                      <span
                        className={styles.annotationType}
                        style={{ color: getTypeColor(ann.type) }}
                      >
                        {ann.type.replace("_", " ")}
                      </span>
                    </div>
                    <p className={styles.annotationText}>{ann.text}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Explanation */}
            <div className={styles.explanationSection}>
              <h3 className={styles.subSectionTitle}>Summary</h3>
              <p className={styles.explanationText}>{example.explanation}</p>
            </div>

            {/* Common mistakes */}
            {example.common_mistakes.length > 0 && (
              <div className={styles.mistakesSection}>
                <h3 className={styles.subSectionTitle}>Common Mistakes</h3>
                <ul className={styles.mistakesList}>
                  {example.common_mistakes.map((mistake, i) => (
                    <li key={i} className={styles.mistakeItem}>
                      ⚠ {mistake}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Why AI generates this */}
            {example.why_ai_generates_this && (
              <div className={styles.aiContextSection}>
                <h3 className={styles.subSectionTitle}>Why AI Generates This</h3>
                <p className={styles.aiContextText}>
                  {example.why_ai_generates_this}
                </p>
              </div>
            )}

            {/* Save CTA */}
            <div className={styles.saveCta}>
              <p className={styles.saveCtaText}>
                Add this pattern to your spaced-repetition review queue.
              </p>
              <button
                className={styles.saveCtaBtn}
                onClick={handleSaveToQueue}
                disabled={saving || saveSuccess}
              >
                {saving
                  ? "⏳ Adding..."
                  : saveSuccess
                  ? "✓ Added!"
                  : "💾 Add to Review Queue"}
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
```

---

## 11. Frontend Detail Loading State — `app/examples/[id]/loading.tsx`

File: `frontend/app/examples/[id]/loading.tsx`

```tsx
export default function Loading() {
  return (
    <div style={{ minHeight: "100vh", background: "#0d1117", color: "#e6edf3", fontFamily: "sans-serif" }}>
      {/* Top bar skeleton */}
      <div style={{ height: "56px", borderBottom: "1px solid #21262d", padding: "0 24px", display: "flex", alignItems: "center", gap: "16px" }}>
        <div style={{ height: "20px", width: "100px", background: "#21262d", borderRadius: "6px" }} />
        <div style={{ height: "32px", width: "160px", background: "#21262d", borderRadius: "6px", marginLeft: "auto" }} />
      </div>

      {/* Main content */}
      <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "32px 24px" }}>
        {/* Header */}
        <div style={{ height: "20px", width: "120px", background: "#21262d", borderRadius: "6px", marginBottom: "8px" }} />
        <div style={{ height: "36px", width: "60%", background: "#21262d", borderRadius: "8px", marginBottom: "32px" }} />

        {/* Two-column layout */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: "24px" }}>
          {/* Code panel */}
          <div>
            <div style={{ height: "24px", width: "80px", background: "#21262d", borderRadius: "6px", marginBottom: "12px" }} />
            <div style={{ height: "400px", background: "#161b22", border: "1px solid #21262d", borderRadius: "12px" }} />
          </div>

          {/* Annotations panel */}
          <div>
            <div style={{ height: "24px", width: "120px", background: "#21262d", borderRadius: "6px", marginBottom: "16px" }} />
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {Array.from({ length: 4 }).map((_, i) => (
                <div
                  key={i}
                  style={{
                    height: "80px",
                    background: "#161b22",
                    border: "1px solid #21262d",
                    borderRadius: "8px",
                  }}
                />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
```

---

## 12. CSS Files

### `frontend/app/examples/page.module.css`

```css
.page { min-height: 100vh; background: #0d1117; color: #e6edf3; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }

.topBar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 24px; height: 56px; border-bottom: 1px solid #21262d; background: #161b22;
}
.brandLink { display: flex; align-items: center; gap: 8px; text-decoration: none; }
.logo { font-size: 20px; color: #58a6ff; }
.brandName { font-size: 16px; font-weight: 700; color: #e6edf3; }
.actions { display: flex; align-items: center; gap: 12px; }

.dashboardBtn {
  padding: 7px 16px; background: transparent; border: 1px solid #30363d;
  border-radius: 6px; color: #8b949e; font-size: 13px; text-decoration: none;
  transition: all 0.15s;
}
.dashboardBtn:hover { background: #21262d; color: #e6edf3; }

.main { max-width: 1100px; margin: 0 auto; padding: 32px 24px; display: flex; flex-direction: column; gap: 24px; }

.header { margin-bottom: 8px; }
.title { font-size: 28px; font-weight: 800; color: #e6edf3; margin: 0 0 8px; }
.subtitle { font-size: 14px; color: #8b949e; margin: 0; }

.filters { display: flex; flex-wrap: wrap; gap: 8px; }
.filterChip {
  padding: 6px 14px; border-radius: 20px; border: 1px solid #30363d;
  background: #161b22; color: #8b949e; font-size: 13px; cursor: pointer;
  transition: all 0.15s;
}
.filterChip:hover { border-color: #58a6ff; color: #58a6ff; background: rgba(88,166,255,0.08); }
.filterActive { border-color: #58a6ff; color: #58a6ff; background: rgba(88,166,255,0.12); }

.filterDescription { font-size: 13px; color: #58a6ff; margin: -8px 0 0; font-style: italic; }

.errorBanner {
  display: flex; align-items: center; gap: 8px; padding: 12px 16px;
  background: rgba(248,81,73,0.1); border: 1px solid rgba(248,81,73,0.3);
  border-radius: 8px; color: #f85149; font-size: 13px;
}
.retryBtn {
  margin-left: auto; padding: 4px 12px; background: transparent;
  border: 1px solid rgba(248,81,73,0.4); border-radius: 4px;
  color: #f85149; font-size: 12px; cursor: pointer;
}
.retryBtn:hover { background: rgba(248,81,73,0.15); }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }

.cardSkeleton {
  height: 200px; background: #161b22; border: 1px solid #21262d;
  border-radius: 12px; animation: pulse 1.5s ease-in-out infinite;
}
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }

.emptyState {
  display: flex; flex-direction: column; align-items: center; gap: 12px;
  padding: 60px 20px; text-align: center; color: #8b949e;
}
.clearFilterBtn {
  padding: 8px 20px; background: #21262d; border: 1px solid #30363d;
  border-radius: 6px; color: #e6edf3; font-size: 13px; cursor: pointer;
}
.clearFilterBtn:hover { background: #30363d; }

.card {
  display: flex; flex-direction: column; gap: 10px; padding: 16px;
  background: #161b22; border: 1px solid #21262d; border-radius: 12px;
  text-decoration: none; transition: border-color 0.15s, transform 0.15s;
}
.card:hover { border-color: #58a6ff; transform: translateY(-2px); }

.cardHeader { display: flex; align-items: center; justify-content: space-between; }
.categoryBadge {
  font-size: 11px; font-weight: 600; padding: 2px 8px;
  background: rgba(88,166,255,0.12); border: 1px solid rgba(88,166,255,0.3);
  border-radius: 12px; color: #58a6ff; text-transform: capitalize;
}
.reviewInterval { font-size: 11px; color: #484f58; }
.cardTitle { font-size: 14px; font-weight: 600; color: #e6edf3; margin: 0; }
.codePreview {
  background: #0d1117; border-radius: 6px; padding: 10px 12px; margin: 0;
  overflow: hidden;
}
.codePreview code {
  font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace;
  font-size: 11px; color: #8b949e; white-space: pre; display: block;
  max-height: 60px; overflow: hidden;
}
.excerpt { font-size: 12px; color: #484f58; margin: 0; line-height: 1.5; }

.pagination { display: flex; align-items: center; justify-content: center; gap: 16px; margin-top: 8px; }
.pageBtn {
  padding: 7px 16px; background: #21262d; border: 1px solid #30363d;
  border-radius: 6px; color: #e6edf3; font-size: 13px; cursor: pointer;
  transition: all 0.15s;
}
.pageBtn:hover:not(:disabled) { background: #30363d; }
.pageBtn:disabled { opacity: 0.4; cursor: not-allowed; }
.pageInfo { font-size: 13px; color: #8b949e; }
```

### `frontend/app/examples/[id]/page.module.css`

```css
.page { min-height: 100vh; background: #0d1117; color: #e6edf3; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }

.topBar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 24px; height: 56px; border-bottom: 1px solid #21262d; background: #161b22;
}
.backLink {
  font-size: 13px; color: #58a6ff; text-decoration: none;
  display: flex; align-items: center; gap: 4px;
}
.backLink:hover { text-decoration: underline; }
.topBarActions { display: flex; align-items: center; gap: 12px; }

.saveSuccessBadge {
  font-size: 13px; color: #7ee787; font-weight: 500;
}
.saveBtn {
  padding: 8px 16px; background: linear-gradient(135deg, #1f6feb, #388bfd);
  border-radius: 6px; border: none; color: white; font-size: 13px;
  font-weight: 600; cursor: pointer; transition: all 0.15s;
}
.saveBtn:hover:not(:disabled) { background: linear-gradient(135deg, #388bfd, #58a6ff); transform: translateY(-1px); }
.saveBtn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

.errorBanner {
  margin: 0 24px; padding: 10px 16px; background: rgba(248,81,73,0.1);
  border: 1px solid rgba(248,81,73,0.3); border-radius: 8px;
  color: #f85149; font-size: 13px; margin-top: 12px;
}

.main { max-width: 1200px; margin: 0 auto; padding: 32px 24px; }

.loading { display: flex; align-items: center; justify-content: center; min-height: 60vh; gap: 12px; color: #8b949e; }
.spinner { animation: spin 1s linear infinite; color: #58a6ff; font-size: 20px; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.errorState { display: flex; flex-direction: column; align-items: center; gap: 16px; padding: 80px 20px; text-align: center; color: #8b949e; }
.retryBtn { padding: 8px 20px; background: #21262d; border: 1px solid #30363d; border-radius: 6px; color: #e6edf3; font-size: 13px; cursor: pointer; }

.exampleHeader { margin-bottom: 28px; }
.meta { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.categoryBadge {
  font-size: 11px; font-weight: 600; padding: 3px 10px;
  background: rgba(88,166,255,0.12); border: 1px solid rgba(88,166,255,0.3);
  border-radius: 12px; color: #58a6ff; text-transform: capitalize;
}
.reviewInterval { font-size: 12px; color: #484f58; }
.title { font-size: 26px; font-weight: 800; color: #e6edf3; margin: 0; }

.layout { display: grid; grid-template-columns: 1fr 380px; gap: 24px; align-items: start; }

.codePanel { display: flex; flex-direction: column; gap: 12px; }
.sectionTitle { font-size: 14px; font-weight: 700; color: #8b949e; margin: 0 0 8px; text-transform: uppercase; letter-spacing: 0.5px; }
.codeBlock { border-radius: 10px; overflow: hidden; border: 1px solid #21262d; }
.legend { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.legendLabel { font-size: 11px; color: #484f58; }
.legendItem {
  font-size: 11px; padding: 2px 8px; border-radius: 10px;
  border: 1px solid; background: rgba(255,255,255,0.04);
  color: #8b949e; text-transform: capitalize;
}

.annotationsPanel { display: flex; flex-direction: column; gap: 20px; }
.noAnnotations { font-size: 13px; color: #484f58; margin: 0; }

.annotationList { display: flex; flex-direction: column; gap: 8px; }
.annotation {
  padding: 12px; background: #161b22; border: 1px solid #21262d;
  border-radius: 8px; cursor: pointer; transition: border-color 0.15s;
}
.annotation:hover { border-color: #30363d; }
.annotationActive { border-color: #58a6ff !important; background: rgba(88,166,255,0.06); }
.annotationHeader { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.annotationLine { font-size: 11px; font-weight: 700; color: #8b949e; }
.annotationType { font-size: 11px; font-weight: 600; text-transform: capitalize; }
.annotationText { font-size: 13px; color: #e6edf3; margin: 0; line-height: 1.6; }

.subSectionTitle { font-size: 13px; font-weight: 700; color: #8b949e; margin: 0 0 10px; text-transform: uppercase; letter-spacing: 0.5px; }
.explanationSection, .mistakesSection, .aiContextSection { padding-top: 16px; border-top: 1px solid #21262d; }
.explanationText { font-size: 13px; color: #e6edf3; margin: 0; line-height: 1.7; }
.mistakesList { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.mistakeItem { font-size: 13px; color: #f85149; line-height: 1.5; }
.aiContextText { font-size: 13px; color: #8b949e; margin: 0; line-height: 1.7; font-style: italic; }

.saveCta {
  padding: 16px; background: #161b22; border: 1px solid #21262d;
  border-radius: 10px; display: flex; flex-direction: column; gap: 10px;
}
.saveCtaText { font-size: 13px; color: #8b949e; margin: 0; }
.saveCtaBtn {
  padding: 10px 20px; background: linear-gradient(135deg, #1f6feb, #388bfd);
  border: none; border-radius: 8px; color: white; font-size: 14px;
  font-weight: 600; cursor: pointer; transition: all 0.15s; text-align: center;
}
.saveCtaBtn:hover:not(:disabled) { background: linear-gradient(135deg, #388bfd, #58a6ff); transform: translateY(-1px); }
.saveCtaBtn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
```

---

## 13. E2E Tests — `frontend/e2e/examples.spec.ts`

```typescript
// frontend/e2e/examples.spec.ts
// Run with: npx playwright test e2e/examples.spec.ts --reporter=list
// Requires: npm install -D @playwright/test && npx playwright install

import { test, expect, Page } from "@playwright/test";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:3000";

// ── Test: browse page loads examples ────────────────────────────────────

test("browse page loads examples", async ({ page }) => {
  await page.goto(`${API_BASE}/examples`);
  // Page should have a heading
  await expect(page.locator("h1")).toContainText("Example Library");
  // Category tabs should be visible
  await expect(page.getByRole("button", { name: /all/i })).toBeVisible();
  // Wait for the grid to populate (loading state should disappear)
  await page.waitForSelector('[class*="grid"]', { timeout: 10000 });
  // At least one example card should appear
  const cards = page.locator('[class*="card"]');
  await expect(cards.first()).toBeVisible({ timeout: 10000 });
});

// ── Test: category filter updates results ──────────────────────────────

test("category filter updates results", async ({ page }) => {
  await page.goto(`${API_BASE}/examples`);
  // Click the "comprehensions" tab
  await page.getByRole("button", { name: /comprehensions/i }).click();
  // Wait for URL or page to update
  await page.waitForURL(/category=comprehensions/);
  // All visible cards should be in the comprehensions category
  const cards = page.locator('[class*="card"]');
  const count = await cards.count();
  expect(count).toBeGreaterThan(0);
});

// ── Test: detail page renders code and annotations ────────────────────

test("detail page renders code and annotations", async ({ page }) => {
  // First go to the browse page and click the first card
  await page.goto(`${API_BASE}/examples`);
  await page.waitForSelector('[class*="card"]', { timeout: 10000 });
  const firstCard = page.locator('[class*="card"]').first();
  await firstCard.click();
  // Wait for detail page to load
  await page.waitForURL(/\/examples\/.+/);
  // Title should be visible
  await expect(page.locator("h1")).toBeVisible();
  // Code section should be present
  await expect(page.locator('[class*="codeSection"]')).toBeVisible();
  // "Save to My Review Queue" button should be visible
  await expect(page.getByRole("button", { name: /save to my review queue/i })).toBeVisible();
});

// ── Test: save button requires auth ────────────────────────────────────

test("save button redirects to login for unauthenticated users", async ({ page }) => {
  await page.goto(`${API_BASE}/examples`);
  await page.waitForSelector('[class*="card"]', { timeout: 10000 });
  // Click the first example card
  await page.locator('[class*="card"]').first().click();
  await page.waitForURL(/\/examples\/.+/);
  // Click "Save to My Review Queue" (no auth cookie set)
  await page.getByRole("button", { name: /save to my review queue/i }).click();
  // Should redirect to login page
  await page.waitForURL(/\/auth\/login/, { timeout: 5000 });
});
```

---

## 14. Navigation Link in Dashboard

Add a link to `/examples` in the dashboard's action bar. Edit `frontend/app/dashboard/page.tsx`:

Find the `<div className={styles.actions}>` section and add the Examples link:

```tsx
<div className={styles.actions}>
  <Link href="/examples" className={styles.examplesLink}>
    📚 Examples
  </Link>
  <Link href="/" className={styles.newTraceBtn}>+ New Trace</Link>
  <div className={styles.userMenu}>
    <span className={styles.userEmail}>{userEmail}</span>
    <button onClick={handleSignOut} className={styles.signOutBtn}>Sign out</button>
  </div>
</div>
```

Add the corresponding CSS to `frontend/app/dashboard/page.module.css`:

```css
.examplesLink {
  padding: 7px 14px; background: #161b22; border: 1px solid #30363d;
  border-radius: 6px; color: #8b949e; font-size: 13px; text-decoration: none;
  transition: all 0.15s;
}
.examplesLink:hover { background: #21262d; color: #e6edf3; }
```

---

## 15. File Creation Order

Create files in this exact order to respect dependencies:

1. `backend/migrations/V002__examples_table.sql` — database schema
2. `backend/app/routers/examples.py` — new router
3. `backend/app/main.py` — register router
4. `backend/tests/unit/test_examples.py` — backend unit tests
5. `frontend/lib/api.ts` — add `fetchExamples`, `fetchExample`, `saveExampleToQueue`
6. `frontend/app/examples/page.tsx` — browse page
7. `frontend/app/examples/loading.tsx` — browse loading state
8. `frontend/app/examples/page.module.css` — browse styles
9. `frontend/app/examples/[id]/page.tsx` — detail page
10. `frontend/app/examples/[id]/loading.tsx` — detail loading state
11. `frontend/app/examples/[id]/page.module.css` — detail styles
12. `frontend/app/dashboard/page.tsx` — add nav link
13. `frontend/app/dashboard/page.module.css` — add nav styles
14. `frontend/e2e/examples.spec.ts` — E2E tests
15. **Install dependency:** `cd frontend && npm install react-syntax-highlighter`
16. **Add to `requirements.txt`:** `slowapi>=0.9.0`

---

## 16. Error Recovery


| Symptom                                              | Likely Cause                       | Fix                                                                                        |
| ---------------------------------------------------- | ---------------------------------- | ------------------------------------------------------------------------------------------ |
| `python -m pytest tests/unit/test_examples.py` fails | `slowapi` not installed            | `pip install slowapi`                                                                      |
| `GET /api/examples` returns 502                      | `SUPABASE_URL` incorrect in `.env` | Verify `backend/.env` has the correct project URL                                          |
| `GET /api/examples` returns 502                      | Service key expired                | Regenerate `SUPABASE_SERVICE_KEY` in Supabase dashboard                                    |
| Migration fails                                      | RLS policy already exists          | Check Supabase SQL editor; the `CREATE POLICY` statements may need `DROP POLICY IF EXISTS` |
| Frontend "Save to Queue" shows UPGRADE_REQUIRED      | User is on free plan               | Show upgrade CTA; this is expected behavior for free users                                 |
| Frontend "Save to Queue" redirects to `/auth/login`  | No session token                   | User must be logged in; redirect to login with return URL                                  |
| Supabase returns 401 on profile fetch                | `get_profile_id` helper broken     | Verify the `profiles` table has `user_id` column matching `auth.users.id`                  |
| `react-syntax-highlighter` throws on import          | SSR issue                          | All imports are inside `"use client"` files; verify no server-side import                  |
| Pagination shows same page on next click             | `page` state not resetting         | `handleCategoryChange` calls `setPage(0)` — verify state update order                      |


---

## 17. Verification Commands

Run in order. Stop at the first failure.

```bash
# 1 — Backend unit tests
cd backend
python -m pytest tests/unit/test_examples.py -v --tb=short

# 2 — Backend type check (if mypy is configured)
cd backend
python -m mypy app/routers/examples.py --ignore-missing-imports

# 3 — Backend lint (if ruff is configured)
cd backend
python -m ruff check app/routers/examples.py

# 4 — Start backend dev server (separate terminal)
cd backend
uvicorn app.main:app --reload --port 8000

# 5 — Smoke test the examples endpoints
curl http://localhost:8000/api/examples | python -m json.tool | head -30
curl http://localhost:8000/api/examples?category=comprehensions | python -m json.tool | head -20
curl http://localhost:8000/api/examples/11111111-1111-1111-1111-111111111101 | python -m json.tool | head -30

# 6 — Frontend build
cd frontend
npm run build 2>&1 | tail -20

# 7 — Frontend E2E tests
cd frontend
npx playwright test e2e/examples.spec.ts --reporter=list
```

---

## 18. Success Criteria Checklist

### Completeness

- All 25 example records with complete `code`, `annotations`, `explanation`, `common_mistakes`, `review_interval`
- Annotation types cover all 54 types from the spec
- Deduplication logic returns existing `card_id` with HTTP 200 on duplicate save
- `SaveExampleRequest` Pydantic model with optional `notes` field

### Correctness

- Every file is complete: no stubs, no `pass`, no `TODO`, no "fill in later"
- Migration SQL is runnable as-is against Supabase
- All 25 example UUIDs are unique
- Annotation `line` numbers are 1-indexed and match the code

### Implementation Clarity

- Prerequisites section exists and is accurate
- File creation order is correct (no forward references)
- Error recovery table covers all 7 failure modes
- Verification commands are copy-paste runnable

### Educational Value

- All 25 example titles are unique and descriptive
- Each annotation's `text` is a full sentence explaining the line
- `common_mistakes` has at least 2 entries per example
- 8 distinct categories represented (comprehensions, none_handling, async_await, decorators, oop, type_hints, context_managers, closures)

### Backend Architecture

- `slowapi.Limiter` applied: 60/min on `GET /examples`, 10/min on `POST /examples/{id}/save`
- Status codes: 201 (created), 200 (dedup), 401 (no auth), 403 (free plan), 404 (not found)
- `get_current_user` used for auth; `get_profile_id` for profile lookup
- `review_interval` on example used only for initial card creation (subsequent intervals via SM-2)

### Frontend Architecture

- Browse page calls `fetchExamples()` from `frontend/lib/api.ts`
- Detail page calls `fetchExample(exampleId)` from `frontend/lib/api.ts`
- Both loading states use Next.js App Router `loading.tsx` files
- No `dangerouslySetInnerHTML` anywhere in the example pages
- Code rendered via `react-syntax-highlighter` with `prism` style

### Test Coverage

- All 10 backend test functions present and named exactly as specified
- All 4 E2E test functions present in `examples.spec.ts` (browse page loads, category filter, detail page, auth redirect)
- Unit tests mock `httpx.AsyncClient`, not Supabase directly

### Red Flags

- Auth check on `POST /examples/{id}/save` uses `get_current_user` (not a raw header check)
- Pro plan check is `profile.get("plan") != "pro"` — explicit, not implicit
- Rate limiting decorator applied to both endpoints
- Pagination: `?limit=` (default 20, max 50) and `?offset=` accepted and respected
- XSS prevention: all user-facing text is React-escaped; no HTML injection possible
- No hardcoded secrets in any new file

