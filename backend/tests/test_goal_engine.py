import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.goal_engine import GoalEngine
from app.models.types import HiveGoalStatus
from datetime import datetime
import json

@pytest.mark.asyncio
async def test_create_goal():
    engine = GoalEngine()
    with patch('app.services.goal_engine.AsyncSessionLocal') as mock_session:
        mock_conn = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_conn
        mock_conn.execute = AsyncMock()
        mock_conn.commit = AsyncMock()

        goal = await engine.create_goal(
            hive_id="h-test",
            description="Test goal",
            constraints={"budget": 100},
            success_criteria=["done"]
        )

        assert goal.id.startswith("g-")
        assert goal.hive_id == "h-test"
        assert goal.description == "Test goal"
        assert goal.status == HiveGoalStatus.CREATED
        assert goal.constraints == {"budget": 100}
        mock_conn.execute.assert_awaited_once()
        mock_conn.commit.assert_awaited_once()

@pytest.mark.asyncio
async def test_get_goal():
    engine = GoalEngine()
    mock_goal_data = {
        "id": "g-123",
        "hive_id": "h-test",
        "description": "Test",
        "constraints": {},
        "success_criteria": [],
        "status": "created",
        "created_at": datetime.utcnow().isoformat()
    }
    with patch('app.services.goal_engine.AsyncSessionLocal') as mock_session:
        mock_conn = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_conn

        # Use MagicMock for fetchone (not AsyncMock)
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (mock_goal_data,)
        mock_conn.execute.return_value = mock_result

        goal = await engine.get_goal("g-123")
        assert goal is not None
        assert goal.id == "g-123"

@pytest.mark.asyncio
async def test_update_goal_status():
    engine = GoalEngine()
    with patch('app.services.goal_engine.GoalEngine.get_goal') as mock_get, \
         patch('app.services.goal_engine.AsyncSessionLocal') as mock_session:
        mock_goal = MagicMock()
        mock_goal.model_dump_json.return_value = "{}"
        mock_get.return_value = mock_goal
        mock_conn = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_conn
        mock_conn.execute = AsyncMock()
        mock_conn.commit = AsyncMock()

        updated = await engine.update_goal_status("g-123", HiveGoalStatus.COMPLETED)
        assert updated is not None
        mock_goal.status = HiveGoalStatus.COMPLETED
        mock_goal.completed_at = datetime.utcnow()
        mock_conn.execute.assert_awaited_once()
        mock_conn.commit.assert_awaited_once()
