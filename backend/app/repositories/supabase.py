"""
Single source of truth for all Supabase REST API calls.
Replaces duplicated httpx.AsyncClient patterns across all routers.

Lifecycle:
  - Registered in app/dependencies.py as a FastAPI dependency
  - Injected into routers via Annotated[..., Depends(get_supabase_repo)]
  - Closed in lifespan shutdown: await repo.close()
"""
from __future__ import annotations

import datetime
import time
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from app.config import Settings
from app.routers.auth import get_profile_id

logger = structlog.get_logger(__name__)

# ── Result Types ───────────────────────────────────────────────────────────
@dataclass
class ProfileResult:
    id: str
    is_pro: bool
    email: str | None

@dataclass
class TraceResult:
    id: str
    code: str
    steps: list[dict]
    share_token: str | None
    is_public: bool
    user_id: str
    created_at: str

@dataclass
class ReviewResult:
    id: str
    code: str
    explanation: str
    steps: list[dict]
    due_date: str
    interval: int
    ease_factor: float
    streak: int


@dataclass
class FingerprintResult:
    """One row of `trace_fingerprints`.

    The `json` field is the canonical wire payload returned by
    `Fingerprint.to_dict()`. The other scalar fields are denormalised so
    the share-page endpoint can query them directly without unpacking
    JSONB.
    """

    id: str
    trace_id: str
    user_id: str | None
    json: dict
    compact: str
    short_form: str
    signature: str
    branches: int
    recursion_depth: int
    loop_iterations: int
    total_steps: int
    conceptual_complexity: str
    total_duration_ms: float
    exception_types: list[str]
    created_at: str
    updated_at: str

