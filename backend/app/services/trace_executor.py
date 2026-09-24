"""Shared trace-execution helpers used by every trace-related router.

This module owns the validate → parse-initial-namespace → run-subprocess →
error-mapping pipeline that was previously duplicated in
`run_trace` (POST /traces/run) and `fork_trace` (POST /traces/fork).

Public surface:
    execute_trace_or_raise(code, initial_namespace, max_steps=500) -> dict

Returns the raw subprocess result dict on success; raises HTTPException on
any of the documented failure modes. Routers should pass the result
straight back to the client (after Pydantic validation).

Collaborators:
    - `backend/tracer/validator.py` (validate_code)
    - `backend/tracer/runner.py` (run_trace_subprocess)
    - `backend/app/concurrency.py` (run_with_concurrency_limit)

Last significant change: Workstream 2 — extracted from `app/routers/traces.py`.
"""
from __future__ import annotations

import ast
import logging
from typing import Any

from fastapi import HTTPException

from tracer.validator import validate_code

logger = logging.getLogger("cognitrace.trace_executor")


def _parse_initial_namespace(raw: dict[str, str] | None) -> dict[str, Any]:
    """Parse string-valued initial-namespace entries into Python literals.

    Values must round-trip through `repr()` and `ast.literal_eval`. Anything
    that fails to parse is silently skipped — the goal is "best-effort",
    not strict rejection, so the user can omit bad entries without losing the
    trace.
    """
    if not raw:
        return {}
    parsed: dict[str, Any] = {}
    for name, val_str in raw.items():
        try:
            parsed[name] = ast.literal_eval(val_str)
        except (ValueError, SyntaxError):
            continue
    return parsed


def _validate_or_422(code: str) -> None:
    """Run the side-effect validator. Raise 422 if the code is unsafe."""
    is_valid, blocking_effects, warnings = validate_code(code)
    if not is_valid:
        logger.warning(
            "trace_blocked_by_validator",
            extra={"matched": [e["pattern"] for e in blocking_effects]},
        )
        raise HTTPException(
            status_code=422,
            detail={
                "error": "SIDE_EFFECT_BLOCKED",
                "message": "This code contains patterns that are not allowed for security reasons.",
                "matched": [e["pattern"] for e in blocking_effects],
                "warnings": [w["pattern"] for w in warnings],
            },
        )


async def execute_trace_or_raise(
    code: str,
    initial_namespace: dict[str, str] | None = None,
    max_steps: int = 500,
) -> dict:
    """Validate, run, and map errors for a single trace request.

    Steps:
        1. Static AST validation (raises 422 on side-effect match).
        2. Parse `initial_namespace` string values into Python literals.
        3. Spawn the tracer subprocess under the global concurrency semaphore.
        4. Map subprocess error codes to HTTPException (408 timeout, 422 syntax,
           422 max-steps, 500 other).

    Args:
        code: The Python source the user wants to trace.
        initial_namespace: Optional `{name: literal_string}` pairs to seed the
                          namespace. Strings are parsed via `ast.literal_eval`.
        max_steps: Hard ceiling on the number of trace steps.

    Returns:
        The raw subprocess result dict. Keys: `steps`, `total_steps`,
        `duration_ms`, `checkpoints`. On failure, `error` plus `message`/`line`.
    """
    _validate_or_422(code)
    parsed_ns = _parse_initial_namespace(initial_namespace)

    # Avoid an import cycle on `app.concurrency`.
    from app.concurrency import run_with_concurrency_limit
    from tracer.runner import run_trace as run_trace_subprocess

    result = await run_with_concurrency_limit(
        lambda: run_trace_subprocess(code, max_steps=max_steps, initial_namespace=parsed_ns)
    )

    error_code = result.get("error")
    if not error_code:
        return result

    if error_code == "TIMEOUT":
        raise HTTPException(
            status_code=408,
            detail={"error": "TIMEOUT", "message": result.get("message", "Execution timed out.")},
        )
    if error_code == "SYNTAX_ERROR":
        raise HTTPException(
            status_code=422,
            detail={
                "error": "SYNTAX_ERROR",
                "message": result.get("message", "Syntax error."),
                "line": result.get("line"),
            },
        )
    if error_code in ("MAX_STEPS", "MAX_STEPS_EXCEEDED"):
        raise HTTPException(
            status_code=422,
            detail={"error": "MAX_STEPS", "message": result.get("message", "Step ceiling reached.")},
        )
    raise HTTPException(
        status_code=500,
        detail={"error": error_code, "message": result.get("message", "Unknown error.")},
    )
