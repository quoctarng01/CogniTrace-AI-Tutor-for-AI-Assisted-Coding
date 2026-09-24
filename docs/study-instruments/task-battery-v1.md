# Task Battery v1 — CS1 Debugging Tasks for Automated Evaluation

**Version:** 1.0
**Date:** 2026-09-23
**Author:** Generated for CogniTrace empirical study
**Status:** Draft — requires expert review before use

---

## Design Principles

1. **CS1-appropriate difficulty** — solvable in 3–8 minutes by a student who understands variables, conditionals, loops, and functions.
2. **One bug per task** — clean fault localization, no multi-fault cascades.
3. **Distinct bug categories** — no two tasks test the same concept.
4. **Verifiable fix** — the buggy line is known; the judge can confirm the fix.
5. **Transfer task** — each task has a "novel program" using the same concept, so we can measure whether understanding transfers.
6. **Automatable rubric** — the LLM-as-judge can score correctness without human intervention.

---

## Task Structure (per task)

Each task contains:

```yaml
task_id:        string   # e.g. "B01"
title:          string   # short descriptive name
concept:        string   # CS1 concept category
difficulty:     string   # easy | medium
time_estimate:  string   # expected fix time for CS1 student
difficulty_tags:         # multiple possible
  - conditional_logic
  - loop_semantics
  - function_arguments

buggy_code:     string   # the broken Python program
fixed_code:     string   # the corrected version
bug_line:       int      # 1-indexed line number of the bug
bug_description: string  # plain-English description of what goes wrong
bug_category:   string   # logic_error | off_by_one | mutable_default | short_circuit | type_error | exception_handling

transfer_task:
  code:         string   # new program using the same concept (bug-free)
  question:     string   # what the "student" should identify
  expected_answer: string # what correct debugging reasoning looks like
  rubric:       dict     # LLM judge rubric

llm_judge_prompt: string  # exact prompt fed to GPT-4o to score the response
max_score:     int       # maximum achievable score
pass_threshold: float    # score ≥ threshold → "bug successfully identified and fixed"
```

---

## Task B01 — Off-by-One in Range Loop

### Metadata

```yaml
task_id: B01
title: "Off-by-One in Range Loop"
concept: loop_semantics / off_by_one
difficulty: easy
time_estimate: 3–5 minutes
difficulty_tags: [loop_semantics, off_by_one, range_function]
```

### Buggy Code

```python
def sum_first_n(n):
    total = 0
    for i in range(1, n):       # BUG: should be range(1, n + 1)
        total = total + i
    return total

# Test
result = sum_first_n(5)
print(f"Sum of 1 to 5: {result}")  # Expected: 15, Got: 10
```

**Bug line:** 3
**Bug description:** `range(1, n)` excludes `n`, so `sum_first_n(5)` sums 1+2+3+4 = 10 instead of 1+2+3+4+5 = 15.

### Fixed Code

```python
def sum_first_n(n):
    total = 0
    for i in range(1, n + 1):   # FIXED
        total = total + i
    return total

result = sum_first_n(5)
print(f"Sum of 1 to 5: {result}")  # 15
```

### Transfer Task

```python
# New program: find the average of the first k integers
def average_first_k(k):
    total = 0
    for i in range(1, k):       # same bug pattern
        total = total + i
    return total / k

# Question: What is wrong? Fix it.
# Expected answer: range(1, k) should be range(1, k + 1)
# to include k in the average.
```

### LLM Judge Rubric

```
Score 2 — Correct: identifies range(1, k) excludes k, fixes to range(1, k + 1)
Score 1 — Partial: identifies the loop produces wrong values but doesn't pinpoint range
Score 0 — Incorrect: no relevant diagnosis
```

---

## Task B02 — Mutable Default Argument

### Metadata

```yaml
task_id: B02
title: "Mutable Default Argument"
concept: mutable_default_argument / function_arguments
difficulty: medium
time_estimate: 5–8 minutes
difficulty_tags: [function_arguments, mutable_default, list_semantics]
```

### Buggy Code

