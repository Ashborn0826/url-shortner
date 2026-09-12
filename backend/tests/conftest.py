"""Pytest fixtures shared across the test suite.

Phase 1 only needs the FastAPI app + httpx client wired against a fresh
in-memory SQLite database per test. Phase 2+ will extend this file with a
Redis client (fakeredis) and worker setup.
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.models import Base
from app.db.session import get_session
from app.main import create_app


@pytest_asyncio.fixture
async def app():
    """Fresh in-memory SQLite + dependency-overridden FastAPI app per test."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

    async def _override_session():
        async with TestSessionLocal() as session:
            yield session

    application = create_app()
    application.dependency_overrides[get_session] = _override_session
    yield application

    await test_engine.dispose()


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest_asyncio.fixture
async def session():
    """Standalone AsyncSession for repository-level tests."""
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)
    async with TestSessionLocal() as session:
        yield session
    await test_engine.dispose()