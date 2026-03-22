# backend/tests/test_agent_role_dynamic.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.agent_manager import AgentManager
from app.services.docker_service import DockerService
from app.models.types import ReasoningConfig, ReportingTarget, AgentCreate
from app.constants import BUILDER_SOUL, BUILDER_IDENTITY, BUILDER_TOOLS

@pytest.mark.asyncio
async def test_get_role_prompts_from_db():
    docker = MagicMock(spec=DockerService)
    manager = AgentManager(docker)

    # Mock database query
    with patch('app.services.agent_manager.AsyncSessionLocal') as mock_session:
        mock_conn = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_conn
        mock_result = AsyncMock()
        mock_result.fetchone = AsyncMock(return_value=("soul", "identity", "tools"))
        mock_conn.execute.return_value = mock_result

        soul, identity, tools = await manager._get_role_prompts_from_db("builder")
        assert soul == "soul"
        assert identity == "identity"
        assert tools == "tools"

        # Fallback when not found
        mock_result.fetchone = AsyncMock(return_value=None)
        soul, identity, tools = await manager._get_role_prompts_from_db("nonexistent")
        assert soul is None
        assert identity is None
        assert tools is None

@pytest.mark.asyncio
async def test_get_prompts_for_role_async_fallback():
    docker = MagicMock(spec=DockerService)
    manager = AgentManager(docker)

    with patch.object(manager, '_get_role_prompts_from_db', new_callable=AsyncMock) as mock_db:
        mock_db.return_value = (None, None, None)
        soul, identity, tools = await manager._get_prompts_for_role_async("builder")
        # Should fall back to constants – check they match expected
        assert soul == BUILDER_SOUL
        assert identity == BUILDER_IDENTITY
        assert tools == BUILDER_TOOLS

@pytest.mark.asyncio
async def test_create_role_agent_uses_db():
    docker = MagicMock(spec=DockerService)
    manager = AgentManager(docker)
    reasoning = ReasoningConfig(model="openai/gpt-4o", temperature=0.7)

    with patch.object(manager, '_get_prompts_for_role_async', new_callable=AsyncMock) as mock_prompts:
        mock_prompts.return_value = ("soul", "identity", "tools")
        with patch.object(manager, 'create_agent', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = MagicMock()
            await manager.create_role_agent(
                name="Test", role="builder", reasoning=reasoning
            )
            mock_prompts.assert_awaited_once_with("builder")
            mock_create.assert_awaited_once()
            args, _ = mock_create.call_args
            agent_in = args[0]
            assert agent_in.soul_md == "soul"
            assert agent_in.identity_md == "identity"
            assert agent_in.tools_md == "tools"
