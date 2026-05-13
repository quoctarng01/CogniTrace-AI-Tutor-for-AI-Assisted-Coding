-- ============================================================
-- CodeScope — Phase 4 Example Data
-- 25 curated educational Python patterns
-- Run this AFTER V002__examples_table.sql
-- ============================================================

BEGIN;

INSERT INTO examples (id, category, title, code, why_ai_generates_this, annotations, explanation, common_mistakes, review_interval) VALUES

-- ── 2.1 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111101', 'comprehensions',
'Nested List Comprehension with Conditional Filter',
E'matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]\nevens = [x for row in matrix for x in row if x % 2 == 0]',
'AI flattens multi-level data structures in one expression to avoid explicit nested loops.',
'[{"line": 1, "text": "Assign the variable ''matrix'' to a list of three lists (a 3x3 grid).", "type": "assignment"}, {"line": 2, "text": "Outer iterator — iterates over each inner list in the matrix, one row at a time.", "type": "iterator"}, {"line": 2, "text": "Inner iterator — unpacks each element x from the current row.", "type": "iterator"}, {"line": 2, "text": "Guard condition — keeps only even numbers. Odd values are discarded.", "type": "filter"}, {"line": 2, "text": "Collects passing values into the resulting flat list.", "type": "scope"}]',
'This flattens a 3x3 matrix into a single list of only the even numbers [2, 4, 6, 8]. The outer comprehension builds the row-level scope; the inner clause extracts each element; the `if` clause acts as a guard to filter conditionally.',
'{"Forgetting the inner iterator clause (`for x in row`) and only writing one `for` — resulting in a list of lists instead of a flat list.", "Using `x % 2 != 0` instead of `== 0` and then being surprised by which numbers appear."}',
'1,3,7'),

-- ── 2.2 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111102', 'comprehensions',
'Building a Dictionary from Two Zipped Lists',
E'keys   = ["name", "age", "city"]\nvalues = ["Alice", 30, "Boston"]\nd      = dict(zip(keys, values))',
'AI uses zip+dict as the idiomatic alternative to manual loop-based dict construction.',
'[{"line": 1, "text": "Bind the name ''keys'' to the list of string keys.", "type": "assignment"}, {"line": 2, "text": "Bind the name ''values'' to the list of corresponding values.", "type": "assignment"}, {"line": 3, "text": "zip() pairs elements at matching indices into tuples: (''name'',''Alice''), (''age'',30), ...", "type": "iterator"}, {"line": 3, "text": "dict() consumes the zip iterator and constructs a mapping from those tuples.", "type": "factory"}]',
'`zip(keys, values)` creates an iterator of 2-tuples by walking both lists in parallel. `dict()` consumes that iterator and builds a standard Python dict. This is the idiomatic replacement for the error-prone `{}` + loop pattern.',
'{"Passing lists of unequal length — zip silently truncates to the shorter list, losing data.", "Forgetting that `dict()` on a zip object consumes it (calling `dict(zip(...))` twice fails the second time)."}',
'1,3,7'),

-- ── 2.3 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111103', 'comprehensions',
'Set Comprehension with Sorted Output',
E'data = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5]\nunique_sorted = sorted({x for x in data if x > 2})',
'AI uses set comprehensions to deduplicate in one line rather than building a manual deduplication loop.',
'[{"line": 1, "text": "Assign a list of integers to ''data'', with deliberate duplicates.", "type": "assignment"}, {"line": 2, "text": "Set comprehension — collects values passing the filter, automatically discarding duplicates.", "type": "iterator"}, {"line": 2, "text": "Filter guard — keeps only values strictly greater than 2.", "type": "filter"}, {"line": 2, "text": "sorted() converts the set back to a list ordered ascending.", "type": "factory"}]',
'The set comprehension `{x for x in data if x > 2}` deduplicates automatically because sets cannot hold duplicate keys. `sorted()` then converts the unordered set into an ascending list.',
'{"Assuming set order is preserved (sets are inherently unordered in Python < 3.7; dict insertion order is guaranteed, not set order).", "Using `x >= 2` and being surprised that 2 itself is excluded."}',
'1,2,4'),

-- ── 2.4 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111104', 'comprehensions',
'Walrus Operator to Capture Repeated Function Call',
'import re\nif (m := re.search(r''\\d+'', data)) and (n := re.search(r''\\d+'', data[m.end():])):\n    print(f"Found: {m.group()} and {n.group()}")',
'AI uses the walrus operator (:=) to avoid calling the same expensive function twice in one expression.',
'[{"line": 1, "text": "Import the regular expression module.", "type": "side_effect"}, {"line": 2, "text": "Walrus captures re.search result into variable m; used in truth test and later.", "type": "assignment"}, {"line": 2, "text": "Slice data starting after m''s match end; second search runs on the remainder.", "type": "iterator"}, {"line": 2, "text": "Walrus captures second search into n; both must be truthy for the block to run.", "type": "assignment"}, {"line": 3, "text": "Both captures are in scope here — m.group() and n.group() refer to the captured expressions.", "type": "closure_var"}]',
'The walrus operator `:=` assigns a value to a variable while returning it, enabling you to call `re.search` once and reuse its result without calling it twice. This avoids redundant computation and simplifies the conditional.',
'{"Using walrus inside a comprehension filter that gets evaluated multiple times (each evaluation re-runs the assigned expression).", "Forgetting that walrus has lower precedence than almost everything — wrapping in parentheses is almost always needed."}',
'1,4,7'),

