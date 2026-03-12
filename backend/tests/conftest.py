import os
import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from httpx import AsyncClient
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, patch

# Set HIVEBOT_DATA to a writable temp directory before importing app modules
os.environ['HIVEBOT_DATA'] = '/tmp/hivebot_test'

from app.core.database import Base, get_db
from app.main import app
from app.core.config import settings
from app.services.redis_service import redis_service

# Ensure the temp directory exists
os.makedirs('/tmp/hivebot_test', exist_ok=True)

# Use a separate test database
TEST_DATABASE_URL = "postgresql+asyncpg://hivebot:hivebot@localhost/hivebot_test"

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
        # Roll back any uncommitted changes
        await session.rollback()

@pytest.fixture
async def client(session) -> AsyncGenerator:
    # Override dependency to use test session
    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    # Mock Redis to avoid needing a real Redis instance in tests
    redis_mock = AsyncMock()
    redis_mock.ping = AsyncMock(return_value=True)
    redis_mock.publish = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock()
    redis_mock.delete = AsyncMock()
    redis_mock.client = redis_mock  # for direct attribute access

    # Patch the redis_service.client
    with patch.object(redis_service, 'client', redis_mock):
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()
