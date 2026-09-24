"""LLM router — /api/llm/* endpoints (explanation streaming).

Workstream 11: thesis-defense "wow" demo.

Endpoint:
  GET /api/llm/ab

Runs two parallel LLM explanations of the same (code, line):
  - GROUNDED: the normal system prompt + runtime variable state.
  - BLIND:    a stripped prompt with no system instruction about trace
              grounding and no `locals_dict`. Mirrors the RQ1 Condition A
              protocol (THESIS-W1-RESULTS.md §2.2).

Both streams are multiplexed over a single SSE connection to the browser.
After both finish, a judge (same provider chain, RQ1 0/1/2 rubric) scores
each side. The verdict is emitted last.

SSE event names:
  - "grounded":  {"token": "...", "provider": "ollama_cloud"}
  - "blind":     {"token": "...", "provider": "github_models"}
  - "grounded_done": {"provider": "..."}
  - "blind_done":    {"provider": "..."}
  - "verdict":   {"blind_score": 0|1|2, "grounded_score": 0|1|2,
                  "blind_reasoning": str, "grounded_reasoning": str,
                  "winner": "grounded"|"blind"|"tie"}
  - "error":     {"message": "..."}
  - "done":      {"ok": true}
"""
from __future__ import annotations

import asyncio
import json
import logging
import time

from fastapi import APIRouter, Header, Query, Request
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.services.llm_router import LLMProvider, llm_router
from app.services.llm_prompts import FALLBACK_AB_VERDICT

logger = logging.getLogger("codescope.llm_ab")

router = APIRouter()


@router.get("/ab")
async def stream_ab_comparison(
    request: Request,
    code: str = Query(..., max_length=5000),
    line_number: int = Query(..., ge=1),
    line_content: str = Query(..., max_length=500),
    locals_json: str = Query(..., max_length=2000),
    authorization: str | None = Header(None),
):
    """
    Stream a side-by-side grounded-vs-blind comparison of the same explanation.

    Designed for the thesis-defense "wow" demo (THESIS-W1-RESULTS.md,
    Contribution 1). Anonymous traffic allowed; no auth required.
    """
    try:
        locals_dict = json.loads(locals_json)
    except json.JSONDecodeError:
        locals_dict = {}

    # If a user is authenticated, forward their custom API key so the
    # ablation honors the user's preferred provider (consistent with /explain/stream).
    kwargs: dict = {}
    if authorization and authorization.startswith("Bearer "):
        try:
            from app.dependencies import get_profile_settings
            from app.routers.auth import get_profile_id

            token = authorization[7:]
            profile_id = await get_profile_id(token)
            if profile_id:
                custom = await get_profile_settings(profile_id)
                if custom:
                    if custom.get("github_models_pat"):
                        kwargs["github_models_pat"] = custom["github_models_pat"]
                    if custom.get("custom_api_url"):
                        kwargs["custom_api_url"] = custom["custom_api_url"]
                    if custom.get("custom_api_key"):
                        kwargs["custom_api_key"] = custom["custom_api_key"]
                    if custom.get("custom_api_model"):
                        kwargs["custom_api_model"] = custom["custom_api_model"]
        except Exception:
            pass  # anonymous or invalid token — fall through with empty kwargs

    async def event_generator():
        grounded_chunks: list[str] = []
        blind_chunks: list[str] = []
        grounded_provider = LLMProvider.GITHUB_MODELS
        blind_provider = LLMProvider.GITHUB_MODELS
        grounded_started_at = time.perf_counter()
        blind_started_at = time.perf_counter()

        async def run_grounded():
            nonlocal grounded_provider
            try:
                async for token, provider in llm_router.stream_explain(
                    code=code,
                    line_number=line_number,
                    line_content=line_content,
                    locals_dict=locals_dict,
                    **kwargs,
                ):
                    if token == "__done__":
                        grounded_provider = provider
                        return
                    grounded_chunks.append(token)
                    yield ("grounded", {"token": token, "provider": provider.value})
            except Exception as e:
                logger.error("ab_grounded_failed err=%s", e)
                yield ("error", {"message": f"grounded stream failed: {e}"})

        async def run_blind():
            nonlocal blind_provider
            try:
                async for token, provider in llm_router.stream_explain_blind(
                    code=code,
                    line_number=line_number,
                    line_content=line_content,
                    **kwargs,
                ):
                    if token == "__done__":
                        blind_provider = provider
                        return
                    blind_chunks.append(token)
                    yield ("blind", {"token": token, "provider": provider.value})
            except Exception as e:
                logger.error("ab_blind_failed err=%s", e)
                yield ("error", {"message": f"blind stream failed: {e}"})

        async def merge(async_iter):
            async for event_name, payload in async_iter:
                yield event_name, payload

        async def run_both():
            # Drain both streams in parallel; whichever yields a token first wins
            # for that tick. We use asyncio.wait on two queues.
            grounded_q: asyncio.Queue = asyncio.Queue()
            blind_q: asyncio.Queue = asyncio.Queue()
            grounded_done = asyncio.Event()
            blind_done = asyncio.Event()

            async def pump_grounded():
                try:
                    async for ev, payload in merge(run_grounded()):
                        await grounded_q.put((ev, payload))
                finally:
                    grounded_done.set()

            async def pump_blind():
                try:
                    async for ev, payload in merge(run_blind()):
                        await blind_q.put((ev, payload))
                finally:
                    blind_done.set()

            t_grounded = asyncio.create_task(pump_grounded())
            t_blind = asyncio.create_task(pump_blind())

            pending = 2
            while pending > 0:
                got_anything = False
                if not grounded_q.empty():
                    ev, payload = await grounded_q.get()
                    yield ev, payload
                    got_anything = True
                if not blind_q.empty():
                    ev, payload = await blind_q.get()
                    yield ev, payload
                    got_anything = True
                if grounded_done.is_set() and not blind_done.is_set():
                    if grounded_q.empty():
                        pending -= 1  # noqa: F841 (kept for clarity)
                if blind_done.is_set() and not grounded_done.is_set():
                    if blind_q.empty():
                        pass
                # If both done and both queues empty, exit.
                if (
                    grounded_done.is_set()
                    and blind_done.is_set()
                    and grounded_q.empty()
                    and blind_q.empty()
                ):
                    pending = 0
                    break
                if not got_anything:
                    await asyncio.sleep(0.01)

            # Drain any final items
            while not grounded_q.empty():
                yield await grounded_q.get()
            while not blind_q.empty():
                yield await blind_q.get()

            await asyncio.gather(t_grounded, t_blind, return_exceptions=True)

        try:
            async for event_name, payload in run_both():
                yield {"event": event_name, "data": json.dumps(payload)}
        except Exception as e:
            logger.error("ab_event_loop_failed err=%s", e)
            yield {"event": "error", "data": json.dumps({"message": str(e)})}

        # Emit done events for each side
        yield {
            "event": "grounded_done",
            "data": json.dumps({"provider": grounded_provider.value}),
        }
        yield {
            "event": "blind_done",
            "data": json.dumps({"provider": blind_provider.value}),
        }

        # Build final text + run the judge
        grounded_text = "".join(grounded_chunks)
        blind_text = "".join(blind_chunks)

        try:
            verdict = await llm_router.judge_ab(
                code=code,
                line_number=line_number,
                line_content=line_content,
                locals_dict=locals_dict,
                blind_text=blind_text,
                grounded_text=grounded_text,
                **kwargs,
            )
        except Exception as e:
            logger.error("ab_judge_failed err=%s — using fallback verdict", e)
            verdict = dict(FALLBACK_AB_VERDICT)

        yield {"event": "verdict", "data": json.dumps(verdict)}

        # Telemetry: log the three LLM calls into llm_call_metrics. We
        # do this best-effort — failures here must not break the demo.
        try:
            await _log_ablation_metrics(
                request=request,
                grounded_provider=grounded_provider,
                blind_provider=blind_provider,
                grounded_text=grounded_text,
                blind_text=blind_text,
                verdict=verdict,
                grounded_ms=int((time.perf_counter() - grounded_started_at) * 1000),
                blind_ms=int((time.perf_counter() - blind_started_at) * 1000),
                line_number=line_number,
            )
        except Exception as e:
            logger.warning("ab_telemetry_failed err=%s", e)

        yield {"event": "done", "data": json.dumps({"ok": True})}

    return EventSourceResponse(event_generator())


