import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app as fastapi_app
from app.models.types import HiveGoal, HiveGoalStatus, HiveTask, HiveTaskStatus
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
    mock_hive = MagicMock()
    mock_hive.global_user_md = "context"
    mock_hive_manager.get_hive.return_value = mock_hive

    with patch('app.api.v1.endpoints.goals.get_goal_engine', return_value=mock_goal_engine), \
         patch('app.api.v1.endpoints.goals.get_planner', return_value=mock_planner), \
         patch('app.api.v1.endpoints.goals.get_hive_manager', return_value=mock_hive_manager), \
         patch('app.api.v1.endpoints.goals.SkillManager') as mock_skill_manager:

        mock_skill_manager.return_value.list_skills = AsyncMock(return_value=[])

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

    with patch('app.api.v1.endpoints.goals.get_goal_engine', return_value=mock_goal_engine):
        response = await client.get("/api/v1/hives/h-test/goals")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "g1"
