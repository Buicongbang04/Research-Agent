"""FastAPI application entrypoint."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.logging import configure_logging

configure_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Research Agent API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.APP_ENV}


from app.api import auth as auth_router  # noqa: E402
from app.api import chat as chat_router  # noqa: E402
from app.api import research as research_router  # noqa: E402

app.include_router(auth_router.router, prefix="/auth", tags=["auth"])
app.include_router(research_router.router, prefix="/research", tags=["research"])
app.include_router(chat_router.router, prefix="/chat", tags=["chat"])
