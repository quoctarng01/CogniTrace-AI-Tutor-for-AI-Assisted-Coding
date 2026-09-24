"""Trace sharing endpoints (Workstream 2: split from monolithic traces.py).

This router owns:
    - POST /api/traces/{trace_id}/share            — generate a share link
    - GET  /api/traces/shared/{share_token}        — fetch a shared trace
    - POST /api/traces/shared/{share_token}/fork   — fork a shared trace into the caller's account

Other trace-related concerns live in:
    - `traces.py` — run, fork (the execution surface)
    - `traces_save.py` — save, list
    - `dashboard.py` — aggregated dashboard widget
"""
from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import APIRouter, Depends, Header, Request
from httpx import AsyncClient
from pydantic import BaseModel, Field

from app.config import settings
from app.dependencies import get_http_client, get_profile_id_for_user
from app.routers.auth import get_current_user, get_profile_id
from app.services.errors import (
    auth_required_401,
    profile_not_found_404,
    shared_trace_expired_410,
    trace_not_found_404,
    upstream_failure_502,
)

logger = logging.getLogger("cognitrace.traces_share")

router = APIRouter()


class ShareTraceRequest(BaseModel):
    expiration_days: int | None = Field(default=None, ge=0, le=365)
    password: str | None = Field(default=None, max_length=128)


class ForkSharedTraceResponse(BaseModel):
    trace_id: str
    share_token: str
    share_url: str


@router.post("/traces/{trace_id}/share")
async def share_trace(
    trace_id: str,
    request: Request,
    req: ShareTraceRequest | None = None,
    authorization: str | None = Header(None),
    client: AsyncClient = Depends(get_http_client),
):
    """Generate or update a share link. Sets `is_public=true` and a fresh token."""
    if not authorization:
        raise auth_required_401()

    user = await get_current_user(request, authorization)
    profile_id = await get_profile_id_for_user(user.get("id", ""), client)
    if not profile_id:
        raise profile_not_found_404()

    share_token = secrets.token_hex(16)
    payload: dict = {"share_token": share_token, "is_public": True}

    if req and req.expiration_days and req.expiration_days > 0:
        expires = datetime.now(UTC) + timedelta(days=req.expiration_days)
        payload["expires_at"] = expires.isoformat()
    else:
        payload["expires_at"] = None

    if req and req.password:
        payload["password_hash"] = bcrypt.hashpw(
            req.password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")
    else:
        payload["password_hash"] = None

    check_resp = await client.get(
        f"{settings.supabase_url}/rest/v1/traces",
        params={"id": f"eq.{trace_id}", "user_id": f"eq.{profile_id}", "select": "id"},
        headers={
            "Authorization": f"Bearer {authorization[7:]}",
            "apikey": settings.supabase_service_key,
        },
    )
    if check_resp.status_code != 200 or not check_resp.json():
        raise trace_not_found_404()

    resp = await client.patch(
        f"{settings.supabase_url}/rest/v1/traces",
        params={"id": f"eq.{trace_id}"},
        headers={
            "Authorization": f"Bearer {authorization[7:]}",
            "apikey": settings.supabase_service_key,
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        json=payload,
    )
    if resp.status_code == 404:
        raise trace_not_found_404()

    return {
        "share_token": share_token,
        "share_url": f"/trace/{share_token}",
        "expires_at": payload.get("expires_at"),
        "has_password": bool(req and req.password),
    }


@router.get("/traces/shared/{share_token}")
async def get_shared_trace(
    share_token: str,
    authorization: str | None = Header(None),
    client: AsyncClient = Depends(get_http_client),
):
    """Fetch a trace by share token. Owner sees their trace; anonymous sees public only."""
    owner_id = None
    if authorization:
        token = authorization.replace("Bearer ", "")
        owner_id = await get_profile_id(token, client)

    if owner_id:
        params = {
            "share_token": f"eq.{share_token}",
            "or": f"(is_public.eq.true,user_id.eq.{owner_id})",
            "select": "*",
            "limit": "1",
        }
    else:
        params = {
            "share_token": f"eq.{share_token}",
            "is_public": "eq.true",
            "select": "*",
            "limit": "1",
        }

    resp = await client.get(
        f"{settings.supabase_url}/rest/v1/traces",
        params=params,
        headers={
            "apikey": settings.supabase_service_key,
            "Authorization": f"Bearer {settings.supabase_service_key}",
        },
    )
    if resp.status_code != 200 or not resp.json():
        raise trace_not_found_404()

    trace = resp.json()[0]

    expires_at = trace.get("expires_at")
    if expires_at:
        try:
            exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if datetime.now(UTC) > exp:
                raise shared_trace_expired_410()
        except ValueError:
            pass

    return {k: v for k, v in trace.items() if k != "password_hash"}


@router.post("/traces/shared/{share_token}/fork", response_model=ForkSharedTraceResponse)
async def fork_shared_trace(
    share_token: str,
    request: Request,
    authorization: str | None = Header(None),
    client: AsyncClient = Depends(get_http_client),
):
    """Copy a shared trace into the authenticated user's account."""
    if not authorization:
        raise auth_required_401()

    user = await get_current_user(request, authorization)
    profile_id = await get_profile_id_for_user(user.get("id", ""), client)
    if not profile_id:
        raise profile_not_found_404()

    orig_resp = await client.get(
        f"{settings.supabase_url}/rest/v1/traces",
        params={"share_token": f"eq.{share_token}", "select": "*"},
        headers={
            "Authorization": f"Bearer {settings.supabase_service_key}",
            "apikey": settings.supabase_service_key,
        },
    )
    orig_traces = orig_resp.json() if orig_resp.status_code == 200 else []
    if not orig_traces:
        raise trace_not_found_404()
    orig = orig_traces[0]

    new_share_token = secrets.token_hex(16)
    fork_payload = {
        "user_id": profile_id,
        "code": orig.get("code", ""),
        "language": orig.get("language", "python"),
        "concept_tags": orig.get("concept_tags", []),
        "is_public": False,
        "share_token": new_share_token,
        "steps": orig.get("steps"),
    }

    fork_resp = await client.post(
        f"{settings.supabase_url}/rest/v1/traces",
        headers={
            "Authorization": f"Bearer {settings.supabase_service_key}",
            "apikey": settings.supabase_service_key,
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        json=fork_payload,
    )
    if fork_resp.status_code not in (200, 201):
        raise upstream_failure_502("fork failed")

    fork = fork_resp.json()
    if isinstance(fork, list) and fork:
        fork = fork[0]
    return ForkSharedTraceResponse(
        trace_id=fork.get("id", ""),
        share_token=new_share_token,
        share_url=f"/trace/{new_share_token}",
    )
