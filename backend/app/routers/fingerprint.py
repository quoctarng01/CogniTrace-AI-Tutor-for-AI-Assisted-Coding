"""Trace fingerprint endpoints (Workstream 12 / thesis Contribution #4).

Owns the read-side surface for `trace_fingerprints`:

  GET /api/traces/{trace_id}/fingerprint           — JSON wire payload
  GET /fingerprint/{share_token}/card.svg          — OG card (Twitter/X/LINE/Discord)
  GET /api/fingerprint/{share_token}               — JSON data for the share page

The save-side stamping happens in `traces_save.save_trace` so the fingerprint
is always written atomically with the trace. The endpoints below are purely
read-side and compute the fingerprint lazily on first access if a row is
missing — useful for traces saved before V014 shipped.
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel

from app.dependencies import get_http_client, get_supabase_repo
from app.repositories.supabase import (
    FingerprintResult,
    SupabaseRepository,
)
from app.services.errors import trace_not_found_404
from app.services.fingerprint import (
    Fingerprint,
    code_preview,
    compute_fingerprint,
    diff_fingerprints_from_payloads,
    render_fingerprint_svg,
    xml_escape as _xml,
)

logger = logging.getLogger("cognitrace.fingerprint")

router = APIRouter()


# ── Response models / serialisation ────────────────────────────────────


def _fingerprint_to_payload(fp: FingerprintResult) -> dict:
    """Convert the DB row into the wire payload the client expects.

    Mirrors `Fingerprint.to_dict()` for the freshly-computed case. The DB
    row already stores the same dict under `fingerprint_json`, so when
    that's present we return it unchanged (preserves ast_metrics keys and
    any future fields the classifier adds without a code change here).
    """
    if fp.json:
        return fp.json
    return {
        "branches": fp.branches,
        "recursion_depth": fp.recursion_depth,
        "exception_types": list(fp.exception_types),
        "loop_iterations": fp.loop_iterations,
        "total_steps": fp.total_steps,
        "conceptual_complexity": fp.conceptual_complexity,
        "total_duration_ms": fp.total_duration_ms,
        "ast_metrics": {},
        "compact": fp.compact,
        "short": fp.short_form,
        "signature": fp.signature,
    }


# ── Lazy compute helper ────────────────────────────────────────────────


async def _ensure_fingerprint_for_trace(
    repo: SupabaseRepository,
    trace_id: str,
) -> FingerprintResult | None:
    """Return the existing fingerprint row, or compute + upsert + return.

    Backfills traces that were saved before V014. Always returns the
    `FingerprintResult` (never the raw `Fingerprint`) so callers can
    trust the wire shape.
    """
    existing = await repo.get_fingerprint_by_trace_id(trace_id)
    if existing:
        return existing

    # Pull the trace so we can run compute_fingerprint on its code+steps.
    try:
        trace_rows = await repo._get(  # noqa: SLF001 — internal but stable
            "/rest/v1/traces",
            params={"id": f"eq.{trace_id}", "select": "id,code,steps,user_id", "limit": "1"},
        )
    except Exception as e:  # pragma: no cover — defensive
        logger.error("fingerprint_trace_lookup_failed", trace_id=trace_id, error=str(e))
        return None
    if not trace_rows:
        return None
    trace = trace_rows[0]
    fp = compute_fingerprint(trace.get("code", ""), trace.get("steps", []))
    return await repo.upsert_fingerprint(
        trace_id=trace_id,
        user_id=trace.get("user_id"),
        payload=fp.to_dict(),
    )


async def _resolve_owner_id(request: Request) -> str | None:
    """Look up the caller's profile id from the Authorization header.

    Returns None for anonymous callers. Used by both the OG-card endpoint
    and the share-page data endpoint so private traces are visible to the
    owner only.
    """
    auth_header = request.headers.get("authorization")
    if not auth_header:
        return None
    token = auth_header.replace("Bearer ", "")
    try:
        from app.routers.auth import get_profile_id

        client = request.app.state.http_client
        return await get_profile_id(token, client)
    except Exception as e:  # pragma: no cover — defensive
        logger.debug("fingerprint_owner_lookup_failed", error=str(e))
        return None


# ── JSON endpoint ──────────────────────────────────────────────────────


@router.get("/traces/{trace_id}/fingerprint")
async def get_trace_fingerprint(
    trace_id: str,
    repo: Annotated[SupabaseRepository, Depends(get_supabase_repo)],
):
    """Return the fingerprint wire payload for a saved trace.

    Always recomputes-and-caches on first access (traces saved before V014
    are backfilled transparently). Subsequent calls return the stored row
    unchanged.
    """
    row = await _ensure_fingerprint_for_trace(repo, trace_id)
    if not row:
        raise trace_not_found_404()
    return _fingerprint_to_payload(row)


# ── OG card endpoint ───────────────────────────────────────────────────


@router.get("/fingerprint/{share_token}/card.svg")
async def get_fingerprint_card_svg(
    share_token: str,
    request: Request,
    repo: Annotated[SupabaseRepository, Depends(get_supabase_repo)],
    title: str | None = None,
):
    """Render the fingerprint as an SVG OG card.

    Served at the public-friendly `/fingerprint/{token}/card.svg` path so
    social-card crawlers (Twitter, Discord, LINE, Slack) can fetch the
    image directly without an auth header. Auth is implied by the share
    token: anonymous callers see public traces only; the trace owner
    sees their own.

    Cache headers:
      - `Cache-Control: public, max-age=300` — fingerprint is a hash of
        code+steps so it's effectively immutable; 5 minutes is just to
        allow quick corrections if we ship a bug fix.
      - `ETag` based on the fingerprint signature so crawlers can
        revalidate cheaply.
    """
    owner_id = await _resolve_owner_id(request)
    fp_row = await repo.get_fingerprint_by_share_token(share_token, owner_id=owner_id)
    if not fp_row:
        # Either the trace has no fingerprint yet OR the share token is
        # bad. Look up the trace itself to distinguish 404 from "lazy
        # compute"; if the trace exists but has no fingerprint, we
        # compute one. Otherwise we 404.
        if owner_id:
            trace_rows = await repo._get(  # noqa: SLF001
                "/rest/v1/traces",
                params={
                    "share_token": f"eq.{share_token}",
                    "or": f"(is_public.eq.true,user_id.eq.{owner_id})",
                    "select": "id,code,steps,user_id",
                    "limit": "1",
                },
            )
        else:
            trace_rows = await repo._get(  # noqa: SLF001
                "/rest/v1/traces",
                params={
                    "share_token": f"eq.{share_token}",
                    "is_public": "eq.true",
                    "select": "id,code,steps,user_id",
                    "limit": "1",
                },
            )
        if not trace_rows:
            raise trace_not_found_404()
        trace = trace_rows[0]
        fp = compute_fingerprint(trace.get("code", ""), trace.get("steps", []))
        fp_row = await repo.upsert_fingerprint(
            trace_id=trace["id"],
            user_id=trace.get("user_id"),
            payload=fp.to_dict(),
        )
        if not fp_row:
            raise HTTPException(status_code=502, detail="fingerprint_compute_failed")

    payload = _fingerprint_to_payload(fp_row)
    fp_obj = Fingerprint(
        branches=payload["branches"],
        recursion_depth=payload["recursion_depth"],
        exception_types=list(payload["exception_types"]),
        loop_iterations=payload["loop_iterations"],
        total_steps=payload["total_steps"],
        conceptual_complexity=payload["conceptual_complexity"],
        total_duration_ms=payload["total_duration_ms"],
        ast_metrics=payload.get("ast_metrics", {}),
    )

    code = await _maybe_fetch_code(repo, fp_row.trace_id)
    svg = render_fingerprint_svg(
        fp_obj,
        title=title or "CogniTrace Trace Fingerprint",
        code_preview=code_preview(code, max_lines=6),
    )

    etag = f'W/"{fp_row.signature}"'
    headers = {
        "Cache-Control": "public, max-age=300",
        "ETag": etag,
        "Content-Type": "image/svg+xml; charset=utf-8",
    }
    if request.headers.get("if-none-match") == etag:
        # 304 lets the crawler reuse its cached card
        return Response(status_code=304, headers=headers)
    return Response(content=svg, media_type="image/svg+xml", headers=headers)


# ── Human share-page data endpoint ─────────────────────────────────────


@router.get("/api/fingerprint/{share_token}")
async def get_fingerprint_by_share_token(
    share_token: str,
    request: Request,
    repo: Annotated[SupabaseRepository, Depends(get_supabase_repo)],
):
    """JSON data for the human-facing `/fingerprint/[token]` page.

    Same auth model as the OG card endpoint: anonymous sees public only;
    the owner sees their own.
    """
    owner_id = await _resolve_owner_id(request)
    fp_row = await repo.get_fingerprint_by_share_token(share_token, owner_id=owner_id)
    if not fp_row:
        raise trace_not_found_404()
    return _fingerprint_to_payload(fp_row)


# ── Code preview helper ────────────────────────────────────────────────


async def _maybe_fetch_code(repo: SupabaseRepository, trace_id: str) -> str:
    """Best-effort code lookup for the OG card. Falls back to empty string.

    We don't store code in `trace_fingerprints` to keep the row small and
    because the fingerprint itself is the only thing the OG image needs to
    show — the code preview is a nice-to-have.
    """
    try:
        rows = await repo._get(  # noqa: SLF001
            "/rest/v1/traces",
            params={"id": f"eq.{trace_id}", "select": "code", "limit": "1"},
        )
        if rows:
            return rows[0].get("code", "")
    except Exception as e:  # pragma: no cover
        logger.warning("fingerprint_code_preview_failed", trace_id=trace_id, error=str(e))
    return ""

# ── T1-D: side-by-side fingerprint diff (THESIS-05 §4) ─────────────────────


async def _resolve_two_fingerprints(
    repo: SupabaseRepository,
    *,
    a: str | None,
    b: str | None,
    owner_id: str | None,
) -> tuple[dict, dict, str, str]:
    """Resolve the two inputs (share_token or trace_id) to fingerprint payloads.

    Both `a` and `b` are accepted as either a `trace_id` or a `share_token`;
    we disambiguate by trying `get_fingerprint_by_share_token` first when the
    value looks like a token (hex, length 16), and falling back to the
    trace-id lookup. Returns `(payload_a, payload_b, kind_a, kind_b)` where
    `kind_*` is either `"share_token"` or `"trace_id"` (useful for the
    shareable link).
    """
    # Heuristic: a 32-char hex string without dashes is almost always the
    # random share_token (`secrets.token_hex(16)`). UUIDs always have
    # dashes. This isn't airtight but it's enough to disambiguate in the
    # share-link workflow the THESIS-05 §4 demo uses.
    def _looks_like_share_token(s: str) -> bool:
        return bool(s) and len(s) >= 16 and "-" not in s

    a_is_token = _looks_like_share_token(a or "")
    b_is_token = _looks_like_share_token(b or "")

    if a_is_token:
        row_a = await repo.get_fingerprint_by_share_token(a or "", owner_id=owner_id)
        if not row_a:
            raise trace_not_found_404()
        payload_a = _fingerprint_to_payload(row_a)
    else:
        row_a = await _ensure_fingerprint_for_trace(repo, a or "")
        if not row_a:
            raise trace_not_found_404()
        payload_a = _fingerprint_to_payload(row_a)

    if b_is_token:
        row_b = await repo.get_fingerprint_by_share_token(b or "", owner_id=owner_id)
        if not row_b:
            raise trace_not_found_404()
        payload_b = _fingerprint_to_payload(row_b)
    else:
        row_b = await _ensure_fingerprint_for_trace(repo, b or "")
        if not row_b:
            raise trace_not_found_404()
        payload_b = _fingerprint_to_payload(row_b)

    return (
        payload_a,
        payload_b,
        "share_token" if a_is_token else "trace_id",
        "share_token" if b_is_token else "trace_id",
    )


@router.get("/api/diff/fingerprint")
async def get_fingerprint_diff(
    a: str,
    b: str,
    request: Request,
    repo: Annotated[SupabaseRepository, Depends(get_supabase_repo)],
):
    """Return the structural delta between two fingerprints.

    Both `a` and `b` accept either a `share_token` or a `trace_id`. The
    endpoint is what powers the `/tracer/compare` page (THESIS-05 §4,
    T1-D "Fingerprint Comparison / Trace Diff").

    The diff is field-level (branches, loop iterations, recursion, …) plus
    a short narrative per delta. The frontend walks the trace steps for a
    line-by-line walkthrough, so this endpoint only returns the aggregated
    structural change — keeping the wire payload small.

    Auth model: same as the OG card. Anonymous callers can diff public
    traces only; the owner can diff their own private traces.
    """
    owner_id = await _resolve_owner_id(request)
    payload_a, payload_b, kind_a, kind_b = await _resolve_two_fingerprints(
        repo, a=a, b=b, owner_id=owner_id
    )
    deltas = diff_fingerprints_from_payloads(payload_a, payload_b)
    # Lightweight summary — the page can render the count + max-significant
    # delta without walking the full list.
    significant_count = sum(1 for d in deltas if d.get("significant"))
    summary = (
        f"{len(deltas)} field difference{'s' if len(deltas) != 1 else ''}; "
        f"{significant_count} significant"
        if deltas
        else "identical fingerprints — the two traces produce the same structural signature"
    )
    return {
        "a": payload_a,
        "b": payload_b,
        "a_kind": kind_a,
        "b_kind": kind_b,
        "deltas": deltas,
        "summary": summary,
        "identical": len(deltas) == 0,
    }


@router.get("/api/fingerprint/diff/card.svg")
async def get_fingerprint_diff_card_svg(
    a: str,
    b: str,
    request: Request,
    repo: Annotated[SupabaseRepository, Depends(get_supabase_repo)],
):
    """Render the diff between two fingerprints as a shareable SVG card.

    Reuses the same fingerprint + delta computation as
    `/fingerprint/diff` and adds the SVG rendering so the result can be
    shared on social / linked from the OG-image pipeline (THESIS-05 §4).
    """
    owner_id = await _resolve_owner_id(request)
    payload_a, payload_b, kind_a, kind_b = await _resolve_two_fingerprints(
        repo, a=a, b=b, owner_id=owner_id
    )
    deltas = diff_fingerprints_from_payloads(payload_a, payload_b)
    significant = sum(1 for d in deltas if d.get("significant"))
    summary = (
        f"{len(deltas)} field differences · {significant} significant"
        if deltas
        else "identical fingerprints"
    )
    a_fp_obj = Fingerprint(
        branches=payload_a["branches"],
        recursion_depth=payload_a["recursion_depth"],
        exception_types=list(payload_a["exception_types"]),
        loop_iterations=payload_a["loop_iterations"],
        total_steps=payload_a["total_steps"],
        conceptual_complexity=payload_a["conceptual_complexity"],
        total_duration_ms=payload_a["total_duration_ms"],
        ast_metrics=payload_a.get("ast_metrics", {}),
    )
    b_fp_obj = Fingerprint(
        branches=payload_b["branches"],
        recursion_depth=payload_b["recursion_depth"],
        exception_types=list(payload_b["exception_types"]),
        loop_iterations=payload_b["loop_iterations"],
        total_steps=payload_b["total_steps"],
        conceptual_complexity=payload_b["conceptual_complexity"],
        total_duration_ms=payload_b["total_duration_ms"],
        ast_metrics=payload_b.get("ast_metrics", {}),
    )

    # Side-by-side compact strings, with arrow between them
    left = a_fp_obj.short()
    right = b_fp_obj.short()
    delta_rows = "".join(
        f'<tr><td>{_xml(d["label"])}</td>'
        f'<td>{_xml(str(d["a_value"]))}</td>'
        f'<td>{_xml(str(d["b_value"]))}</td>'
        f'<td>{_xml(d["narrative"])}</td></tr>'
        for d in deltas[:6]
    )
    width = 720
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="420" viewBox="0 0 {width} 420" role="img" aria-label="CogniTrace fingerprint diff card">
  <defs>
    <linearGradient id="bg2" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#0f172a"/>
      <stop offset="100%" stop-color="#1e1b4b"/>
    </linearGradient>
    <style>
      .title {{ font: 600 16px/1.2 -apple-system, "Segoe UI", system-ui, sans-serif; fill:#e2e8f0; letter-spacing:0.04em; }}
      .subtle {{ font: 400 12px/1.4 -apple-system, "Segoe UI", system-ui, sans-serif; fill:#94a3b8; }}
      .mono {{ font: 600 18px/1.3 ui-monospace, "JetBrains Mono", "Cascadia Code", Menlo, monospace; fill:#f1f5f9; }}
      .diff td {{ font: 500 12px/1.6 ui-monospace, monospace; fill:#cbd5e1; }}
      .diff td:first-child {{ fill:#64748b; }}
      .footer {{ font: 500 11px/1.4 -apple-system, sans-serif; fill:#64748b; letter-spacing:0.08em; }}
    </style>
  </defs>
  <rect width="{width}" height="420" fill="url(#bg2)" rx="14"/>
  <rect x="14" y="14" width="{width - 28}" height="392" fill="none" stroke="#312e81" stroke-width="1" rx="10"/>
  <g transform="translate(28, 36)">
    <text class="title">COGNITRACE · TRACE DIFF</text>
    <text class="subtle" y="20">{_xml(summary)}</text>
  </g>
  <g transform="translate(28, 110)">
    <text class="mono">{_xml(left)}</text>
    <text class="subtle" x="280">→</text>
    <text class="mono" x="310">{_xml(right)}</text>
  </g>
  <g transform="translate(28, 170)">
    <table class="diff">
      {delta_rows}
    </table>
  </g>
  <g transform="translate(28, 392)">
    <text class="footer">FINGERPRINT DIFF · THESIS CONTRIBUTION #4</text>
  </g>
</svg>'''
    return Response(
        content=svg.encode("utf-8"),
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=300"},
    )


# ── T1-D: from-code fingerprint (paste-flow support) ────────────────────────


class FromCodeRequest(BaseModel):
    code: str
    steps: list[dict] | None = None


@router.post("/api/fingerprint/from-code")
async def fingerprint_from_code(req: FromCodeRequest):
    """Compute (without persisting) the fingerprint for arbitrary Python code.

    Powers the paste-flow on `/tracer/compare` — students paste two snippets
    and we need a fingerprint *immediately* without going through a saved
    trace. The result is the same wire payload as `/traces/{id}/fingerprint`.

    Auth: NOT required — the classifier is pure AST + trace-step analysis,
    no DB rows involved. We don't write anything; the response is the
    same dict a saved trace would emit if it had the given code+steps.
    """
    code = req.code or ""
    steps = req.steps or []
    fp = compute_fingerprint(code, steps)
    return fp.to_dict()

