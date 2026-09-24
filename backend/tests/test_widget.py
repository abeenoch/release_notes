"""Embeddable widget: /widget.js served, CORS open ONLY for /api/public/*."""
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models.user  # noqa: F401 — register mappers
import app.models.repo  # noqa: F401
import app.models.changelog  # noqa: F401
import app.models.user_config  # noqa: F401
import app.models.notify_config  # noqa: F401
import app.models.subscriber  # noqa: F401

from app.core.dependencies import get_db
from app.database import Base
from app.main import app


@pytest_asyncio.fixture
async def client():
    """TestClient with the app's DB dependency swapped for in-memory SQLite.

    No lifespan → init_db never touches the real dev database.
    """
    engine = create_async_engine("sqlite+aiosqlite://", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _override():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override
    try:
        with TestClient(app) as c:  # `with` runs lifespan; init_db is a no-op here (override)
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


def test_widget_js_is_served(client):
    resp = client.get("/widget.js")
    assert resp.status_code == 200
    assert "javascript" in resp.headers["content-type"]
    # The widget must actually be the shadow-DOM embedder, not the SPA shell.
    assert "attachShadow" in resp.text
    assert "data-repo" in resp.text


def test_widget_js_not_the_spa_fallback(client):
    """/widget.js must never return index.html (the catch-all would)."""
    resp = client.get("/widget.js")
    assert "<!DOCTYPE html>" not in resp.text


def test_public_api_gets_open_cors(client):
    """Third-party widget sites must be able to read /api/public/*."""
    resp = client.get("/api/public/nobody/nothing", headers={"Origin": "https://blog.example"})
    assert resp.status_code == 404
    assert resp.headers.get("access-control-allow-origin") == "*"


def test_authenticated_api_keeps_strict_cors(client):
    """The wildcard must NOT bleed onto authenticated endpoints."""
    resp = client.get("/api/health", headers={"Origin": "https://blog.example"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") != "*"
