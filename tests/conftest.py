"""Shared test fixtures."""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Ensure we have a test database and no real API keys are required
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///test_incidents.db")
os.environ.setdefault("GOOGLE_API_KEY", "test-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("LOG_LEVEL", "WARNING")


@pytest_asyncio.fixture
async def client():
    """Provide an async test client wired to the FastAPI app."""
    # Reset the settings cache so test env vars take effect
    from src.config import get_settings
    get_settings.cache_clear()

    from src.main import app
    from src.database.repository import init_db, close_db

    await init_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await close_db()

    # Cleanup test DB
    import pathlib
    db = pathlib.Path("test_incidents.db")
    if db.exists():
        db.unlink()
