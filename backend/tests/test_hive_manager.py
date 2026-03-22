# backend/tests/test_hive_manager.py
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.services.hive_manager import HiveManager
from app.services.agent_manager import AgentManager
from app.services.docker_service import DockerService
from app.models.types import HiveCreate, AgentCreate, ReasoningConfig, ReportingTarget
from app.core.config import settings
import tempfile

@pytest.mark.asyncio
async def test_create_hive_persists_agent_ids(session):
    # Create a temporary directory for agent data to avoid cluttering real data
    with tempfile.TemporaryDirectory() as tmpdir:
        # Patch settings.AGENTS_DIR to point to a temporary directory
        with patch.object(settings, 'AGENTS_DIR', tmpdir):
            # Mock DockerService to prevent container creation
            docker = MagicMock(spec=DockerService)
            agent_manager = AgentManager(docker)
            hive_manager = HiveManager(agent_manager)

            hive_in = HiveCreate(name="Test Hive")
            hive = await hive_manager.create_hive(hive_in)

            # Verify that the hive's agent_ids is an empty list
            assert hive.agent_ids == []

            # Verify that the stored data in DB has the agentIds field (camelCase)
            from sqlalchemy import text
            result = await session.execute(
                text("SELECT data FROM hives WHERE id = :id"),
                {"id": hive.id}
            )
            row = result.fetchone()
            assert row is not None
            data = row[0]
            assert "agentIds" in data
            assert data["agentIds"] == []


@pytest.mark.asyncio
async def test_add_agent_updates_agent_ids(session):
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch.object(settings, 'AGENTS_DIR', tmpdir):
            # Mock DockerService to avoid container creation
            docker = MagicMock(spec=DockerService)
            agent_manager = AgentManager(docker)
            hive_manager = HiveManager(agent_manager)

            # Create a hive
            hive_in = HiveCreate(name="Test Hive")
            hive = await hive_manager.create_hive(hive_in)

            # Create an agent
            reasoning = ReasoningConfig(model="openai/gpt-4o", temperature=0.7)
            agent_in = AgentCreate(
                name="Test Agent",
                role="generic",
                soulMd="soul",
                identityMd="identity",
                toolsMd="tools",
                reasoning=reasoning,
                reporting_target=ReportingTarget.PARENT
            )

            # Patch redis_service to avoid Redis calls
            with patch('app.services.agent_manager.redis_service.sadd', new_callable=AsyncMock) as mock_sadd, \
                 patch('app.services.agent_manager.redis_service.publish', new_callable=AsyncMock) as mock_publish:

                agent = await agent_manager.create_agent(agent_in)
                assert agent.id is not None

            # Add agent to hive
            updated_hive = await hive_manager.add_agent(hive.id, agent)

            # Verify that the hive's agent_ids contains the agent's id
            assert agent.id in updated_hive.agent_ids

            # Verify from DB
            from sqlalchemy import text
            result = await session.execute(
                text("SELECT data FROM hives WHERE id = :id"),
                {"id": hive.id}
            )
            row = result.fetchone()
            data = row[0]
            assert agent.id in data["agentIds"]
