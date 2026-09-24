"""Unit tests for `app.services.trace_executor` (Workstream 8).

This module is the single pipeline shared by every trace-related router.
The tests pin:

1. The validator's "blocked" outcome maps to a 422 with the right payload.
2. Subprocess error codes (TIMEOUT, SYNTAX_ERROR, MAX_STEPS) map to the
   documented HTTP statuses.
3. The initial-namespace parser only accepts `ast.literal_eval`-able values.
"""
import asyncio
import pytest
from fastapi import HTTPException

from app.services.trace_executor import _parse_initial_namespace, execute_trace_or_raise


# ──────────────────────────────────────────────────────────────────────
# _parse_initial_namespace (the cheap, sync helper)
# ──────────────────────────────────────────────────────────────────────


def test_parse_initial_namespace_empty_returns_empty():
    """None / {} / empty inputs all yield an empty dict."""
    assert _parse_initial_namespace(None) == {}
    assert _parse_initial_namespace({}) == {}


def test_parse_initial_namespace_parses_literals():
    """Each value is parsed via ast.literal_eval."""
    ns = _parse_initial_namespace({"x": "1", "y": "1.5", "name": "'alice'"})
    assert ns == {"x": 1, "y": 1.5, "name": "alice"}


def test_parse_initial_namespace_silently_drops_invalid_entries():
    """Invalid literals are skipped, not raised — best-effort."""
    ns = _parse_initial_namespace({"good": "1", "bad": "os.system('rm -rf /')"})
    assert "good" in ns and ns["good"] == 1
    # The bad entry must NOT have executed os.system — sandbox test
    assert "bad" not in ns


def test_parse_initial_namespace_keeps_collections():
    """Lists / tuples / dicts round-trip as Python literals."""
    ns = _parse_initial_namespace({"items": "[1, 2, 3]", "config": "{'a': 1}"})
    assert ns["items"] == [1, 2, 3]
    assert ns["config"] == {"a": 1}


# ──────────────────────────────────────────────────────────────────────
# execute_trace_or_raise (mocked subprocess)
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def patch_subprocess(monkeypatch):
    """Replace the subprocess + concurrency layer with controllable fakes.

    The trace executor pulls in `app.concurrency.run_with_concurrency_limit`
    and `tracer.runner.run_trace` at runtime to avoid an import cycle. We
    patch both modules so the executor calls our fake coroutine instead.
    """
    fake_result = {"steps": [], "total_steps": 0, "duration_ms": 5}

    async def fake_run_with_limit(fn):
        # The executor passes a lambda that returns the subprocess result.
        # We just invoke it.
        return fn()

    def fake_run_trace_subprocess(code, max_steps=500, initial_namespace=None):
        return fake_result

    monkeypatch.setattr(
        "app.concurrency.run_with_concurrency_limit",
        fake_run_with_limit,
        raising=False,
    )
    monkeypatch.setattr(
        "tracer.runner.run_trace",
        fake_run_trace_subprocess,
        raising=False,
    )
    return fake_result


@pytest.mark.asyncio
async def test_execute_trace_runs_validator_first(monkeypatch, patch_subprocess):
    """If the validator flags the code, we raise 422 BEFORE spawning a subprocess."""
    blocking = [{"pattern": "os.system", "line": 1, "type": "function_call"}]
    warnings = []

    def fake_validate(code):
        return (False, blocking, warnings)

    # Patch the validator at the *import site used by trace_executor* —
    # `from tracer.validator import validate_code` binds the symbol in
    # `app.services.trace_executor`, so we patch there.
    monkeypatch.setattr(
        "app.services.trace_executor.validate_code",
        fake_validate,
        raising=False,
    )

    # The subprocess must NEVER run — track invocations.
    called = {"n": 0}

    def tracking_run(code, **kwargs):
        called["n"] += 1
        return {}

    monkeypatch.setattr(
        "tracer.runner.run_trace",
        tracking_run,
        raising=False,
    )

    with pytest.raises(HTTPException) as exc_info:
        await execute_trace_or_raise("os.system('rm -rf /')")
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["error"] == "SIDE_EFFECT_BLOCKED"
    assert "os.system" in exc_info.value.detail["matched"]
    # Subprocess was never spawned
    assert called["n"] == 0


