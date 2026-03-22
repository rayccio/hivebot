# backend/tests/test_agent_roles.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.agent_manager import AgentManager
from app.services.docker_service import DockerService
from app.models.types import ReasoningConfig, ReportingTarget, AgentCreate
from app.constants import (
    BUILDER_SOUL, BUILDER_IDENTITY, BUILDER_TOOLS,
    TESTER_SOUL, TESTER_IDENTITY, TESTER_TOOLS,
    INITIAL_SOUL, INITIAL_IDENTITY, INITIAL_TOOLS
)
from app.services.skill_manager import SkillManager  # not used directly but needed for imports

@pytest.mark.asyncio
async def test_get_prompts_for_role():
    docker = MagicMock(spec=DockerService)
    manager = AgentManager(docker)
    soul, identity, tools = manager._get_prompts_for_role("builder")
    assert soul == BUILDER_SOUL
    assert identity == BUILDER_IDENTITY
    assert tools == BUILDER_TOOLS

    soul, identity, tools = manager._get_prompts_for_role("tester")
    assert soul == TESTER_SOUL
    assert identity == TESTER_IDENTITY
    assert tools == TESTER_TOOLS

    # Fallback
    soul, identity, tools = manager._get_prompts_for_role("generic")
    assert soul == INITIAL_SOUL
    assert identity == INITIAL_IDENTITY
    assert tools == INITIAL_TOOLS

@pytest.mark.asyncio
async def test_create_role_agent(session):
    docker = MagicMock(spec=DockerService)
    manager = AgentManager(docker)
    reasoning = ReasoningConfig(model="openai/gpt-4o", temperature=0.7)

    with patch('app.services.agent_manager.AsyncSessionLocal') as mock_session, \
         patch('app.services.agent_manager.redis_service.sadd', new_callable=AsyncMock) as mock_sadd, \
         patch('builtins.open', new_callable=MagicMock) as mock_open, \
         patch('app.services.agent_manager.AgentRepository') as mock_repo:

        mock_conn = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_conn

        # Mock the database result for _get_role_prompts_from_db
        mock_result = AsyncMock()
        mock_result.fetchone = AsyncMock(return_value=None)  # return None so fallback to constants
        mock_conn.execute.return_value = mock_result

        # Mock the repository create method
        mock_repo_instance = AsyncMock()
        mock_repo.return_value = mock_repo_instance
        mock_repo_instance.create = AsyncMock(return_value=None)

        # Mock the _get_repo method to return our mock repo
        manager._get_repo = AsyncMock(return_value=(mock_repo_instance, mock_conn))

        agent = await manager.create_role_agent(
            name="Builder Bot",
            role="builder",
            reasoning=reasoning
        )

        assert agent.name == "Builder Bot"
        assert agent.role == "builder"
        assert agent.soul_md == BUILDER_SOUL
        assert agent.identity_md == BUILDER_IDENTITY
        assert agent.tools_md == BUILDER_TOOLS
        mock_sadd.assert_awaited_once_with("agents:idle", agent.id)

@pytest.mark.asyncio
async def test_spawn_agent_for_task():
    docker = MagicMock(spec=DockerService)
    manager = AgentManager(docker)
    with patch.object(manager, 'create_role_agent', new_callable=AsyncMock) as mock_create, \
         patch('app.services.agent_manager.SkillManager') as MockSkillManager, \
         patch('app.services.agent_manager.HiveManager') as MockHiveManager:

        mock_agent = MagicMock()
        mock_agent.id = "b-test"
        mock_create.return_value = mock_agent

        mock_skill_manager = AsyncMock()
        mock_skill_manager.get_skill.return_value = MagicMock(id="skill1")
        mock_skill_manager.list_versions.return_value = []
        MockSkillManager.return_value = mock_skill_manager

        mock_hive_manager = AsyncMock()
        MockHiveManager.return_value = mock_hive_manager

        agent = await manager.spawn_agent_for_task(
            hive_id="h-test",
            required_skill_ids=["skill1"],
            agent_type="builder"
        )

        assert agent == mock_agent
        mock_create.assert_awaited_once()
        args, kwargs = mock_create.call_args
        assert kwargs['role'] == "builder"
        mock_hive_manager.add_agent.assert_awaited_once_with("h-test", mock_agent)