-- ── 2.5 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111105', 'comprehensions',
'Generator Expression vs List Comprehension for Large Data',
'values = range(1_000_000)\nlist_sum   = sum([x for x in values if x % 3 == 0])\ngen_sum    = sum(x for x in values if x % 3 == 0)',
'AI uses generator expressions to avoid materializing large intermediate lists in memory.',
'[{"line": 1, "text": "range(1_000_000) is a lazy iterator — no million-element list is allocated yet.", "type": "iterator"}, {"line": 2, "text": "Square brackets force full materialization into a list before sum() receives it.", "type": "factory"}, {"line": 2, "text": "sum() then iterates the materialized list to compute the total.", "type": "iterator"}, {"line": 3, "text": "No brackets — this is a generator expression; sum() consumes it lazily, one element at a time.", "type": "iterator"}, {"line": 3, "text": "Memory-efficient: only one integer exists in memory at any moment.", "type": "offload"}]',
'List comprehensions eagerly build the entire list in memory before `sum()` can begin. Generator expressions are lazy — `sum()` pulls items one at a time as needed. For a million-element range, the generator version avoids allocating an 8 MB list.',
'{"Using `sum([...])` (list comp) and being unaware of the intermediate list allocation.", "Passing a generator expression to a function that needs to iterate multiple times (it will be exhausted on the second pass)."}',
'1,3,7'),

-- ── 2.6 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111201', 'none_handling',
'Chained Comparison with is not None',
'def classify(value):\n    if value is not None and 0 <= value <= 100:\n        return "valid"\n    return "invalid"',
'AI chains comparisons for cleaner range checks and adds explicit None guards to prevent TypeError.',
'[{"line": 1, "text": "Define classify function taking one parameter ''value''.", "type": "function_call"}, {"line": 2, "text": "Guard: check that value is not None before any comparison — prevents TypeError.", "type": "guard"}, {"line": 2, "text": "Chained comparison: 0 <= value AND value <= 100, evaluated as a single boolean expression.", "type": "filter"}, {"line": 3, "text": "Return ''valid'' string if both conditions are True.", "type": "assignment"}, {"line": 4, "text": "Return ''invalid'' string for all other cases (None, out of range, non-numeric).", "type": "assignment"}]',
'The chained comparison `0 <= value <= 100` is equivalent to `(0 <= value) and (value <= 100)` but is shorter and slightly faster. The `value is not None` guard must come first, or the chained comparison would raise a `TypeError` when `value` is `None`.',
'{"Writing `if 0 <= value is not None <= 100:` due to misunderstanding operator precedence.", "Using `!= None` instead of `is not None` (identity vs equality — None is a singleton, use identity)."}',
'1,3,7'),

-- ── 2.7 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111202', 'none_handling',
'Using None as Sentinel Value for Optional Parameters',
'def find_user(users, role=None):\n    if role is None:\n        return users\n    return [u for u in users if u.get("role") == role]',
'AI uses None as a sentinel to distinguish "no filter provided" from "filter by empty string."',
'[{"line": 1, "text": "Define function with ''role'' defaulting to None (sentinel value).", "type": "function_call"}, {"line": 2, "text": "Guard check: if role was not provided, return the full list unchanged.", "type": "guard"}, {"line": 3, "text": "Return full users list when role is None.", "type": "passthrough"}, {"line": 4, "text": "List comprehension filters users to those whose role field matches.", "type": "iterator"}]',
'`None` is used as a sentinel to distinguish "no filter provided" from "filter by empty string." Without this pattern, there is no way to differentiate between "return all users" and "return users with no role."',
'{"Using a mutable default argument like `users=[]` (a classic Python pitfall — the list is shared across calls).", "Confusing the sentinel check `is None` with the value check `== None` (always use `is None` for identity comparison)."}',
'1,2,4'),

