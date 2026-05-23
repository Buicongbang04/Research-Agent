# syntax=docker/dockerfile:1.7

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps: libpq for psycopg2, curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
      libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifest first for layer caching
COPY pyproject.toml ./

# Install deps (without the project itself yet)
RUN pip install --upgrade pip && pip install \
    "fastapi>=0.115.0" "uvicorn[standard]>=0.32.0" "pydantic>=2.9.0" \
    "pydantic-settings>=2.5.0" "sqlalchemy[asyncio]>=2.0.36" "asyncpg>=0.30.0" \
    "psycopg2-binary>=2.9.10" "alembic>=1.14.0" "pgvector>=0.3.6" \
    "passlib[bcrypt]>=1.7.4" "bcrypt==4.0.1" "python-jose[cryptography]>=3.3.0" \
    "python-multipart>=0.0.12" "httpx>=0.27.2" "arxiv>=2.1.3" \
    "langgraph>=0.2.50" "langchain-core>=0.3.20" "celery[redis]>=5.4.0" \
    "redis>=5.2.0" "sse-starlette>=2.1.3" "email-validator>=2.2.0"

# Copy application source and install in editable mode (cheap, just registers package)
COPY . .
RUN pip install -e . --no-deps

EXPOSE 8000

# Default command runs migrations then API; override for Celery worker.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