```python
def add_student(name, roster=[]):   # BUG: mutable default argument
    roster.append(name)
    return roster

# Test
class_a = add_student("Alice")
class_b = add_student("Bob")
print(f"Class A: {class_a}")   # Expected: ['Alice'], Got: ['Alice', 'Bob']
print(f"Class B: {class_b}")   # Expected: ['Bob'], Got: ['Alice', 'Bob']
```

**Bug line:** 1
**Bug description:** `roster=[]` creates a single shared list across all calls. On the second call, the list already contains 'Alice', so 'Bob' is appended to the same list. Both `class_a` and `class_b` point to the same object.

### Fixed Code

```python
def add_student(name, roster=None):   # FIXED: use None sentinel
    if roster is None:
        roster = []
    roster.append(name)
    return roster

class_a = add_student("Alice")
class_b = add_student("Bob")
print(f"Class A: {class_a}")   # ['Alice']
print(f"Class B: {class_b}")   # ['Bob']
```

### Transfer Task

```python
# New program: collect errors in a log
def log_error(message, errors=[]):   # same mutable default bug pattern
    errors.append(message)
    return errors

log_a = log_error("File not found")
log_b = log_error("Permission denied")
# Question: What is wrong with this function?
# Expected answer: mutable default argument; use errors=None and initialize inside
```

### LLM Judge Rubric

```
Score 2 — Correct: identifies mutable default argument (roster=[]) causes shared state,
           fixes by using roster=None and initializing inside
Score 1 — Partial: notices that class_a and class_b share values but misattributes cause
Score 0 — Incorrect: no relevant diagnosis
```

---

## Task B03 — Short-Circuit Evaluation with `or`

### Metadata

```yaml
task_id: B03
title: "Short-Circuit 'or' Misuse"
concept: short_circuit / boolean_logic
difficulty: medium
time_estimate: 4–7 minutes
difficulty_tags: [boolean_logic, short_circuit, conditional_logic]
```

### Buggy Code

```python
def get_default_name(name):
    if name or "Guest":   # BUG: name or "Guest" returns name if truthy
        return name      # always returns the actual name, never "Guest"
    return "Guest"

# Test
print(get_default_name(""))    # Expected: "Guest", Got: "" (empty string)
print(get_default_name("Bob"))  # Expected: "Bob", Got: "Bob"  ✓
```

**Bug line:** 2
**Bug description:** `name or "Guest"` evaluates to `name` when `name` is truthy, and `"Guest"` when `name` is falsy. But `if name or "Guest":` then returns `name` regardless — which is `""` (empty string) when name is falsy. The intent was `name if name else "Guest"`.

### Fixed Code

```python
def get_default_name(name):
    if name:              # FIXED: check truthiness first
        return name
    return "Guest"

print(get_default_name(""))    # "Guest"
print(get_default_name("Bob")) # "Bob"
```

### Transfer Task

```python
# New program: validate a username
def validate_username(username):
    if username or "invalid":  # same bug pattern
        return username
    return "invalid"

# Question: This function should return "invalid" for empty input.
# What is wrong?
# Expected answer: conditional logic with 'or' — should use if username: / else: / return
#                 or the expression itself should be: username if username else "invalid"
```

### LLM Judge Rubric

```
Score 2 — Correct: identifies that `name or "Guest"` inside if-statement returns name
           regardless of truthiness; fixes with explicit if/else or correct expression
Score 1 — Partial: identifies that empty string case is wrong but doesn't explain the or-logic
Score 0 — Incorrect: no relevant diagnosis
```

---

## Task B04 — List Mutation During Iteration

### Metadata

```yaml
task_id: B04
title: "List Mutation During Iteration"
concept: mutation_during_iteration / loop_semantics
difficulty: medium-hard
time_estimate: 5–8 minutes
difficulty_tags: [loop_semantics, list_mutation, iterator_behavior]
```

### Buggy Code

```python
def remove_negatives(nums):
    for num in nums:            # BUG: modifying list while iterating over it
        if num < 0:
            nums.remove(num)   # skips the next element after removal
    return nums

# Test
data = [1, -2, 3, -4, 5]
print(remove_negatives(data))   # Expected: [1, 3, 5], Got: [1, 3, -4]
```

