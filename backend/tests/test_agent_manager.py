import pytest
from unittest.mock import Mock, patch, AsyncMock
from app.services.agent_manager import AgentManager
from app.services.docker_service import DockerService
from app.models.types import AgentCreate, ReasoningConfig, ReportingTarget, AgentRole
from app.services.redis_service import redis_service

@pytest.mark.asyncio
async def test_create_agent(session):
    docker = Mock(spec=DockerService)
    agent_manager = AgentManager(docker)

    # Mock vector_service to avoid real Qdrant connection during delete
    with patch('app.services.agent_manager.vector_service', new_callable=AsyncMock) as mock_vector:
        mock_vector.delete_by_agent = AsyncMock()

        agent_in = AgentCreate(
            name="Test Agent",
            role=AgentRole.GENERIC,
            soulMd="test soul",
            identityMd="test identity",
            toolsMd="test tools",
            reasoning=ReasoningConfig(model="openai/gpt-4o", temperature=0.7),
            reporting_target=ReportingTarget.PARENT
        )
        agent = await agent_manager.create_agent(agent_in)
        assert agent.id.startswith("b-")
        assert agent.name == "Test Agent"

        # Clean up – delete agent
        await agent_manager.delete_agent(agent.id)
        mock_vector.delete_by_agent.assert_awaited_once_with(agent.id)