@pytest.mark.asyncio
async def test_execute_trace_returns_success_result(patch_subprocess):
    """Happy path: validator passes, subprocess returns steps, executor returns dict."""
    result = await execute_trace_or_raise("x = 1\nprint(x)")
    assert result == patch_subprocess


@pytest.mark.asyncio
async def test_execute_trace_passes_initial_namespace(patch_subprocess, monkeypatch):
    """The executor parses initial_namespace and passes Python values (not strings) to the subprocess."""
    captured = {}

    def capturing_run(code, max_steps=500, initial_namespace=None):
        captured["ns"] = initial_namespace
        return patch_subprocess

    monkeypatch.setattr("tracer.runner.run_trace", capturing_run, raising=False)

    await execute_trace_or_raise(
        "x = 1",
        initial_namespace={"x": "5", "name": "'alice'"},
    )
    # The string '5' must have been parsed to the int 5
    assert captured["ns"] == {"x": 5, "name": "alice"}


@pytest.mark.asyncio
async def test_execute_trace_maps_timeout_to_408(monkeypatch, patch_subprocess):
    """TIMEOUT error code from the subprocess becomes 408."""

    def timeout_run(code, **kwargs):
        return {"error": "TIMEOUT", "message": "exceeded 10s"}

    monkeypatch.setattr("tracer.runner.run_trace", timeout_run, raising=False)

    with pytest.raises(HTTPException) as exc_info:
        await execute_trace_or_raise("while True: pass")
    assert exc_info.value.status_code == 408
    assert exc_info.value.detail["error"] == "TIMEOUT"


@pytest.mark.asyncio
async def test_execute_trace_maps_syntax_error_to_422(monkeypatch, patch_subprocess):
    """SYNTAX_ERROR from the subprocess becomes 422 with the offending line."""

    def syntax_run(code, **kwargs):
        return {"error": "SYNTAX_ERROR", "message": "unexpected EOF", "line": 7}

    monkeypatch.setattr("tracer.runner.run_trace", syntax_run, raising=False)

    with pytest.raises(HTTPException) as exc_info:
        await execute_trace_or_raise("def f(:\n    pass")
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["error"] == "SYNTAX_ERROR"
    assert exc_info.value.detail["line"] == 7


@pytest.mark.asyncio
@pytest.mark.parametrize("error_code", ["MAX_STEPS", "MAX_STEPS_EXCEEDED"])
async def test_execute_trace_maps_max_steps_to_422(monkeypatch, patch_subprocess, error_code):
    """Both MAX_STEPS and MAX_STEPS_EXCEEDED become 422."""
    fake_ns = {"error": error_code, "message": "step ceiling"}

    def max_run(code, **kwargs):
        return fake_ns

    monkeypatch.setattr("tracer.runner.run_trace", max_run, raising=False)

    with pytest.raises(HTTPException) as exc_info:
        await execute_trace_or_raise("for i in range(10**9): pass")
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail["error"] == "MAX_STEPS"


@pytest.mark.asyncio
async def test_execute_trace_unknown_error_becomes_500(monkeypatch, patch_subprocess):
    """Anything else from the subprocess becomes a generic 500."""

    def unknown_run(code, **kwargs):
        return {"error": "WEIRD_INTERNAL_THING", "message": "what"}

    monkeypatch.setattr("tracer.runner.run_trace", unknown_run, raising=False)

    with pytest.raises(HTTPException) as exc_info:
        await execute_trace_or_raise("x = 1")
    assert exc_info.value.status_code == 500
    assert exc_info.value.detail["error"] == "WEIRD_INTERNAL_THING"