**Bug line:** 3
**Bug description:** Removing an element from `nums` during iteration shifts all subsequent elements one position left, causing the iterator to skip the element after the removed one. `-4` is skipped because after removing `-2`, the iterator moves to what was at index 2 (`3`), then index 3 (`-4`) is treated as already visited.

### Fixed Code

```python
def remove_negatives(nums):
    return [num for num in nums if num >= 0]   # FIXED: build new list

# Alternative fix:
def remove_negatives_v2(nums):
    result = []
    for num in nums:
        if num >= 0:
            result.append(num)
    return result
```

### Transfer Task

```python
# New program: remove all strings from a mixed list
def filter_strings(items):
    for item in items:
        if isinstance(item, str):
            items.remove(item)   # same mutation-during-iteration bug
    return items

# Test
data = ["a", 1, "b", 2, "c"]
# Question: What will this return? What is the bug?
# Expected answer: mutation during iteration causes skips; should use list comprehension
```

### LLM Judge Rubric

```
Score 2 — Correct: identifies that modifying a list while iterating skips elements;
           fixes with list comprehension or separate list
Score 1 — Partial: notices wrong output but attributes to wrong logic rather than mutation
Score 0 — Incorrect: no relevant diagnosis
```

---

## Task B05 — Accidental Variable Shadowing

### Metadata

```yaml
task_id: B05
title: "Variable Shadowing in Nested Scope"
concept: variable_shadowing / scoping
difficulty: easy-medium
time_estimate: 3–6 minutes
difficulty_tags: [variable_shadowing, scoping, function_arguments]
```

### Buggy Code

```python
PI = 3.14159

def circle_area(radius):
    PI = 3        # BUG: local PI shadows global PI; this is a typo/confusion
    return PI * radius ** 2

def circle_circumference(radius):
    return 2 * PI * radius   # Uses global PI correctly: 3.14159

# Test
print(f"Area: {circle_area(2):.2f}")        # Expected: 12.57, Got: 12.00
print(f"Circumference: {circle_circumference(2):.2f}")  # 12.57  ✓
```

**Bug line:** 3
**Bug description:** `PI = 3` inside `circle_area` creates a local variable that shadows the global `PI = 3.14159`. The function uses `PI = 3`, not the global value.

### Fixed Code

```python
PI = 3.14159

def circle_area(radius):
    # FIXED: remove the local assignment; use global PI
    return PI * radius ** 2

def circle_circumference(radius):
    return 2 * PI * radius
```

### Transfer Task

```python
# New program: calculate discount
DISCOUNT = 0.1

def apply_discount(price, discount=DISCOUNT):
    discount = 0.05  # same shadowing bug — local variable shadows parameter default
    return price * (1 - discount)

# Test
print(apply_discount(100))  # Expected: 90.00 (10% off), Got: 95.00 (5% off)
# Question: What is the bug?
# Expected answer: local assignment shadows the parameter/discount value;
#                  remove the local assignment
```

### LLM Judge Rubric

```
Score 2 — Correct: identifies variable shadowing — local PI/discount shadows the global/parameter;
           fixes by removing the local assignment
Score 1 — Partial: identifies wrong output but doesn't explain the scoping cause
Score 0 — Incorrect: no relevant diagnosis
```

---

## Task B06 — Bare `except` Masking Specific Errors

### Metadata

```yaml
task_id: B06
title: "Bare except Masks All Errors"
concept: exception_handling / error_diagnosis
difficulty: easy-medium
time_estimate: 3–5 minutes
difficulty_tags: [exception_handling, error_diagnosis, debugging]
```

### Buggy Code

```python
def safe_divide(a, b):
    try:
        result = a / b
        return result
    except:                    # BUG: catches everything including KeyboardInterrupt
        return "Error"        # hides the real problem

# Test
print(safe_divide(10, 2))    # 5.0  ✓
print(safe_divide(10, 0))      # "Error"  ← correct behavior, but hides TypeError too
print(safe_divide("10", 2))   # "Error"  ← but this is TypeError, not ZeroDivisionError!
```

