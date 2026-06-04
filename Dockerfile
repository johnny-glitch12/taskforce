# ============================================================================
# Task Force AI — Multi-stage Docker build (Railway / single-container deploy)
# ----------------------------------------------------------------------------
# Stage 1 builds the React frontend (CRA via CRACO) to /app/frontend/build.
# Stage 2 installs the FastAPI backend + copies the build output into
# `backend/static/` where server.py auto-mounts it as the SPA.
# Container exposes a single port serving both the API (under /api/*) and
# the React SPA (everything else).
# ============================================================================

# ── Stage 1: build React frontend ────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Install deps first (better layer cache).
# We use `npm install` (not `npm ci`) so the build works whether or not a
# package-lock.json is committed to the repo — CRA + React 19 mixed deps
# also need --legacy-peer-deps to bypass the npm 7+ strict resolver.
COPY frontend/package.json frontend/package-lock.json* frontend/yarn.lock* ./
RUN npm install --no-audit --no-fund --legacy-peer-deps

# Copy source and build
COPY frontend/ ./

# Disable source maps + lint failures to keep the image small and fast.
ENV GENERATE_SOURCEMAP=false
ENV DISABLE_ESLINT_PLUGIN=true
ENV CI=false

# PUBLIC_URL=/spa rewrites every CRA-generated asset reference to
# /spa/static/js/main.<hash>.js etc. This avoids colliding with the
# existing `/static/*` mount (csdrop debug images + exchange uploads).
ENV PUBLIC_URL=/spa

# The build defaults REACT_APP_BACKEND_URL to "" so all fetches resolve
# to relative `/api/...` paths against the FastAPI container that serves
# the SPA. Override at build time if you want to point at a separate API.
ARG REACT_APP_BACKEND_URL=""
ENV REACT_APP_BACKEND_URL=${REACT_APP_BACKEND_URL}

RUN npm run build


# ── Stage 2: Python backend + serve frontend ────────────────────────────────
FROM python:3.11-slim AS runtime

# System deps needed for several Python wheels (cryptography, magic, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc g++ libffi-dev libssl-dev curl libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install backend Python deps first (layer cache)
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy backend + scripts
COPY backend/ /app/backend/
COPY scripts/ /app/scripts/

# Copy built frontend into backend/spa — server.py auto-mounts when
# this directory exists. We intentionally use `spa/` (not `static/`)
# because `static/` is already in use by the csdrop debug images.
COPY --from=frontend-builder /app/frontend/build/ /app/backend/spa/

# Scratch dirs for the agent runtime (sandbox venvs / per-run workdirs).
RUN mkdir -p /tmp/agent_workdir /tmp/agent_venvs

# Production env defaults — overridden by Railway dashboard variables.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    PYTHONPATH=/app/backend

# Railway injects PORT at runtime — bind to it.
EXPOSE 8000

WORKDIR /app/backend

# Single-container start: launches Celery worker in the background and then
# Uvicorn in the foreground. If Celery dies the container stays up (the API
# is still healthy). For high-volume production, split worker into a separate
# Railway service using Dockerfile.worker.
CMD ["bash", "/app/scripts/start.sh"]
