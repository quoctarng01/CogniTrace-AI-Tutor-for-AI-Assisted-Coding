"""FastAPI application entry point."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import traces, llm, review, profiles, static_analysis, examples, ratings


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    """
    Health check endpoint for Docker/liveness probes + readiness probes.
    Checks Supabase connectivity.
    """
    from app.config import settings
    import httpx
    
    checks: dict = {"status": "ok", "checks": {}}
    healthy = True
    
    # Check Supabase connectivity
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(
                f"{settings.supabase_url}/rest/v1/",
                headers={"apikey": settings.supabase_service_key},
            )
            checks["checks"]["supabase"] = "ok" if resp.status_code == 200 else f"error:{resp.status_code}"
            if resp.status_code != 200:
                healthy = False
    except Exception as e:
        checks["checks"]["supabase"] = f"error:{type(e).__name__}"
        healthy = False
    
    checks["status"] = "ok" if healthy else "degraded"
    from fastapi.responses import JSONResponse
    return JSONResponse(content=checks, status_code=200 if healthy else 503)