async def _log_ablation_metrics(
    request: Request,
    grounded_provider: LLMProvider,
    blind_provider: LLMProvider,
    grounded_text: str,
    blind_text: str,
    verdict: dict,
    grounded_ms: int,
    blind_ms: int,
    line_number: int,
) -> None:
    """
    Best-effort insert three rows into llm_call_metrics for the demo.

    The V013 migration added `ablation_mode` and `judge_score` columns.
    We use the service-role key to bypass RLS so the demo always logs,
    even when run by an anonymous user.
    """
    if not settings.supabase_url or not settings.supabase_service_key:
        return

    client = (
        request.app.state.http_client
        if hasattr(request.app, "state") and hasattr(request.app.state, "http_client")
        else None
    )
    if client is None:
        return

    rows = [
        {
            "cache_key": "ab-grounded",
            "model_used": grounded_provider.value,
            "model_name": grounded_provider.value,
            "prompt_tokens": 0,
            "completion_tokens": len(grounded_text),
            "latency_ms": grounded_ms,
            "cache_hit": False,
            "ablation_mode": "grounded",
            "judge_score": verdict.get("grounded_score"),
        },
        {
            "cache_key": "ab-blind",
            "model_used": blind_provider.value,
            "model_name": blind_provider.value,
            "prompt_tokens": 0,
            "completion_tokens": len(blind_text),
            "latency_ms": blind_ms,
            "cache_hit": False,
            "ablation_mode": "blind",
            "judge_score": verdict.get("blind_score"),
        },
    ]

    try:
        await client.post(
            f"{settings.supabase_url}/rest/v1/llm_call_metrics",
            headers={
                "apikey": settings.supabase_service_key,
                "Authorization": f"Bearer {settings.supabase_service_key}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            },
            json=rows,
        )
    except Exception as e:
        logger.warning("ab_metrics_insert_failed err=%s", e)
