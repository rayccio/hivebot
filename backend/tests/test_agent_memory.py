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

    # Patch vector_service and SentenceTransformer with create=True
    with patch('app.services.agent_manager.vector_service', new_callable=AsyncMock, create=True) as mock_vector, \
         patch('sentence_transformers.SentenceTransformer', new_callable=MagicMock, create=True) as mock_transformer:

        mock_model = MagicMock()
        # Return a numpy array that has .tolist() method
        mock_model.encode.return_value = np.array([0.1] * 384)
        mock_transformer.return_value = mock_model

        mock_vector.search_memory = AsyncMock(return_value=[
            {"text": "memory1"},
            {"text": "memory2"}
        ])

        memories = await manager.get_long_term_memory(agent_id, query, limit=2)

        assert memories == ["memory1", "memory2"]
        mock_vector.search_memory.assert_awaited_once_with(agent_id, [0.1]*384, 2)
