"""Trace execution API endpoints (Workstream 2: split from monolithic traces.py).

This router owns the **execution-only** surface:
    - POST /api/traces/run
    - POST /api/traces/fork

Persistence (save, list) lives in `traces_save.py`.
Sharing and shared-trace forks live in `traces_share.py`.
The aggregated dashboard widget lives in `dashboard.py`.

The validate-then-run pipeline is shared with `traces_save.py` and
`traces_share.py` via `app.services.trace_executor.execute_trace_or_raise`.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Header
from httpx import AsyncClient
from pydantic import BaseModel, Field

from app.dependencies import get_http_client
from app.services.trace_executor import execute_trace_or_raise

logger = logging.getLogger("cognitrace.traces")

router = APIRouter()


# ── Response models ─────────────────────────────────────────────────


class VariableInfoResponse(BaseModel):
    type: str
    value: str
    changed: bool
    id: int | None = None
    is_ref: bool = False
    children: dict | None = None
    mutation_type: str = "unchanged"


class TraceStepResponse(BaseModel):
    step_number: int
    line_number: int
    bytecode_offset: int
    opcode: str
    variables: dict[str, VariableInfoResponse]
    branches_taken: dict
    duration_ms: float


class TraceResponse(BaseModel):
    steps: list[TraceStepResponse]
    total_steps: int
    duration_ms: float
    checkpoints: list[dict] = []


class ForkStepRequest(BaseModel):
    code: str = Field(..., max_length=5000)
    fork_step_number: int = Field(default=0, ge=0)
    overridden_variables: dict[str, str] = Field(default_factory=dict)
    parent_trace_id: str | None = None


class ForkTraceStepResponse(BaseModel):
    steps: list[TraceStepResponse]
    total_steps: int
    duration_ms: float
    checkpoints: list[dict] = []
    fork_step_number: int
    overridden_variables: dict[str, str]
    parent_trace_id: str | None = None


# ── Request models ──────────────────────────────────────────────────


class TraceRequest(BaseModel):
    code: str = Field(..., max_length=5000)
    initial_namespace: dict[str, str] | None = None


# ── Endpoints ───────────────────────────────────────────────────────


@router.post("/traces/run", response_model=TraceResponse)
async def run_trace(
    req: TraceRequest,
    authorization: str | None = Header(None),
    client: AsyncClient = Depends(get_http_client),
):
    """Execute Python code and return a step-by-step trace.

    Free users are limited to 50 traces per month; Pro users have unlimited.
    Side-effect patterns are blocked before execution begins.
    """
    await _check_free_quota(authorization, client)

    result = await execute_trace_or_raise(
        code=req.code,
        initial_namespace=req.initial_namespace,
    )
    return TraceResponse(
        steps=[TraceStepResponse(**s) for s in result["steps"]],
        total_steps=result["total_steps"],
        duration_ms=result["duration_ms"],
        checkpoints=result.get("checkpoints", []),
    )


@router.post("/traces/fork", response_model=ForkTraceStepResponse)
async def fork_trace(
    req: ForkStepRequest,
    client: AsyncClient = Depends(get_http_client),
):
    """Fork an execution trace from a step N with custom variable overrides."""
    # 1. Base trace to capture the target-step variables.
    base = await execute_trace_or_raise(code=req.code)
    target_vars = _extract_step_variables(base, req.fork_step_number)
    if req.overridden_variables:
        target_vars.update(req.overridden_variables)

    # 2. Re-run with merged namespace.
    forked = await execute_trace_or_raise(
        code=req.code,
        initial_namespace=target_vars,
    )

    return ForkTraceStepResponse(
        steps=[TraceStepResponse(**s) for s in forked["steps"]],
        total_steps=forked["total_steps"],
        duration_ms=forked["duration_ms"],
        checkpoints=forked.get("checkpoints", []),
        fork_step_number=req.fork_step_number,
        overridden_variables=req.overridden_variables,
        parent_trace_id=req.parent_trace_id,
    )


# ── Helpers ─────────────────────────────────────────────────────────

FREE_TRACE_LIMIT = 50


async def _check_free_quota(authorization: str | None, client: AsyncClient) -> None:
    """Enforce the 50-traces-per-month cap for free-tier users.

    No-op for anonymous (header missing) and Pro users. Raises 402 on cap reached.
    """
    if not authorization:
        return
    from fastapi import HTTPException

    from app.config import settings
    from app.dependencies import is_pro_user
    from app.routers.auth import get_current_user

    user = await get_current_user(None, authorization)
    user_id = user.get("id", "")
    if not user_id:
        return
    if await is_pro_user(user_id, client):
        return

    settings_local = settings
    count = await _get_trace_count_this_month(user_id, settings_local, client)
    if count >= FREE_TRACE_LIMIT:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "FREE_LIMIT_REACHED",
                "message": "You've used your 50 free traces this month. Upgrade to Pro for unlimited.",
                "upgrade_url": "/upgrade",
            },
        )


async def _get_trace_count_this_month(
    user_id: str,
    settings_local: settings | None = None,
    client: AsyncClient | None = None,
) -> int:
    """Return the number of trace rows this user has created in the current month.

    Exposed as a module-level helper so it can be unit-tested independently of
    the quota-enforcement path. Reads via the service-role key, so the count
    is correct even when RLS would filter on the user_id filter.
    """
    from datetime import datetime

    from app.config import settings as default_settings

    settings_local = settings_local or default_settings
    client_local = client
    should_close = False
    if client_local is None:
        import httpx
        client_local = httpx.AsyncClient()
        should_close = True

    try:
        now = datetime.utcnow()
        month_start = f"{now.year}-{now.month:02d}-01"
        resp = await client_local.get(
            f"{settings_local.supabase_url}/rest/v1/traces",
            params={
                "user_id": f"eq.{user_id}",
                "created_at": f"gte.{month_start}",
                "select": "id",
            },
            headers={
                "Authorization": f"Bearer {settings_local.supabase_service_key}",
                "apikey": settings_local.supabase_service_key,
            },
        )
        if resp.status_code != 200:
            return 0
        return len(resp.json())
    finally:
        if should_close:
            await client_local.aclose()


def _extract_step_variables(trace_result: dict, step_number: int) -> dict[str, str]:
    """Return the variables at `step_number` as `name → repr_string` pairs.

    The fork endpoint feeds these into a fresh trace with `initial_namespace`.
    """
    steps = trace_result.get("steps", [])
    if not steps:
        return {}
    idx = min(step_number, len(steps) - 1)
    out: dict[str, str] = {}
    for var_name, var_info in steps[idx].get("variables", {}).items():
        out[var_name] = var_info.get("value", "None")
    return out


# ── Re-exports for backward-compatibility with the pre-split module ───
# The split-routers refactor moved these symbols to dedicated files. Tests
# and old imports continue to work via these aliases.

from app.routers.dashboard import get_dashboard  # noqa: E402,F401
from app.routers.traces_save import SaveTraceRequest, save_trace  # noqa: E402,F401
