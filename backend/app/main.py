"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.routers import traces, llm, review, profiles, static_analysis, examples, ratings
from app.routers.analytics import router as analytics_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown hooks."""
    from app.config import settings
    
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
    
    yield
    
    # Shutdown: close the LLM router's HTTP client
    from app.services.llm_router import llm_router
    await llm_router.close()


app = FastAPI(
    title="CodeScope API",
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

# ── SlowAPI rate limiting ─────────────────────────────────────────
# Must be added BEFORE any routes that use @limiter.limit()
try:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    from app.routers.examples import _limiter

    app.state.limiter = _limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
except ImportError:
    pass  # slowapi not installed — rate limiting disabled

app.include_router(traces.router, prefix="/api")
app.include_router(llm.router, prefix="/api/llm")
app.include_router(review.router, prefix="/api/review")
app.include_router(profiles.router, prefix="/profiles")
app.include_router(static_analysis.router, prefix="/api")
app.include_router(examples.router, prefix="/api/examples")
app.include_router(ratings.router)
app.include_router(analytics_router, prefix="/api")




@app.get("/health")
async def health():
    """
    Health check endpoint for Docker/liveness probes + readiness probes.
    Checks Supabase, Redis, and LLM provider connectivity.
    """
    from app.config import settings
    import httpx
    from fastapi.responses import JSONResponse
    
    checks: dict[str, dict[str, str | bool]] = {}
    all_ok = True
    
    # Check Supabase connectivity
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"{settings.supabase_url}/rest/v1/",
                headers={"apikey": settings.supabase_service_key},
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
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{settings.ollama_cloud_url}/api/tags")
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
