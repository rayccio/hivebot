import os
import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from httpx import AsyncClient, ASGITransport
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, patch

# Set HIVEBOT_DATA and INTERNAL_API_KEY for tests
os.environ['HIVEBOT_DATA'] = '/tmp/hivebot_test'
os.environ['INTERNAL_API_KEY'] = 'test-internal-key'

from app.core.database import Base, get_db
from app.main import app
from app.core.config import settings
from app.services.redis_service import redis_service
import app.core.database  # to patch AsyncSessionLocal

# Ensure the temp directory exists
os.makedirs('/tmp/hivebot_test', exist_ok=True)

# Use a separate test database with NullPool to avoid connection reuse
TEST_DATABASE_URL = "postgresql+asyncpg://hivebot:hivebot@localhost/hivebot_test"

@pytest.fixture(scope="function")
def event_loop() -> Generator:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="function")
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Patch the global AsyncSessionLocal to use this engine's sessionmaker
    test_sessionmaker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    app.core.database.AsyncSessionLocal = test_sessionmaker

    yield engine
    await engine.dispose()

@pytest.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        await session.rollback()

# Autouse fixture to patch settings.secrets.get globally for all tests
@pytest.fixture(autouse=True)
def patch_settings():
    with patch.object(settings.secrets, 'get', side_effect=lambda key, default=None: 'test-internal-key' if key == 'INTERNAL_API_KEY' else default):
        yield

@pytest.fixture
async def client(session) -> AsyncGenerator:
    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    # Mock Redis – all methods are AsyncMock
    redis_mock = AsyncMock()
    redis_mock.ping = AsyncMock(return_value=True)
    redis_mock.publish = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock()
    redis_mock.delete = AsyncMock()
    redis_mock.client = redis_mock  # for direct attribute access

    with patch.object(redis_service, 'client', redis_mock):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()
