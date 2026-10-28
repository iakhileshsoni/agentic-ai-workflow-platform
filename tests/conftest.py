"""Pytest Shared Fixtures and Setup."""
import asyncio
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.core.config import settings
from app.db.session import init_db
from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_test_db():
    """Ensure DB tables are initialized before each test."""
    await init_db()
    yield


@pytest_asyncio.fixture
async def async_client():
    """Yield an HTTPX AsyncClient wired to the FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
