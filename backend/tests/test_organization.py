# backend/tests/test_organization.py
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app as fastapi_app
from app.models.types import Agent, AgentStatus, ReasoningConfig, ReportingTarget, AgentRole, OrgRole
from datetime import datetime

# Import the dependency functions to override
from app.api.v1.endpoints.organization import get_agent_manager, get_hive_manager

@pytest.fixture
def sample_agents():
    now = datetime.utcnow()
    reasoning = ReasoningConfig(model="openai/gpt-4o", temperature=0.7)
    return [
        Agent(
            id="ceo1",
            name="CEO",
            role=AgentRole.GENERIC,
            soul_md="",
            identity_md="",
            tools_md="",
            status=AgentStatus.IDLE,
            reasoning=reasoning,
            reporting_target=ReportingTarget.PARENT,
            sub_agent_ids=["strat1", "strat2"],
            memory={"short_term": [], "summary": "", "token_count": 0},
            last_active=now,
            container_id="",
            user_uid="10001",
            local_files=[],
            skills=[],
            meta={},
            org_role=OrgRole.CEO,
            department=None
        ),
        Agent(
            id="strat1",
            name="Strategy1",
            role=AgentRole.GENERIC,
            soul_md="",
            identity_md="",
            tools_md="",
            status=AgentStatus.IDLE,
            reasoning=reasoning,
            reporting_target=ReportingTarget.PARENT,
            parent_id="ceo1",
            sub_agent_ids=["dept1"],
            memory={"short_term": [], "summary": "", "token_count": 0},
            last_active=now,
            container_id="",
            user_uid="10001",
            local_files=[],
            skills=[],
            meta={},
            org_role=OrgRole.STRATEGY,
            department=None
        ),
        Agent(
            id="dept1",
            name="DeptHead",
            role=AgentRole.GENERIC,
            soul_md="",
            identity_md="",
            tools_md="",
            status=AgentStatus.IDLE,
            reasoning=reasoning,
            reporting_target=ReportingTarget.PARENT,
            parent_id="strat1",
            sub_agent_ids=[],
            memory={"short_term": [], "summary": "", "token_count": 0},
            last_active=now,
            container_id="",
            user_uid="10001",
            local_files=[],
            skills=[],
            meta={},
            org_role=OrgRole.DEPARTMENT_HEAD,
            department="Engineering"
        )
    ]

@pytest.mark.asyncio
async def test_get_org_chart(client: AsyncClient, sample_agents):
    mock_hive_manager = AsyncMock()
    mock_hive = MagicMock()
    mock_hive.agents = sample_agents
    mock_hive_manager.get_hive = AsyncMock(return_value=mock_hive)

    fastapi_app.dependency_overrides[get_hive_manager] = lambda: mock_hive_manager

    response = await client.get("/api/v1/hives/h-test/organization/chart")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0]["id"] == "ceo1"
    assert data[0]["org_role"] == "ceo"

    fastapi_app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_get_team(client: AsyncClient, sample_agents):
    mock_agent_manager = AsyncMock()
    mock_hive_manager = AsyncMock()

    # Map agents by id
    agent_map = {a.id: a for a in sample_agents}
    mock_agent_manager.get_agent = AsyncMock(side_effect=lambda id: agent_map.get(id))

    mock_hive = MagicMock()
    mock_hive.agents = sample_agents
    mock_hive_manager.get_hive = AsyncMock(return_value=mock_hive)

    fastapi_app.dependency_overrides[get_agent_manager] = lambda: mock_agent_manager
    fastapi_app.dependency_overrides[get_hive_manager] = lambda: mock_hive_manager

    # Test ceo1's team
    response = await client.get("/api/v1/hives/h-test/organization/agents/ceo1/team")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] in ["strat1", "strat2"]
    assert data[1]["id"] in ["strat1", "strat2"]

    fastapi_app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_get_managers(client: AsyncClient, sample_agents):
    mock_agent_manager = AsyncMock()
    mock_hive_manager = AsyncMock()

    agent_map = {a.id: a for a in sample_agents}
    mock_agent_manager.get_agent = AsyncMock(side_effect=lambda id: agent_map.get(id))

    mock_hive = MagicMock()
    mock_hive.agents = sample_agents
    mock_hive_manager.get_hive = AsyncMock(return_value=mock_hive)

    fastapi_app.dependency_overrides[get_agent_manager] = lambda: mock_agent_manager
    fastapi_app.dependency_overrides[get_hive_manager] = lambda: mock_hive_manager

    # Test dept1's managers
    response = await client.get("/api/v1/hives/h-test/organization/agents/dept1/managers")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] == "strat1"
    assert data[1]["id"] == "ceo1"

    fastapi_app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_agent_not_in_hive_fails(client: AsyncClient, sample_agents):
    mock_agent_manager = AsyncMock()
    mock_hive_manager = AsyncMock()

    agent_map = {a.id: a for a in sample_agents}
    mock_agent_manager.get_agent = AsyncMock(side_effect=lambda id: agent_map.get(id))

    # Create a hive that does NOT contain the agent we'll request
    mock_hive = MagicMock()
    mock_hive.agents = [sample_agents[0]]  # only ceo1
    mock_hive_manager.get_hive = AsyncMock(return_value=mock_hive)

    fastapi_app.dependency_overrides[get_agent_manager] = lambda: mock_agent_manager
    fastapi_app.dependency_overrides[get_hive_manager] = lambda: mock_hive_manager

    # Try to get team for dept1, which is not in hive
    response = await client.get("/api/v1/hives/h-test/organization/agents/dept1/team")
    assert response.status_code == 404
    assert "Agent not in this hive" in response.text

    fastapi_app.dependency_overrides.clear()