# ── Repository ─────────────────────────────────────────────────────────────
class SupabaseRepository:
    """
    All Supabase REST API calls go through this class.
    Includes circuit breaker for resilience.
    """

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.base_url = settings.supabase_url
        self.service_key = settings.supabase_service_key
        self._client = client or httpx.AsyncClient(timeout=10.0)
        self._owns_client = client is None
        self._circuit_open = False
        self._circuit_opened_at: float | None = None
        self._cache: dict[str, tuple[Any, float]] = {}
        self._cache_ttl = 300

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "Content-Type": "application/json",
        }

    def _user_headers(self, token: str) -> dict[str, str]:
        return {
            "apikey": self.service_key,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _cache_key(self, method: str, path: str, params: dict | None) -> str:
        return f"{method}:{path}:{str(sorted(params.items()) if params else [])}"

    async def _get_cached(
        self,
        path: str,
        params: dict | None = None,
        headers: dict | None = None,
        ttl: int = 300,
    ) -> list[dict]:
        key = self._cache_key("GET", path, params)
        now = time.time()
        if key in self._cache:
            value, expires_at = self._cache[key]
            if now < expires_at:
                return value
        result = await self._get(path, params, headers)
        self._cache[key] = (result, now + ttl)
        return result

    async def _get(
        self,
        path: str,
        params: dict | None = None,
        headers: dict | None = None,
    ) -> list[dict]:
        if self._is_circuit_open():
            logger.warning("supabase_circuit_open", path=path)
            return []
        try:
            resp = await self._client.get(
                f"{self.base_url}{path}",
                params=params,
                headers=headers or self._headers(),
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code >= 500:
                self._trip_circuit()
            logger.error("supabase_get_failed", path=path,
                         status=e.response.status_code, detail=e.response.text[:200])
            return []
        except Exception as e:
            self._trip_circuit()
            logger.error("supabase_get_failed", path=path, error=str(e))
            return []

    async def _post(
        self,
        path: str,
        json: dict,
        headers: dict | None = None,
    ) -> dict | None:
        try:
            resp = await self._client.post(
                f"{self.base_url}{path}",
                json=json,
                headers=headers or self._headers(),
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.error("supabase_post_failed", path=path, error=str(e))
            return None

    def _is_circuit_open(self) -> bool:
        if not self._circuit_open:
            return False
        if self._circuit_opened_at and (time.time() - self._circuit_opened_at) > 30:
            logger.info("supabase_circuit_recovering")
            self._circuit_open = False
            return False
        return True

    def _trip_circuit(self):
        self._circuit_open = True
        self._circuit_opened_at = time.time()
        logger.warning("supabase_circuit_tripped")

    async def close(self):
        if self._owns_client:
            await self._client.aclose()

    # ── Profile ─────────────────────────────────────────────────────────
    async def get_profile_by_token(self, token: str) -> ProfileResult | None:
        # Step 1: Decode token to get user UUID
        user_resp = await self._client.get(
            f"{self.base_url}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": self.service_key,
            },
        )
        if user_resp.status_code != 200:
            return None
        user_id = user_resp.json().get("id", "")
        if not user_id:
            return None

        # Step 2: Retrieve profile by user_id UUID
        rows = await self._get(
            "/rest/v1/profiles",
            params={"user_id": f"eq.{user_id}", "select": "*"},
            headers=self._headers(),
        )
        if not rows:
            return None
        p = rows[0]
        return ProfileResult(id=p["id"], is_pro=p.get("plan") == "pro", email=p.get("email"))

    # ── Traces ─────────────────────────────────────────────────────────
    async def get_user_traces(
        self, user_id: str, limit: int = 20
    ) -> list[TraceResult]:
        rows = await self._get(
            "/rest/v1/traces",
            params={
                "user_id": f"eq.{user_id}",
                "limit": str(limit),
                "order": "created_at.desc",
                "select": "*",
            },
        )
        return [TraceResult(**r) for r in rows]

    async def save_trace(self, trace: dict, token: str) -> TraceResult | None:
        result = await self._post(
            "/rest/v1/traces",
            json=trace,
            headers=self._user_headers(token),
        )
        return TraceResult(**result) if result else None

    async def get_shared_trace(
        self, share_token: str, owner_token: str | None = None
    ) -> TraceResult | None:
        if owner_token:
            owner_id = await get_profile_id(owner_token)
            params = {
                "share_token": f"eq.{share_token}",
                "or": f"(is_public.eq.true,user_id.eq.{owner_id})",
                "select": "*",
                "limit": "1",
            }
            headers = self._user_headers(owner_token)
        else:
            params = {
                "share_token": f"eq.{share_token}",
                "is_public": "eq.true",
                "select": "*",
                "limit": "1",
            }
            headers = self._headers()

        rows = await self._get("/rest/v1/traces", params=params, headers=headers)
        return TraceResult(**rows[0]) if rows else None

    # ── Reviews ────────────────────────────────────────────────────────
    async def get_due_reviews(self, user_id: str) -> list[ReviewResult]:
        rows = await self._get_cached(
            "/rest/v1/review_cards",
            params={
                "user_id": f"eq.{user_id}",
                "due_date": f"lte.{datetime.datetime.utcnow().isoformat()}",
                "order": "due_date.asc",
                "select": "*",
            },
            ttl=60,
        )
        return [ReviewResult(**r) for r in rows]

    # ── Trace Fingerprints (Workstream 12) ─────────────────────────────
    async def upsert_fingerprint(
        self,
        *,
        trace_id: str,
        user_id: str | None,
        payload: dict,
    ) -> FingerprintResult | None:
        """Insert or update the fingerprint row for a trace.

        `payload` is the wire dict returned by `Fingerprint.to_dict()`
        PLUS the denormalised scalar fields we store alongside the JSON
        blob. We POST with `Prefer: resolution=merge-duplicates` so the
        unique constraint on `trace_id` produces an UPSERT — the same
        call works for first-save and for re-save without branching.
        """
        body = {
            "trace_id": trace_id,
            "user_id": user_id,
            "fingerprint_json": payload,
            "compact": payload["compact"],
            "short_form": payload["short"],
            "signature": payload["signature"],
            "branches": payload["branches"],
            "recursion_depth": payload["recursion_depth"],
            "loop_iterations": payload["loop_iterations"],
            "total_steps": payload["total_steps"],
            "conceptual_complexity": payload["conceptual_complexity"],
            "total_duration_ms": payload["total_duration_ms"],
            "exception_types": payload["exception_types"],
        }
        try:
            resp = await self._client.post(
                f"{self.base_url}/rest/v1/trace_fingerprints",
                json=body,
                headers={
                    **self._headers(),
                    "Prefer": "resolution=merge-duplicates,return=representation",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and data:
                data = data[0]
            # Postgres returns `fingerprint_json` not `json`; remap.
            data["json"] = data.pop("fingerprint_json", {})
            return FingerprintResult(**data)
        except Exception as e:
            logger.error("supabase_upsert_fingerprint_failed", trace_id=trace_id, error=str(e))
            return None

    async def get_fingerprint_by_trace_id(self, trace_id: str) -> FingerprintResult | None:
        """Fetch the fingerprint for a trace id. Returns None if no row exists."""
        rows = await self._get(
            "/rest/v1/trace_fingerprints",
            params={"trace_id": f"eq.{trace_id}", "select": "*", "limit": "1"},
        )
        if not rows:
            return None
        row = rows[0]
        row["json"] = row.pop("fingerprint_json", {})
        return FingerprintResult(**row)

    async def get_fingerprint_by_share_token(
        self, share_token: str, owner_id: str | None = None
    ) -> FingerprintResult | None:
        """Fetch the fingerprint via the trace's share token. The join lives
        in application code (PostgREST doesn't do cross-table SELECTs without
        an explicit `!inner()` resource embedding) so we look up the trace
        first, then the fingerprint.

        Anonymous callers (no `owner_id`) can only resolve fingerprints for
        traces that are publicly shared.
        """
        if owner_id:
            trace_rows = await self._get(
                "/rest/v1/traces",
                params={
                    "share_token": f"eq.{share_token}",
                    "or": f"(is_public.eq.true,user_id.eq.{owner_id})",
                    "select": "id",
                    "limit": "1",
                },
            )
        else:
            trace_rows = await self._get(
                "/rest/v1/traces",
                params={
                    "share_token": f"eq.{share_token}",
                    "is_public": "eq.true",
                    "select": "id",
                    "limit": "1",
                },
            )
        if not trace_rows:
            return None
        return await self.get_fingerprint_by_trace_id(trace_rows[0]["id"])
