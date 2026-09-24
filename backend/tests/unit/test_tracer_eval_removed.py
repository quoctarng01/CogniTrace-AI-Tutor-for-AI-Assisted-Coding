"""Workstream 5: regression test that asserts `eval()` is no longer called inside the tracer.

This is the dedicated test for the eval-removal acceptance criterion:
"`grep -n 'eval(' backend/tracer/` returns zero matches in the tracer module".

We additionally guard against future regressions by importing the module and
checking that the literal substring `"eval("` does not appear as a callable
invocation in the tracer source.
"""

from __future__ import annotations

import inspect
import re

import tracer.tracer as tracer_module


def test_eval_not_invoked_in_tracer_source():
    """Static check: no `eval(...)` call appears in the tracer module source."""
    src = inspect.getsource(tracer_module)
    # Look for any `eval(` call, not for the substring "eval" inside identifiers
    # like "evaluator". The pattern requires `eval(` with a non-identifier char
    # (or EOL) after the closing paren to avoid matching `evaluator(` etc.
    pattern = re.compile(r"\beval\s*\(")
    matches = pattern.findall(src)
    assert matches == [], (
        f"eval() must not be called from the tracer module; found {len(matches)} match(es)"
    )


def test_validator_not_importing_eval():
    """Guard: `validator.py` is also free of `eval(` calls."""
    import tracer.validator as validator_module
    src = inspect.getsource(validator_module)
    pattern = re.compile(r"\beval\s*\(")
    matches = pattern.findall(src)
    assert matches == [], (
        f"validator must not call eval(); found {len(matches)} match(es)"
    )


def test_branch_compiler_present():
    """The new compile-time branch compiler must exist on the tracer module."""
    assert hasattr(tracer_module, "_BranchCompiler")
    assert hasattr(tracer_module, "_compile_branch_predicate")
    assert hasattr(tracer_module, "BranchDecision")