**Bug line:** 5
**Bug description:** `except:` catches *all* exceptions — `ZeroDivisionError`, `TypeError`, `ValueError`, `KeyboardInterrupt`, and `SystemExit`. The programmer should catch `ZeroDivisionError` specifically so that a `TypeError` (wrong input type) is not silently swallowed.

### Fixed Code

```python
def safe_divide(a, b):
    try:
        result = a / b
        return result
    except ZeroDivisionError:   # FIXED: specific exception
        return "Error: division by zero"
    except TypeError:
        return "Error: both arguments must be numeric"
```

### Transfer Task

```python
# New program: parse a number from user input
def parse_number(user_input):
    try:
        return int(user_input)
    except:                         # same bare except bug
        return None

# Test
parse_number("42")    # 42  ✓
parse_number("abc")    # None  ← correct
parse_number([])       # None  ← TypeError hidden — should say "expected string"
# Question: What is wrong with this exception handling?
# Expected answer: bare except catches everything; should catch specific exceptions
```

### LLM Judge Rubric

```
Score 2 — Correct: identifies bare except catches all exceptions including non-errors;
           fixes by catching specific exceptions (ZeroDivisionError, TypeError)
Score 1 — Partial: notices that some errors are hidden but doesn't identify bare except
Score 0 — Incorrect: no relevant diagnosis
```

---

## LLM Judge Evaluation Framework

### Judge Prompt Template

```python
JUDGE_SYSTEM_PROMPT = """You are an expert CS1 instructor evaluating debugging responses.
Score the student's debugging work on a scale of 0–2:

Score 2 (EXCELLENT): Correctly identifies the bug, explains why it causes the wrong
  behavior, and provides the correct fix.

Score 1 (PARTIAL): Identifies that something is wrong but misattributes the cause,
  or identifies the correct fix without explaining the mechanism.

Score 0 (INCORRECT): No relevant diagnosis, or diagnosis is clearly wrong.

Respond in JSON format only:
{
  "score": 0 | 1 | 2,
  "reasoning": "one sentence explaining the score",
  "bug_identified": "what the student correctly identified (or 'none')",
  "fix_provided": "whether the fix was correct (yes/no/partial)"
}
"""
```

### Automated Evaluation Script

For each task and each condition (A / B / C):

1. Feed the **buggy code** to the tool being evaluated.
2. Ask for a **debugging explanation**.
3. Feed the explanation + the **buggy code** and ask for a **fix**.
4. Run the **LLM judge prompt** against the student's fix + the **fixed code**.
5. Record: `{task_id, condition, score, reasoning}`.

### Condition Simulation Prompts

**Condition A (Python Tutor baseline):**
> "You have a Python code visualization tool. Run this code step-by-step and observe the output. Identify any bugs."
> [Buggy code]

**Condition B (Ungrounded LLM chat):**
> "You are a helpful coding assistant. The following Python code has a bug. Identify and fix it."
> [Buggy code]

**Condition C (CogniTrace — trace-grounded):**
> "You are a CogniTrace tutor. The following Python code was executed step-by-step.
> Runtime state at each line: [captured trace frames]
> Identify and fix the bug. Reference the specific runtime values when explaining."
> [Buggy code + simulated trace frames]

---

## Summary Table

| ID | Concept | Difficulty | Est. Time | Bug Category |
|----|---------|-----------|-----------|-------------|
| B01 | Off-by-one in range | Easy | 3–5 min | off_by_one |
| B02 | Mutable default argument | Medium | 5–8 min | mutable_default |
| B03 | Short-circuit `or` misuse | Medium | 4–7 min | short_circuit |
| B04 | List mutation during iteration | Medium-Hard | 5–8 min | mutation_iteration |
| B05 | Variable shadowing | Easy-Medium | 3–6 min | variable_shadowing |
| B06 | Bare `except` masking errors | Easy-Medium | 3–5 min | exception_handling |

---

## Pre-Registration

These 6 tasks and their rubrics are fixed before the automated evaluation runs. No task will be changed, added, or removed after evaluation begins. If a task is found to be defective (e.g., multiple valid interpretations), it will be noted as a threat to validity rather than modified.

**Registered at:** `docs/THESIS-00-RESEARCH-QUESTIONS.md` §7
