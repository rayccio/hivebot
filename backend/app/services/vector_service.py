# backend/tests/test_agent_memory.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import numpy as np
from app.services.agent_manager import AgentManager
from app.services.docker_service import DockerService
from app.models.types import Agent, AgentStatus, ReasoningConfig, ReportingTarget, AgentRole
from datetime import datetime

@pytest.mark.asyncio
async def test_get_long_term_memory():
    docker = MagicMock(spec=DockerService)
    manager = AgentManager(docker)
    agent_id = "b-test"
    query = "test query"

    with patch('app.services.agent_manager.vector_service', new_callable=AsyncMock, create=True) as mock_vector, \
         patch('sentence_transformers.SentenceTransformer', new_callable=MagicMock, create=True) as mock_transformer:

        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.1] * 384)
        mock_transformer.return_value = mock_model

        mock_vector.search_memory = AsyncMock(return_value=[
            {"text": "memory1"},
            {"text": "memory2"}
        ])

        memories = await manager.get_long_term_memory(agent_id, query, limit=2)

        assert memories == ["memory1", "memory2"]
        mock_vector.search_memory.assert_awaited_once_with(agent_id, [0.1]*384, 2)

@pytest.mark.asyncio
async def test_store_long_term_memory():
    docker = MagicMock(spec=DockerService)
    manager = AgentManager(docker)
    agent_id = "b-test"
    text = "This is a test memory summary"
    timestamp = datetime.utcnow()

    with patch('app.services.agent_manager.vector_service', new_callable=AsyncMock, create=True) as mock_vector, \
         patch('sentence_transformers.SentenceTransformer', new_callable=MagicMock, create=True) as mock_transformer:

        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.1] * 384)
        mock_transformer.return_value = mock_model

        mock_vector.store_memory = AsyncMock(return_value=True)

        result = await manager.store_long_term_memory(agent_id, text, timestamp)

        assert result is True
        mock_vector.store_memory.assert_awaited_once_with(
            agent_id=agent_id,
            text=text,
            vector=[0.1]*384,
            timestamp=timestamp.isoformat(),
            source="memory"
        )