-- ── 2.8 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111203', 'none_handling',
'Or Coalescing for Default Values',
'def greet(name):\n    display_name = name or "Anonymous"\n    return f"Hello, {display_name}!"',
'AI uses `or` coalescing as a concise way to provide default values for potentially missing data.',
'[{"line": 1, "text": "Define greet function taking a name parameter.", "type": "function_call"}, {"line": 2, "text": "Or coalescing: returns ''Anonymous'' if name is falsy (None, '''', 0, [], etc.).", "type": "coalesce"}, {"line": 2, "text": "IMPORTANT: or coalescing treats ALL falsy values as missing, not just None.", "type": "guard"}, {"line": 3, "text": "Build the formatted greeting string with the resolved display name.", "type": "function_call"}]',
'`name or "Anonymous"` returns `"Anonymous"` whenever `name` is falsy — including `None`, `""`, `0`, `[]`, and `False`. This is convenient for optional strings but can mask real bugs when the value could legitimately be an empty string or zero.',
'{"Using `or` to coalesce numeric defaults: `timeout or 30` — this breaks if `timeout = 0` is a valid value.", "Prefer the explicit `timeout if timeout is not None else 30` for numeric defaults."}',
'1,2,4'),

-- ── 2.9 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111204', 'none_handling',
'Ternary Conditional for None/Value Branch',
'def status_msg(records):\n    count = len(records) if records is not None else 0\n    return f"Found {count} record{"s" if count != 1 else ""}."',
'AI uses ternary conditionals to safely handle None inputs without verbose if/else blocks.',
'[{"line": 1, "text": "Define function taking records parameter.", "type": "function_call"}, {"line": 2, "text": "Ternary: use len() if records is not None, otherwise default to 0.", "type": "ternary"}, {"line": 2, "text": "Prevents TypeError from calling len(None).", "type": "guard"}, {"line": 3, "text": "Pluralize ''record'' only when count is not 1.", "type": "ternary"}, {"line": 3, "text": "Return the formatted status message.", "type": "passthrough"}]',
'The ternary conditional `x if condition else y` evaluates exactly one branch. `records if records is not None else 0` safely handles both `None` and empty lists while still getting the actual count for non-empty lists.',
'{"Using `len(records or [])` instead of the ternary — this works for falsy values but loses information if records is legitimately an empty list.", "Confusing the ternary syntax order — it is `value_if_true if condition else value_if_false`, not the C-style `condition ? true : false`."}',
'1,2,4'),

-- ── 2.10 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111301', 'async_await',
'Running Multiple Async Tasks Concurrently with asyncio.gather',
'import asyncio\n\nasync def fetch(url):\n    await asyncio.sleep(0.1)\n    return f"data from {url}"\n\nasync def main():\n    urls = ["a.com", "b.com", "c.com"]\n    results = await asyncio.gather(*[fetch(u) for u in urls])\n    print(results)',
'AI uses asyncio.gather to run multiple I/O-bound tasks concurrently instead of sequentially.',
'[{"line": 1, "text": "Import the asyncio module for async/await support.", "type": "side_effect"}, {"line": 3, "text": "Define an async function fetch — can be paused and resumed.", "type": "function_call"}, {"line": 4, "text": "asyncio.sleep() yields control back to the event loop, simulating an I/O wait.", "type": "async_wait"}, {"line": 6, "text": "Define the main async entry point.", "type": "function_call"}, {"line": 7, "text": "Bind the list of URLs.", "type": "assignment"}, {"line": 8, "text": "List comprehension creates three fetch coroutines — NOT yet executed.", "type": "iterator"}, {"line": 8, "text": "* unpacks the list into separate arguments; gather schedules all coroutines concurrently.", "type": "executor"}, {"line": 9, "text": "Print the list of results returned by all three coroutines.", "type": "side_effect"}]',
'`asyncio.gather(*coroutines)` runs all passed coroutines concurrently on a single thread. The event loop interleaves their await points. This is dramatically faster than `await`-ing each one sequentially (0.3s sequential vs 0.1s concurrent here).',
'{"Forgetting to `await` gather — the coroutines are created but never run.", "Passing coroutines directly vs. call expressions: `gather(fetch(u))` passes the coroutine object; `gather(*[fetch(u)])` actually calls each function."}',
'1,4,7'),

-- ── 2.11 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111302', 'async_await',
'Custom Async Context Manager with __aenter__ / __aexit__',
'import asyncio\n\nclass AsyncDatabase:\n    async def __aenter__(self):\n        self.conn = await asyncio.to_thread(self._connect)\n        return self\n\n    async def __aexit__(self, *args):\n        await asyncio.to_thread(self._close, self.conn)\n\n    def _connect(self):\n        return "db-connection-object"\n\n    def _close(self, conn):\n        pass\n\nasync def main():\n    async with AsyncDatabase() as db:\n        print(db.conn)',
'AI uses async context managers to properly manage async resources that need setup and teardown.',
'[{"line": 6, "text": "Define the async context manager class.", "type": "function_call"}, {"line": 7, "text": "__aenter__ is called on entry to ''async with''; runs before the block body.", "type": "enter"}, {"line": 8, "text": "to_thread runs the blocking _connect() in a thread pool, freeing the event loop.", "type": "executor"}, {"line": 9, "text": "__aexit__ runs after the block body completes — always, even on exception.", "type": "exit"}, {"line": 12, "text": "to_thread runs the blocking _close() asynchronously in a thread pool.", "type": "executor"}, {"line": 17, "text": "async with invokes __aenter__, passing the returned value (self) to ''db''.", "type": "async_cm"}, {"line": 18, "text": "Block body executes while the connection is open.", "type": "body"}, {"line": 19, "text": "On exiting the block, __aexit__ is automatically called to clean up.", "type": "cleanup"}]',
'`async with` is the async equivalent of `with`. Python calls `__aenter__` on entry and `__aexit__` on exit. Using `asyncio.to_thread` lets blocking I/O run without blocking the event loop.',
'{"Forgetting to `await` the operations inside `__aenter__` and `__aexit__` (they are async methods).", "Raising an exception inside the `async with` block — `__aexit__` still runs, but if it returns `True` the exception is suppressed."}',
'1,5,14'),

-- ── 2.12 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111303', 'async_await',
'Offloading Blocking CPU Work with asyncio.to_thread',
'import asyncio\nimport hashlib\n\ndef compute_hash(data: str) -> str:\n    return hashlib.sha256(data.encode()).hexdigest()\n\nasync def main():\n    data_chunks = ["chunk1", "chunk2", "chunk3"]\n    hashes = await asyncio.gather(*[\n        asyncio.to_thread(compute_hash, chunk) for chunk in data_chunks\n    ])\n    print(hashes)',
'AI uses asyncio.to_thread to offload CPU-bound work without blocking the async event loop.',
'[{"line": 1, "text": "Import asyncio for async concurrency primitives.", "type": "side_effect"}, {"line": 2, "text": "Import hashlib for CPU-bound SHA-256 computation.", "type": "side_effect"}, {"line": 4, "text": "Define a synchronous (blocking) CPU-bound function.", "type": "function_call"}, {"line": 7, "text": "Define the async entry point.", "type": "function_call"}, {"line": 8, "text": "Create the list of data chunks to hash.", "type": "assignment"}, {"line": 9, "text": "to_thread wraps each compute_hash call, running it in a thread pool.", "type": "offload"}, {"line": 9, "text": "gather runs all three thread-pool tasks concurrently.", "type": "executor"}, {"line": 10, "text": "Print the resulting list of SHA-256 hex strings.", "type": "side_effect"}]',
'CPU-bound work blocks the event loop if done directly inside async code. `asyncio.to_thread()` offloads the callable to a thread pool executor, allowing the event loop to continue running other async tasks while the CPU work happens in parallel.',
'{"Calling a CPU-bound function directly inside async code without `to_thread` — this blocks the entire event loop.", "Over-serializing with `await` in a loop instead of using `gather`."}',
'1,4,7'),

-- ── 2.13 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111401', 'decorators',
'Preserving Function Metadata with functools.wraps',
'import functools\n\ndef logged(func):\n    @functools.wraps(func)\n    def wrapper(*args, **kwargs):\n        print(f"Calling {func.__name__}")\n        return func(*args, **kwargs)\n    return wrapper\n\n@logged\ndef add(a, b):\n    """Add two numbers and return the result."""\n    return a + b',
'AI wraps functions with decorators and uses functools.wraps to preserve introspection metadata.',
'[{"line": 1, "text": "Import functools for the wraps utility.", "type": "side_effect"}, {"line": 3, "text": "Define the decorator function taking the original function as its argument.", "type": "function_call"}, {"line": 4, "text": "wraps copies __name__, __doc__, __module__, etc. from func to wrapper.", "type": "metadata_preservation"}, {"line": 5, "text": "wrapper wraps func — *args and **kwargs forward all arguments transparently.", "type": "function_call"}, {"line": 6, "text": "Side-effect: log the name of the function being called.", "type": "side_effect"}, {"line": 7, "text": "Forward the actual call to the original function.", "type": "passthrough"}, {"line": 8, "text": "Return the wrapper closure, which now replaces add.", "type": "assignment"}, {"line": 10, "text": "Decorator syntax: Python calls logged(add) and rebinds ''add'' to the result.", "type": "function_call"}]',
'`functools.wraps(func)` inside the wrapper ensures that metadata like `__name__`, `__doc__`, and `__annotations__` are copied from the original function to the wrapper. Without it, introspection tools, debuggers, and decorators higher in the stack see the wrapper''s metadata instead.',
'{"Forgetting `functools.wraps` and then debugging a stack trace that shows `wrapper` instead of the real function name.", "Forgetting to `return` the wrapper from the decorator (the function silently becomes `None`)."}',
'1,4,7'),

-- ── 2.14 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111402', 'decorators',
'Decorator with Arguments — Triple Layer Closure',
'import functools\n\ndef repeat(times):\n    def decorator(func):\n        @functools.wraps(func)\n        def wrapper(*args, **kwargs):\n            results = []\n            for _ in range(times):\n                results.append(func(*args, **kwargs))\n            return results\n        return wrapper\n    return decorator\n\n@repeat(times=3)\ndef greet(name):\n    return f"Hello, {name}!"',
'AI uses decorator factories (decorators with arguments) to create configurable wrapping behavior.',
'[{"line": 1, "text": "Import functools for wraps.", "type": "side_effect"}, {"line": 3, "text": "Outer closure: captures ''times'' argument.", "type": "closure_var"}, {"line": 4, "text": "Middle layer: receives the raw function being decorated.", "type": "function_call"}, {"line": 5, "text": "wraps preserves the original function''s metadata.", "type": "metadata_preservation"}, {"line": 6, "text": "Inner wrapper: loop that calls func ''times'' times, collecting all results.", "type": "iterator"}, {"line": 7, "text": "Call func with the forwarded arguments, append result to list.", "type": "function_call"}, {"line": 9, "text": "Return the wrapper closure.", "type": "assignment"}, {"line": 11, "text": "Return the decorator (second layer), completing the chain.", "type": "assignment"}, {"line": 13, "text": "Decorator syntax: repeat(3) returns decorator, which then receives greet.", "type": "function_call"}]',
'A decorator with arguments requires three nested functions: the outer accepts the decorator arguments, the middle receives the function, and the inner is the actual wrapper. This is a "decorator factory" pattern.',
'{"Writing `@repeat` instead of `@repeat(times=3)` (TypeError: repeat() missing required argument).", "Forgetting that `times` is captured from the outer scope (closure) — it is fixed at decoration time."}',
'1,5,14'),

-- ── 2.15 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111403', 'decorators',
'Class-Based Decorator Implementing __call__',
'import functools\n\nclass CountCalls:\n    def __init__(self, func):\n        functools.wraps(func)(self)\n        self._count = 0\n\n    def __call__(self, *args, **kwargs):\n        self._count += 1\n        print(f"Called {self._count} time(s)")\n        return self._func(*args, **kwargs)\n\n@CountCalls\ndef add(a, b):\n    return a + b',
'AI uses class-based decorators to maintain state across multiple calls cleanly.',
'[{"line": 1, "text": "Import functools for wraps.", "type": "side_effect"}, {"line": 3, "text": "Define the class-based decorator.", "type": "function_call"}, {"line": 4, "text": "__init__ is called at decoration time; receives the function to wrap.", "type": "enter"}, {"line": 5, "text": "wraps copies function metadata onto the CountCalls instance itself.", "type": "metadata_preservation"}, {"line": 6, "text": "Initialize counter to 0.", "type": "assignment"}, {"line": 8, "text": "__call__ is invoked each time the decorated function is called.", "type": "callable_sig"}, {"line": 9, "text": "Increment counter on each invocation.", "type": "mutation"}, {"line": 10, "text": "Print current call count.", "type": "side_effect"}, {"line": 11, "text": "Forward the call to the wrapped function and return its result.", "type": "passthrough"}]',
'A class-based decorator works by making the decorator instance callable. `__init__` receives the original function; `__call__` is invoked each time the decorated function is called. This pattern is useful when the decorator needs to maintain mutable state across calls.',
'{"Forgetting to store `func` as `self._func` in `__init__` (it gets overwritten).", "Forgetting `functools.wraps` in the class — the decorated function loses its original name and docstring."}',
'1,5,14'),

-- ── 2.16 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111501', 'oop',
'Abstract Base Class with Abstract Method Enforcement',
'from abc import ABC, abstractmethod\n\nclass Animal(ABC):\n    @abstractmethod\n    def speak(self) -> str:\n        raise NotImplementedError\n\nclass Dog(Animal):\n    def speak(self) -> str:\n        return "Woof!"\n\nclass Cat(Animal):\n    pass',
'AI uses ABC and @abstractmethod to enforce interface contracts in subclasses.',
'[{"line": 1, "text": "Import ABC and abstractmethod from the abc module.", "type": "side_effect"}, {"line": 3, "text": "Define Animal as an abstract base class.", "type": "abc"}, {"line": 4, "text": "@abstractmethod marks speak() as required — subclasses MUST implement it.", "type": "enforcement"}, {"line": 5, "text": "The body raises NotImplementedError if called directly (should never be called).", "type": "rollback"}, {"line": 7, "text": "Dog inherits from Animal and implements speak().", "type": "contract"}, {"line": 9, "text": "Cat inherits from Animal but fails to implement speak().", "type": "contract"}, {"line": 10, "text": "TypeError raised at instantiation time, not at definition time.", "type": "validation"}]',
'`ABC` and `@abstractmethod` enforce a contract: any subclass of `Animal` must implement `speak()`. Python raises `TypeError` at instantiation time if the abstract method is not overridden. This is compile-time-like enforcement in a dynamically-typed language.',
'{"Instantiating a subclass that forgot to implement the abstract method (raises `TypeError` at instantiation, not definition).", "Confusing `ABC` with `Protocol` from typing — `ABC` requires inheritance; `Protocol` is for structural subtyping."}',
'1,5,14'),

-- ── 2.17 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111502', 'oop',
'Dataclass with __post_init__ for Computed Fields',
'from dataclasses import dataclass, field\n\n@dataclass\nclass Rectangle:\n    width:  int\n    height: int\n    area:   int = field(init=False)\n\n    def __post_init__(self):\n        object.__setattr__(self, "area", self.width * self.height)\n\nr = Rectangle(width=10, height=5)\nprint(r.area)',
'AI uses dataclasses with __post_init__ to automatically compute derived fields.',
'[{"line": 1, "text": "Import dataclass decorator and field from dataclasses.", "type": "side_effect"}, {"line": 4, "text": "@dataclass generates __init__, __repr__, __eq__, __hash__ automatically.", "type": "factory"}, {"line": 5, "text": "Define width and height as required fields.", "type": "parameterized"}, {"line": 6, "text": "area is declared with init=False — it is not a constructor parameter.", "type": "parameterized"}, {"line": 8, "text": "__post_init__ runs after the generated __init__ but before the object is returned.", "type": "init"}, {"line": 9, "text": "object.__setattr__ bypasses dataclass field immutability check to set area.", "type": "mutation"}]',
'`@dataclass` generates boilerplate `__init__`, `__repr__`, `__eq__` automatically. `__post_init__` runs after `__init__` and lets you compute derived fields. Using `object.__setattr__` is necessary because dataclasses make fields immutable by default.',
'{"Trying to assign to `self.area = ...` inside `__post_init__` when `frozen=True` — must use `object.__setattr__`.", "Declaring `area: int` as a regular field (not `init=False`) and then overwriting it in `__post_init__`."}',
'1,5,14'),

-- ── 2.18 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111503', 'oop',
'Mixin Class for Reusable Cross-Cutting Behavior',
'class LoggedMixin:\n    def log(self, msg: str) -> None:\n        print(f"[LOG] {msg}")\n\nclass Service(LoggedMixin):\n    def run(self) -> None:\n        self.log("Service started")\n        print("Doing work...")\n        self.log("Service done")\n\nclass Tool(LoggedMixin):\n    def execute(self) -> None:\n        self.log("Tool executing")',
'AI uses mixins to share behavior across unrelated classes without inheritance hierarchy conflicts.',
'[{"line": 1, "text": "Define the mixin — provides log() to any class that inherits it.", "type": "mixin"}, {"line": 2, "text": "Mixin method for logging messages.", "type": "function_call"}, {"line": 4, "text": "Service inherits from LoggedMixin — gets log() for free.", "type": "mixin_usage"}, {"line": 5, "text": "Service defines its own run() method.", "type": "function_call"}, {"line": 6, "text": "Mixin method called within Service''s method.", "type": "self_reflection"}, {"line": 10, "text": "Tool also uses the same mixin — DRY: log() is defined only once.", "type": "mixin_usage"}]',
'A mixin is a class that provides methods to other classes through multiple inheritance, without being intended to stand alone. It encapsulates cross-cutting behavior (like logging) that multiple unrelated classes share.',
'{"Forgetting that mixins should not call `super().__init__()` unless designed to cooperate with the MRO.", "Defining `__init__` in a mixin (mixins should only add methods, not initialization logic)."}',
'1,5,14'),

-- ── 2.19 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111601', 'type_hints',
'Callable Type Hint for Callback Parameters',
'from typing import Callable\n\ndef apply_twice(func: Callable[[int], int], value: int) -> int:\n    return func(func(value))\n\ndef add_five(x: int) -> int:\n    return x + 5\n\nresult = apply_twice(add_five, 0)',
'AI annotates higher-order functions with Callable to document callback signatures clearly.',
'[{"line": 1, "text": "Import Callable from typing for higher-order function type hints.", "type": "side_effect"}, {"line": 3, "text": "Define apply_twice: takes a callable (int -> int) and an int, returns int.", "type": "function_call"}, {"line": 3, "text": "Callable[[int], int] means: accepts one int argument, returns an int.", "type": "callable_sig"}, {"line": 4, "text": "Call func twice: inner call with value, outer call with the result.", "type": "nested_call"}, {"line": 6, "text": "Define add_five as a concrete implementation of Callable[[int], int].", "type": "function_call"}, {"line": 8, "text": "apply_twice(add_five, 0): first add_five(0)=5, then add_five(5)=10.", "type": "nested_call"}]',
'`Callable[[ArgType, ...], ReturnType]` is the standard way to annotate functions that accept other functions as arguments. The list inside `Callable` describes the argument types the callable must accept; the final type is the return type.',
'{"Writing `Callable[int, int]` instead of `Callable[[int], int]` — the outer brackets are required.", "Forgetting that `Callable[..., R]` with `...` means ''any arguments'' — the ellipsis is a valid type."}',
'1,4,7'),

-- ── 2.20 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111602', 'type_hints',
'Generic Type Variable for Type-Safe Container Operations',
'from typing import TypeVar, Generic\n\nT = TypeVar("T")\n\nclass Stack(Generic[T]):\n    def __init__(self) -> None:\n        self._items: list[T] = []\n\n    def push(self, item: T) -> None:\n        self._items.append(item)\n\n    def pop(self) -> T:\n        return self._items.pop()\n\nnums: Stack[int] = Stack()\nnums.push(42)\nvalue: int = nums.pop()',
'AI uses TypeVar and Generic to create type-safe generic containers.',
'[{"line": 1, "text": "Import TypeVar for generic type variables and Generic for generic classes.", "type": "side_effect"}, {"line": 3, "text": "T is an unconstrained TypeVar — can be bound to any type.", "type": "typevar"}, {"line": 5, "text": "Stack is parameterized over T — each instantiation fixes T to a concrete type.", "type": "parameterized"}, {"line": 8, "text": "push accepts an item of type T (determined by how the Stack was instantiated).", "type": "parameterized"}, {"line": 11, "text": "pop returns a T — type checker enforces that callers use the returned value correctly.", "type": "generic_class"}, {"line": 13, "text": "Instantiate Stack bound to int — all T positions become int.", "type": "generic_class"}, {"line": 14, "text": "push(42) is type-correct: int is valid for Stack[int].", "type": "validation"}, {"line": 15, "text": "Assigning pop() result to int; type checker confirms T=int at this instantiation.", "type": "validation"}]',
'`TypeVar` and `Generic` enable parametric polymorphism in Python''s type system. When you write `Stack[int]`, the type checker enforces that all `T` positions in the class are treated as `int`.',
'{"Instantiating `Stack()` without a type parameter (becomes `Stack[Any]`, losing all type safety).", "Forgetting that `list[T]` inside the class needs the same type variable."}',
'1,5,14'),

-- ── 2.21 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111701', 'context_managers',
'@contextmanager Decorator for Automatic Resource Cleanup',
'from contextlib import contextmanager\n\n@contextmanager\ndef managed_file(path, mode="r"):\n    f = open(path, mode)\n    try:\n        yield f\n    finally:\n        f.close()\n\nwith managed_file("data.txt") as fh:\n    print(fh.read())',
'AI uses @contextmanager as a cleaner alternative to full class-based context managers.',
'[{"line": 1, "text": "Import contextmanager from contextlib.", "type": "side_effect"}, {"line": 3, "text": "@contextmanager transforms a generator into a context manager.", "type": "factory"}, {"line": 4, "text": "Generator sets up the resource (opens the file).", "type": "enter"}, {"line": 5, "text": "open() acquires the file handle.", "type": "side_effect"}, {"line": 6, "text": "try block: yield passes control to the with-block body, returning fh.", "type": "yield"}, {"line": 8, "text": "finally block: ALWAYS runs, even if an exception occurs — ensures cleanup.", "type": "cleanup"}, {"line": 9, "text": "Close the file handle, releasing the OS resource.", "type": "cleanup"}, {"line": 11, "text": "with assigns fh from the yield value; reads file while it is open.", "type": "body"}, {"line": 12, "text": "On exiting the with block, the finally block runs — file is guaranteed closed.", "type": "exit"}]',
'`@contextmanager` turns a generator function into a context manager. The code before `yield` runs on `__aenter__` (entry); the code after `yield` in the `finally` block runs on `__aexit__` (exit). This avoids writing a full class for simple resource management.',
'{"Forgetting the `finally` block — if the `with` body raises an exception, the file handle leaks.", "Using `yield` outside of a `try/finally` entirely."}',
'1,3,7'),

-- ── 2.22 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111702', 'context_managers',
'Context Manager for Database Transaction with Rollback',
'class Transaction:\n    def __init__(self, conn):\n        self.conn = conn\n        self._committed = False\n\n    def __enter__(self):\n        self.conn.execute("BEGIN")\n        return self\n\n    def __exit__(self, exc_type, exc_val, exc_tb):\n        if exc_type is not None:\n            self.conn.execute("ROLLBACK")\n            return False\n        self.conn.execute("COMMIT")\n        self._committed = True\n        return False\n\nwith Transaction(conn) as tx:\n    tx.conn.execute("UPDATE accounts SET balance = balance - 100")\n    tx.conn.execute("UPDATE accounts SET balance = balance + 100")',
'AI uses context managers for database transactions to ensure automatic rollback on failure.',
'[{"line": 1, "text": "Define the Transaction context manager class.", "type": "function_call"}, {"line": 3, "text": "__enter__: begins the database transaction.", "type": "begin"}, {"line": 8, "text": "__exit__ is called when leaving the with block.", "type": "exit"}, {"line": 9, "text": "If an exception occurred: execute ROLLBACK to undo all changes in this transaction.", "type": "rollback"}, {"line": 10, "text": "Return False so the exception is re-raised to the caller.", "type": "rollback"}, {"line": 12, "text": "No exception: commit makes all changes permanent.", "type": "commit"}, {"line": 14, "text": "Return False to not suppress any exception.", "type": "exit"}, {"line": 16, "text": "Two UPDATE statements run atomically within the transaction.", "type": "executor"}]',
'The transaction context manager ensures atomicity: either both UPDATE statements succeed and are committed, or an exception causes a rollback. The `return False` from `__exit__` does NOT suppress the exception — it is required to re-raise it.',
'{"Returning `True` from `__exit__` to suppress the exception (hides bugs).", "Forgetting to issue `ROLLBACK` in the exception branch (partial changes persist)."}',
'1,5,14'),

-- ── 2.23 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111703', 'context_managers',
'Async Context Manager for Network Connection Pool',
'import asyncio\n\nclass AsyncPool:\n    async def __aenter__(self):\n        self.connections = await asyncio.Queue()\n        for _ in range(5):\n            await self.connections.put("conn-object")\n        return self\n\n    async def __aexit__(self, *args):\n        while not self.connections.empty():\n            conn = await self.connections.get()\n            await conn.close()\n\nasync def main():\n    async with AsyncPool() as pool:\n        conn = await pool.connections.get()\n        await conn.query("SELECT 1")\n        await pool.connections.put(conn)',
'AI uses async context managers to safely manage async network resources.',
'[{"line": 1, "text": "Import asyncio for async/await support.", "type": "side_effect"}, {"line": 3, "text": "Define the async context manager class.", "type": "function_call"}, {"line": 4, "text": "__aenter__ runs on entry; initializes the connection pool.", "type": "enter"}, {"line": 5, "text": "Create an async queue to hold pooled connection objects.", "type": "factory"}, {"line": 6, "text": "Pre-populate the pool with 5 connection objects.", "type": "iterator"}, {"line": 7, "text": "Return self to be bound in the ''as pool'' clause.", "type": "passthrough"}, {"line": 9, "text": "__aexit__ runs on exit; drains and closes all connections.", "type": "exit"}, {"line": 10, "text": "Loop until the pool is empty.", "type": "iterator"}, {"line": 11, "text": "Get and close each connection in turn.", "type": "cleanup"}]',
'Async context managers are needed when the entry or exit requires async operations (like network I/O). The `async with` statement awaits both `__aenter__` and `__aexit__`.',
'{"Using `with` instead of `async with` (TypeError).", "Forgetting to `await` operations inside `__aenter__` and `__aexit__`."}',
'1,5,14'),

-- ── 2.24 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111801', 'closures',
'Nonlocal Variable Capture in a Counter Closure',
'def make_counter(start=0):\n    count = start\n\n    def increment(delta=1):\n        nonlocal count\n        count += delta\n        return count\n\n    return increment\n\ncounter = make_counter(10)\nprint(counter())\nprint(counter(5))\nprint(counter(-2))',
'AI uses nonlocal to create closures that mutate captured variables.',
'[{"line": 1, "text": "Define factory function that creates a counter closure.", "type": "function_call"}, {"line": 2, "text": "Initialize count in the enclosing scope — captured by the inner function.", "type": "closure_var"}, {"line": 3, "text": "Define the inner increment function.", "type": "function_call"}, {"line": 5, "text": "nonlocal declares count as mutable from the enclosing scope.", "type": "nonlocal"}, {"line": 6, "text": "Assign to count: increments it by delta in the enclosing scope.", "type": "mutation"}, {"line": 7, "text": "Return the updated count.", "type": "passthrough"}, {"line": 9, "text": "Factory creates one closure instance with count=10.", "type": "factory"}, {"line": 10, "text": "First call: count becomes 10+1=11.", "type": "mutation"}, {"line": 11, "text": "Second call: count becomes 11+5=16.", "type": "mutation"}]',
'`nonlocal count` tells Python to look up `count` in the enclosing (non-global, non-local) scope rather than creating a new local variable. Without `nonlocal`, the assignment `count += delta` would create a new local variable, raising `UnboundLocalError`.',
'{"Forgetting `nonlocal` and getting `UnboundLocalError: local variable ''count'' referenced before assignment`.", "Using this pattern with mutable values (lists, dicts) where `nonlocal` is not needed but confusion arises."}',
'1,3,7'),

-- ── 2.25 ──────────────────────────────────────────────────
('11111111-1111-1111-1111-111111111802', 'closures',
'functools.partial for Partial Function Application',
'from functools import partial\n\ndef power(base, exponent):\n    return base ** exponent\n\nsquare = partial(power, exponent=2)\ncube   = partial(power, exponent=3)\n\nprint(square(5))\nprint(cube(5))',
'AI uses functools.partial to create specialized functions from generic ones.',
'[{"line": 1, "text": "Import partial from functools.", "type": "side_effect"}, {"line": 3, "text": "Define the power function: takes base and exponent, returns base ** exponent.", "type": "function_call"}, {"line": 5, "text": "partial creates a new callable with exponent=2 pre-bound.", "type": "partial"}, {"line": 6, "text": "partial creates a new callable with exponent=3 pre-bound.", "type": "partial"}, {"line": 8, "text": "square(5) calls power(5, exponent=2) = 5**2 = 25.", "type": "function_call"}, {"line": 9, "text": "cube(5) calls power(5, exponent=3) = 5**3 = 125.", "type": "function_call"}]',
'`functools.partial` creates a new callable with some arguments pre-filled. It is a factory function that returns a callable object. This is cleaner than defining wrapper functions manually.',
'{"Confusing `partial(power, exponent=2)` with `partial(power, 2)` — the latter binds `base=2`, not `exponent=2`.", "Passing mutable objects as defaults to partial (the partial object stores them by reference)."}',
'1,3,7');

COMMIT;
