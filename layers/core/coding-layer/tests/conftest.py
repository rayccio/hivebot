import os
import sys
import pytest
import asyncio
from unittest.mock import AsyncMock, patch

# Ensure the layer modules can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@pytest.fixture(autouse=True)
def mock_env():
    """Mock environment variables for testing."""
    with patch.dict(os.environ, {
        "INTERNAL_API_KEY": "test-key",
        "ORCHESTRATOR_URL": "http://localhost:8000",
    }):
        yield

@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient for AI calls."""
    with patch('httpx.AsyncClient') as MockClient:
        client = AsyncMock()
        MockClient.return_value.__aenter__.return_value = client
        yield client
