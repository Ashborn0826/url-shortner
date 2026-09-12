"""Pytest fixtures shared across the test suite.

We use a temp-file SQLite (not :memory:) so multiple engines pointing at
the same file can share data. The `db_setup` fixture creates tables and
monkey-patches the global engine + AsyncSessionLocal so that
`persist_click` (which uses the globals via a late import) writes to
the test database instead of opening its own connection.
"""
import os
import tempfile

_test_db_path = os.path.join(tempfile.gettempdir(), "url_shortener_test.db")
os.environ.setdefault("DATABASE_URL", f"sqlite+aiosqlite:///{_test_db_path}")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

import pytest_asyncio
from fakeredis import aioredis as fakeredis_aio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.cache.redis_client import get_redis
from app.db.models import Base
from app.db.session import get_session
from app.main import create_app


@pytest_asyncio.fixture
async def db_setup(monkeypatch):
    """Create tables in a temp-file SQLite and patch the global engine +
    AsyncSessionLocal so persist_click writes to the same DB the tests read.
    """
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    new_session_local = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr("app.db.session.engine", engine)
    monkeypatch.setattr("app.db.session.AsyncSessionLocal", new_session_local)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def redis_client():
    client = fakeredis_aio.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def app(db_setup, redis_client):
    """Fresh FastAPI app per test, with get_session and get_redis overridden."""
    SessionLocal = async_sessionmaker(db_setup, expire_on_commit=False)

    async def _override_session():
        async with SessionLocal() as session:
            yield session

    application = create_app()
    application.dependency_overrides[get_session] = _override_session
    application.dependency_overrides[get_redis] = lambda: redis_client
    yield application


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest_asyncio.fixture
async def session(db_setup):
    """Standalone AsyncSession for repository-level tests."""
    SessionLocal = async_sessionmaker(db_setup, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session