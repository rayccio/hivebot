import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app as fastapi_app
from app.models.types import HiveGoal, HiveGoalStatus, HiveTask, HiveTaskStatus, Hive
from datetime import datetime
import json

@pytest.mark.asyncio
async def test_create_goal_api(client: AsyncClient):
    # Mock dependencies
    mock_goal_engine = AsyncMock()
    mock_goal = HiveGoal(
        id="g-test",
        hive_id="h-test",
        description="Test goal",
        constraints={},
        success_criteria=[],
        status=HiveGoalStatus.CREATED,
        created_at=datetime.utcnow()
    )
    mock_goal_engine.create_goal.return_value = mock_goal

    mock_planner = AsyncMock()
    mock_task = HiveTask(
        id="t-test",
        goal_id="g-test",
        description="Task",
        agent_type="builder",
        status=HiveTaskStatus.PENDING,
        created_at=datetime.utcnow()
    )
    mock_planner.plan.return_value = [mock_task]

    mock_hive_manager = AsyncMock()
    mock_hive = MagicMock(spec=Hive)
    mock_hive.global_user_md = "context"
    mock_hive_manager.get_hive.return_value = mock_hive

    # Apply dependency overrides for the functions that exist
    from app.api.v1.endpoints.goals import get_goal_engine, get_planner, get_hive_manager
    fastapi_app.dependency_overrides[get_goal_engine] = lambda: mock_goal_engine
    fastapi_app.dependency_overrides[get_planner] = lambda: mock_planner
    fastapi_app.dependency_overrides[get_hive_manager] = lambda: mock_hive_manager

    # Patch SkillManager at its original location (class in service module)
    with patch('app.services.skill_manager.SkillManager') as MockSkillManager:
        mock_skill_manager = AsyncMock()
        mock_skill_manager.list_skills = AsyncMock(return_value=[])
        MockSkillManager.return_value = mock_skill_manager

        payload = {
            "description": "Test goal",
            "constraints": {},
            "success_criteria": []
        }
        response = await client.post("/api/v1/hives/h-test/goals", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["goal"]["id"] == "g-test"
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["id"] == "t-test"

    fastapi_app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_list_goals(client: AsyncClient):
    mock_goal_engine = AsyncMock()
    mock_goals = [
        HiveGoal(
            id="g1",
            hive_id="h-test",
            description="Goal 1",
            constraints={},
            success_criteria=[],
            status=HiveGoalStatus.CREATED,
            created_at=datetime.utcnow()
        )
    ]
    mock_goal_engine.list_goals_for_hive.return_value = mock_goals

    from app.api.v1.endpoints.goals import get_goal_engine
    fastapi_app.dependency_overrides[get_goal_engine] = lambda: mock_goal_engine

    response = await client.get("/api/v1/hives/h-test/goals")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "g1"

    fastapi_app.dependency_overrides.clear()
