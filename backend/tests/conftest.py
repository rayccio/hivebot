import pytest
import asyncio
import os
import tempfile
from unittest.mock import patch, MagicMock
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient
from typing import AsyncGenerator, Generator

# Set HIVEBOT_DATA to a temporary directory before importing app modules
temp_data_dir = tempfile.mkdtemp()
os.environ["HIVEBOT_DATA"] = temp_data_dir
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_USER"] = "hivebot"
os.environ["POSTGRES_PASSWORD"] = "hivebot"
os.environ["POSTGRES_DB"] = "hivebot_test"
os.environ["REDIS_HOST"] = "localhost"
os.environ["REDIS_PORT"] = "6379"
os.environ["INTERNAL_API_KEY"] = "test-key"

# Now import app modules after setting env vars
from app.core.database import Base, get_db
from app.main import app
from app.core.config import settings
from app.core.secrets import SecretsManager

# Mock the secrets manager to avoid file access
mock_secrets = MagicMock(spec=SecretsManager)
mock_secrets.get.return_value = None
mock_secrets.set.return_value = None

# Patch the settings._secrets attribute
@pytest.fixture(autouse=True)
def patch_secrets():
    with patch.object(settings, '_secrets', mock_secrets):
        yield

# Use the test database URL (already set via env vars)
TEST_DATABASE_URL = f"postgresql+asyncpg://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}@{os.environ['POSTGRES_HOST']}/{os.environ['POSTGRES_DB']}"

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

@pytest.fixture
async def client(session) -> AsyncGenerator:
    # Override dependency to use test session
    async def override_get_db():
        yield session
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

@pytest.fixture
async def redis_client():
    import redis.asyncio as redis
    client = await redis.from_url("redis://localhost:6379/1", decode_responses=True)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.close()
