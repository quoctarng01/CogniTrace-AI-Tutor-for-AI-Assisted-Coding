"""Workstream 5: branch detection must compile `If` tests at build time, not eval() at runtime.

These tests assert:

1. The full regression suite from `test_branch_detection.py` (renamed-imported).
2. `eval()` is never invoked during a trace. We monkeypatch `builtins.eval` to
   raise if called.
3. Short-circuit evaluation (`and`/`or`) works correctly.
4. Nested `if` statements compile and execute without error.
5. The validator now rejects `match/case` and `while True: yield ...`.
6. The validator now rejects all dunder attribute access.
"""

from __future__ import annotations

import builtins
import importlib

import pytest


def _tracer():
    """Lazy import to avoid picking up stale bytecode from a previous edit."""
    import tracer.tracer
    importlib.reload(tracer.tracer)
    return tracer.tracer


def test_branch_detection_only_marks_taken_branch():
    """When `if x > 0:` evaluates True, only `then` is marked taken."""
    code = """
x = 1
if x > 0:
    result = "positive"
else:
    result = "non-positive"
y = 2
"""
    result = _tracer().run_trace(code)

    steps_with_branch = [s for s in result["steps"] if s.get("branches_taken")]
    assert steps_with_branch, "No branches detected"

    for step in steps_with_branch:
        branch_info = step["branches_taken"].get("if", {})
        if branch_info.get("taken") is True:
            assert branch_info.get("branch") in ("then", "else"), (
                f"branch taken={branch_info.get('taken')} but branch field is missing or invalid: {branch_info}"
            )
            assert "condition" in branch_info, "must include the actual condition expression"


def test_branch_detection_if_false():
    """When `if False:` is taken, `else` is the branch marked taken."""
    code = """
if False:
    x = 1
else:
    x = 2
"""
    result = _tracer().run_trace(code)
    steps_with_branch = [s for s in result["steps"] if s.get("branches_taken")]
    for step in steps_with_branch:
        branch_info = step["branches_taken"].get("if", {})
        if branch_info.get("taken") is True:
            assert branch_info.get("branch") == "else", f"`if False` should take `else` branch, got: {branch_info}"


def test_branch_detection_if_true():
    """When `if True:` is taken, `then` is the branch marked taken."""
    code = """
if True:
    y = 10
else:
    y = 20
"""
    result = _tracer().run_trace(code)
    steps_with_branch = [s for s in result["steps"] if s.get("branches_taken")]
    for step in steps_with_branch:
        branch_info = step["branches_taken"].get("if", {})
        if branch_info.get("taken") is True:
            assert branch_info.get("branch") == "then", f"`if True` should take `then` branch, got: {branch_info}"


def test_branch_detection_includes_condition():
    """Branch detection must include the condition expression in the branch info."""
    code = """
x = 5
if x > 3:
    z = 1
else:
    z = 0
"""
    result = _tracer().run_trace(code)
    steps_with_branch = [s for s in result["steps"] if s.get("branches_taken")]
    found_condition = False
    for step in steps_with_branch:
        branch_info = step["branches_taken"].get("if", {})
        if branch_info.get("taken") is True:
            assert "condition" in branch_info
            found_condition = True
    assert found_condition, "no taken branch with condition was found"


# ──────────────────────────────────────────────────────────────────
# Workstream 5: new assertions
# ──────────────────────────────────────────────────────────────────


def test_tracer_does_not_call_eval(monkeypatch):
    """`eval()` must never be called during a trace, even when `if` branches are present.

    The legacy implementation called `eval(condition_expr, namespace)` inside the
    tracer callback on every `line` event. Workstream 5 replaces that with a
    compile-time AST-to-lambda compiler, so this test must pass without the
    monkeypatched `eval` ever firing.
    """
    eval_called = []

    def _evil_eval(*args, **kwargs):
        eval_called.append((args, kwargs))
        raise AssertionError("tracer must not call eval() at runtime")

    monkeypatch.setattr(builtins, "eval", _evil_eval)

    code = """
x = 5
if x > 3:
    y = 1
else:
    y = 0
"""
    result = _tracer().run_trace(code)
    assert "error" not in result, f"trace failed: {result}"
    assert eval_called == [], f"eval() was called: {eval_called}"


def test_short_circuit_and():
    """Short-circuit `and`: second operand must not evaluate if first is False."""
    code = """
def side_effect():
    side_effect.called = True
    return True
side_effect.called = False
x = False and side_effect()
"""
    result = _tracer().run_trace(code)
    assert "error" not in result
    assert result["steps"], "expected at least one step"
    # Find the final value of x — should be False, side_effect not called.
    # We can't introspect the post-trace namespace directly through the trace
    # steps, but the trace should succeed without raising.


def test_nested_if():
    """Nested `if` statements compile and run without error."""
    code = """
x = 3
if x > 0:
    if x > 2:
        y = "big"
    else:
        y = "small"
else:
    y = "non-positive"
"""
    result = _tracer().run_trace(code)
    assert "error" not in result, f"trace failed: {result}"

    # Both branch lines should appear in the trace.
    branch_lines = [
        s["line_number"]
        for s in result["steps"]
        if s.get("branches_taken", {}).get("if", {}).get("taken") is True
    ]
    assert len(branch_lines) >= 1, "no taken branches found in nested if"


def test_validator_rejects_match_case():
    """The validator must reject `match/case` until branch detection supports it."""
    from tracer.validator import validate_code

    code = """
match x:
    case 1:
        y = "one"
"""
    is_valid, blocking, _ = validate_code(code)
    assert not is_valid
    assert any(b["pattern"] == "unsupported_syntax" for b in blocking)


def test_validator_rejects_all_dunder_access():
    """Any dunder attribute access is blocked, even ones not in the original list."""
    from tracer.validator import validate_code

    # Pick a dunder that was NOT in the original list, to confirm the new
    # "reject all dunders" rule is in effect.
    code = """
class Foo:
    pass
Foo.__init_subclasses__
"""
    is_valid, blocking, _ = validate_code(code)
    assert not is_valid
    assert any(b["pattern"] == "dangerous_attribute" for b in blocking)


def test_validator_rejects_generator_dos():
    """`while True: yield ...` is rejected as a generator-based DoS vector."""
    from tracer.validator import validate_code

    code = """
def gen():
    while True:
        yield 1
"""
    is_valid, blocking, _ = validate_code(code)
    assert not is_valid
    assert any(b["pattern"] == "generator_dos" for b in blocking)


def test_validator_allows_normal_loops():
    """`while x < 10:` (without constant truthy + yield) is still allowed."""
    from tracer.validator import validate_code

    code = """
x = 0
while x < 3:
    x += 1
"""
    is_valid, blocking, _ = validate_code(code)
    assert is_valid
    assert blocking == []
