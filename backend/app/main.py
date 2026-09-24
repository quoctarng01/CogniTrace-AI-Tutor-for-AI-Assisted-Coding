"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    dashboard,
    examples,
    fingerprint,
    llm,
    metrics,
    profiles,
    ratings,
    review,
    static_analysis,
    traces,
    traces_save,
    traces_share,
)
from app.routers.analytics import router as analytics_router
from app.routers.load import router as load_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown hooks."""
    import httpx

    from app.config import settings

    # Initialize global HTTP client with connection pooling
    limits = httpx.Limits(max_keepalive_connections=20, max_connections=100)
    app.state.http_client = httpx.AsyncClient(limits=limits, timeout=10.0)

    # Validate at least one LLM provider is configured
    import logging
    has_ollama = bool(settings.ollama_cloud_url)
    has_github = bool(settings.github_models_pat)

    if not has_ollama and not has_github:
        logging.error(
            "HI-05: No LLM provider configured. "
            "Set OLLAMA_CLOUD_URL or GITHUB_MODELS_PAT. "
            "AI explanations will not work."
        )

    if has_ollama:
        logging.info("llm_provider_ready", extra={"provider": "ollama_cloud", "url": settings.ollama_cloud_url})
    if has_github:
        logging.info("llm_provider_ready", extra={"provider": "github_models"})

    # Workstream 10 — start the metrics rollup loop. Cancelled cleanly on shutdown.
    import asyncio

    from app.services.metrics_aggregator import run_periodically

    rollup_task = asyncio.create_task(run_periodically())
    app.state.rollup_task = rollup_task

    yield

    # Shutdown: close http clients + cancel background tasks
    rollup_task.cancel()
    try:
        await rollup_task
    except asyncio.CancelledError:
        pass

    await app.state.http_client.aclose()

    from app.services.llm_router import llm_router
    await llm_router.close()


app = FastAPI(
    title="CogniTrace API",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS Middleware ──────────────────────────────────────────────────────────
# Added before routers to make execution order visually obvious.
from app.config import settings  # noqa: E402

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request correlation ID middleware ─────────────────────────────────────────
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add correlation ID to each request for tracing."""
    import structlog
    request_id = request.headers.get("x-request-id", str(uuid4()))
    structlog.contextvars.bind_contextvars(request_id=request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# ── Pilot study session middleware ────────────────────────────────────────
# When a pilot participant's frontend sends `X-Study-Session: <uuid>` on any
# request, this middleware binds the UUID to a context-var so service-layer
# code (LLM router, cache, etc.) can attach it to telemetry rows without
# explicit plumbing. For production traffic without the header, this is a
# zero-cost no-op. See `app/services/study_session.py` and migration V013.
@app.middleware("http")
async def study_session_middleware(request: Request, call_next):
    """Bind X-Study-Session UUID to a context-var for telemetry tagging.

    For production traffic without the header, this is a zero-cost no-op
    (the helper reads no header and writes nothing). See
    `app/services/study_session.py` and migration V013.
    """
    from app.services.study_session import bind_study_session_id

    bind_study_session_id(request.headers.get("x-study-session"))
    return await call_next(request)

# ── SlowAPI rate limiting ─────────────────────────────────────────
# Must be added BEFORE any routes that use @limiter.limit()
try:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    # Importing the shared module also instantiates the limiter as a
    # side-effect — every router pulls `_rate_limit` from there.
    from app.rate_limit_decorator import _limiter

    app.state.limiter = _limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
except ImportError:
    pass  # slowapi not installed — rate limiting disabled

app.include_router(traces.router, prefix="/api")
app.include_router(traces_save.router, prefix="/api")
app.include_router(traces_share.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")
# Workstream 12 — Trace Fingerprint (thesis Contribution #4). The router
# owns its own JSON + OG-card endpoints under /api and /fingerprint; it is
# mounted WITHOUT a prefix so /fingerprint/{token}/card.svg resolves
# directly (Twitter/Discord crawlers hit that path verbatim).
app.include_router(fingerprint.router)
app.include_router(llm.router, prefix="/api/llm")
app.include_router(review.router, prefix="/api/review")
app.include_router(profiles.router, prefix="/profiles")
app.include_router(static_analysis.router, prefix="/api")
app.include_router(examples.router, prefix="/api/examples")
app.include_router(ratings.router)
app.include_router(analytics_router, prefix="/api")
# T1-A: Cognitive Load Dashboard
app.include_router(load_router)




@app.get("/")
async def root():
    """Root endpoint showing status and link to docs."""
    return {"message": "CogniTrace API is running. Go to /docs for Swagger documentation."}


@app.get("/health")
async def health(request: Request):
    """
    Health check endpoint for Docker/liveness probes + readiness probes.
    Checks Supabase, Redis, and LLM provider connectivity.
    """
    from fastapi.responses import JSONResponse

    from app.config import settings

    client = request.app.state.http_client
    checks: dict[str, dict[str, str | bool]] = {}
    all_ok = True

    # Check Supabase connectivity
    try:
        resp = await client.get(
            f"{settings.supabase_url}/rest/v1/",
            headers={"apikey": settings.supabase_service_key},
            timeout=3.0,
        )
        checks["supabase"] = {
            "ok": resp.status_code == 200,
            "detail": "ok" if resp.status_code == 200 else f"error:{resp.status_code}"
        }
        if resp.status_code != 200:
            all_ok = False
    except Exception as e:
        checks["supabase"] = {"ok": False, "detail": f"error:{type(e).__name__}"}
        all_ok = False

    # Check Redis connectivity
    if settings.redis_enabled:
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.redis_url, socket_connect_timeout=3)
            await r.ping()
            await r.aclose()
            checks["redis"] = {"ok": True, "detail": "ok"}
        except Exception as e:
            checks["redis"] = {"ok": False, "detail": f"error:{type(e).__name__}"}
            all_ok = False
    else:
        checks["redis"] = {"ok": True, "detail": "disabled"}

    # Check LLM provider connectivity
    try:
        if settings.ollama_cloud_url:
            resp = await client.get(f"{settings.ollama_cloud_url}/api/tags", timeout=5.0)
            checks["llm"] = {
                "ok": resp.status_code == 200,
                "detail": "ok" if resp.status_code == 200 else f"error:{resp.status_code}"
            }
        elif settings.github_models_pat:
            checks["llm"] = {"ok": True, "detail": "github_models_configured"}
        else:
            checks["llm"] = {"ok": True, "detail": "no_llm_provider"}
    except Exception as e:
        checks["llm"] = {"ok": False, "detail": f"error:{type(e).__name__}"}
        all_ok = False

    # Return 200 even if degraded to prevent orchestrator reboot loops,
    # as the backend itself is responsive and running.
    return JSONResponse(
        {"status": "healthy" if all_ok else "degraded", "checks": checks},
        status_code=200,
    )
