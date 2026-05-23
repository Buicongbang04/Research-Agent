"""Shared pytest fixtures."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.db.session import AsyncSessionLocal, engine
from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_clean() -> AsyncGenerator[None, None]:
    """Truncate user-scoped tables before each test for isolation."""
    async with AsyncSessionLocal() as session:
        # Cascading truncate handles dependent rows
        await session.execute(
            text("TRUNCATE TABLE users, reports, conversations, messages, memories RESTART IDENTITY CASCADE")
        )
        await session.commit()
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_clean) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
