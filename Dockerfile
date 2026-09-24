# CogniTrace Backend — Railway Production Dockerfile
#
# This file lives at the repo ROOT (not in backend/) because Railway's
# dockerfilePath setting does NOT change the build context. The context
# is always the Root Directory, which defaults to the repo root.
#
# Build commands effectively run as:
#   docker build -f Dockerfile .        (with Root Directory = /)
#
# All COPY paths are therefore relative to the repo root and prefixed
# with `backend/`. The resulting image runs the FastAPI app from /app.

# ---- Stage 1: install Python dependencies into /install ---------------
FROM python:3.12-slim AS builder

WORKDIR /install
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ---- Stage 2: runtime image with the API only -------------------------
FROM python:3.12-slim

WORKDIR /app

# Pull installed packages from the builder stage.
COPY --from=builder /install /usr/local

# Copy only what we need to run the API. Avoid `COPY backend/. .` because
# it pulls in backend/tests/, backend/.coverage, backend/.pytest_cache,
# etc. which bloat the image.
COPY backend/app ./app
COPY backend/tracer ./tracer
COPY backend/analyzers ./analyzers
COPY backend/scripts ./scripts

# Run as a non-privileged user. Defence in depth in case the sandbox in
# app.services.tracer_runner ever fails closed.
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

# Railway injects $PORT. Local docker compose uses 8000. Honour $PORT so
# the same image runs on Railway, locally, and in CI.
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:'+__import__('os').environ.get('PORT','8000')+'/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
