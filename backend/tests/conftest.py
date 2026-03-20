import os
import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from httpx import AsyncClient, ASGITransport
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, patch
import tempfile

# -------------------------------------------------------------------
# Set environment variables BEFORE importing any app modules
# -------------------------------------------------------------------
os.environ['HIVEBOT_DATA'] = './test_data'
os.environ['INTERNAL_API_KEY'] = 'test-internal-key'

# Override log directory to a temporary location (prevent /app/logs creation)
os.environ['HIVEBOT_LOG_DIR'] = tempfile.mkdtemp()

# Ensure the test data directory exists
os.makedirs('./test_data', exist_ok=True)
os.makedirs('./test_data/secrets', exist_ok=True)

# -------------------------------------------------------------------
# Create the test database engine and sessionmaker
# -------------------------------------------------------------------
TEST_DATABASE_URL = "postgresql+asyncpg://hivebot:hivebot@localhost/hivebot_test"

_test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
_test_sessionmaker = sessionmaker(_test_engine, class_=AsyncSession, expire_on_commit=False)

# -------------------------------------------------------------------
# Patch the global AsyncSessionLocal BEFORE any app modules are imported
# -------------------------------------------------------------------
import app.core.database
app.core.database.AsyncSessionLocal = _test_sessionmaker

# -------------------------------------------------------------------
# Now import the rest of the app modules (they will use the patched sessionmaker)
# -------------------------------------------------------------------
from app.main import app as fastapi_app
from app.core.config import settings
from app.services.redis_service import redis_service

# -------------------------------------------------------------------
# Session‑scoped autouse fixture to create/drop tables and clean up the engine
# -------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
async def setup_test_db():
    """Create tables before any tests and dispose the engine after all tests."""
    async with _test_engine.begin() as conn:
        await conn.run_sync(app.core.database.Base.metadata.drop_all)
        await conn.run_sync(app.core.database.Base.metadata.create_all)
    yield
    await _test_engine.dispose()


# -------------------------------------------------------------------
# Function‑scoped fixtures
# -------------------------------------------------------------------
@pytest.fixture(scope="function")
def event_loop() -> Generator:
    """Provide a new event loop for each test function."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for tests that need it."""
    async with app.core.database.AsyncSessionLocal() as session:
        yield session
        await session.rollback()


# -------------------------------------------------------------------
# Autouse fixtures for mocking Redis and settings
# -------------------------------------------------------------------
@pytest.fixture(autouse=True)
def mock_redis():
    """Mock Redis client for every test."""
    redis_mock = AsyncMock()
    redis_mock.ping = AsyncMock(return_value=True)
    redis_mock.publish = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock()
    redis_mock.delete = AsyncMock()
    redis_mock.client = redis_mock  # for direct attribute access

    with patch.object(redis_service, 'client', redis_mock):
        yield


@pytest.fixture(autouse=True)
def patch_settings():
    """Mock settings.secrets.get to return a test key."""
    with patch.object(settings.secrets, 'get', side_effect=lambda key, default=None: 'test-internal-key' if key == 'INTERNAL_API_KEY' else default):
        yield


# -------------------------------------------------------------------
# HTTP client fixture with dependency override
# -------------------------------------------------------------------
@pytest.fixture
async def client(session) -> AsyncGenerator:
    """Provide an HTTP client with the test session injected."""

    async def override_get_db():
        yield session

    fastapi_app.dependency_overrides[app.core.database.get_db] = override_get_db

    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    fastapi_app.dependency_overrides.clear()
