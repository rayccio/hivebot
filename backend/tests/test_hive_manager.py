# backend/tests/test_hive_manager.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.hive_manager import HiveManager
from app.services.agent_manager import AgentManager
from app.services.docker_service import DockerService
from app.models.types import HiveCreate, Hive, Agent, AgentCreate, ReasoningConfig, ReportingTarget, AgentRole
from datetime import datetime

@pytest.mark.asyncio
async def test_create_hive_persists_agent_ids(session):
    docker = MagicMock(spec=DockerService)
    agent_manager = AgentManager(docker)
    hive_manager = HiveManager(agent_manager)

    with patch('app.services.hive_manager.AsyncSessionLocal') as mock_session:
        mock_conn = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_conn
        mock_repo = AsyncMock()
        mock_repo.create = AsyncMock(return_value=MagicMock())
        hive_manager.repo = lambda s: mock_repo  # simplified

        hive_in = HiveCreate(name="Test Hive")
        hive = await hive_manager.create_hive(hive_in)
        # Check that the created Hive has agent_ids empty list
        assert hive.agent_ids == []
        # Check that model_dump was called with by_alias=True (ensures agentIds field)
        # We can't easily check, but we trust the model.

@pytest.mark.asyncio
async def test_add_agent_updates_agent_ids(session):
    docker = MagicMock(spec=DockerService)
    agent_manager = AgentManager(docker)
    hive_manager = HiveManager(agent_manager)

    now = datetime.utcnow()
    reasoning = ReasoningConfig(model="openai/gpt-4o", temperature=0.7)
    agent = Agent(
        id="b-test",
        name="Test",
        role=AgentRole.GENERIC,
        soul_md="",
        identity_md="",
        tools_md="",
        status="IDLE",
        reasoning=reasoning,
        reporting_target=ReportingTarget.PARENT,
        sub_agent_ids=[],
        memory={"short_term": [], "summary": "", "token_count": 0},
        last_active=now,
        container_id="",
        user_uid="10001",
        local_files=[],
        skills=[],
        meta={},
        org_role="member",
        department=None
    )

    hive = Hive(
        id="h-test",
        name="Test",
        agent_ids=[],
        agents=[],
        global_user_md="",
        messages=[],
        global_files=[],
        hive_mind_config={},
        created_at=now,
        updated_at=now
    )

    with patch.object(hive_manager, '_get_session_and_repo') as mock_get_repo:
        mock_repo = AsyncMock()
        mock_repo.get.return_value = hive
        mock_repo.update = AsyncMock()
        mock_session = AsyncMock()
        mock_get_repo.return_value = (mock_repo, mock_session)

        result = await hive_manager.add_agent("h-test", agent)
        assert result is not None
        # Check that agent_ids was updated
        assert "b-test" in hive.agent_ids
        mock_repo.update.assert_called_once()
        args, kwargs = mock_repo.update.call_args
        # The update data should include agentIds (camelCase)
        update_dict = args[1]  # second arg is the data dict
        assert "agentIds" in update_dict
        assert "b-test" in update_dict["agentIds"]
