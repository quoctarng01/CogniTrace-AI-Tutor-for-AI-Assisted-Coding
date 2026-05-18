"""
Legacy entry point — redirects to app.main.

This file is kept for backwards compatibility only.
All requests are now handled by app.main:app (FastAPI with lifespan hooks,
rate limiting, and comprehensive health checks).

To run the server:
    uvicorn app.main:app --reload --port 8000

Or via docker-compose / Dockerfile, which uses app.main:app by default.
"""
from app.main import app

__all__ = ["app"]
