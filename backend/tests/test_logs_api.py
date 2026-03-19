import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app as fastapi_app
from app.models.types import HiveGoal, HiveGoalStatus, Hive, ExecutionLog, ExecutionLogLevel
from datetime import datetime
import json

@pytest.mark.asyncio
async def test_get_execution_logs(client: AsyncClient):
    # Mock dependencies
    mock_logger = AsyncMock()
    mock_log = ExecutionLog(
        id="log-123",
        goal_id="g-test",
        task_id="t-test",
        agent_id="b-test",
        level=ExecutionLogLevel.INFO,
        message="Test log",
        iteration=1,
        created_at=datetime.utcnow()
    )
    mock_logger.get_logs_for_goal.return_value = [mock_log]

    mock_goal_engine = AsyncMock()
    mock_goal = HiveGoal(
        id="g-test",
        hive_id="h-test",
        description="test",
        constraints={},
        success_criteria=[],
        status=HiveGoalStatus.EXECUTING,
        created_at=datetime.utcnow()
    )
    mock_goal_engine.get_goal.return_value = mock_goal

    mock_hive_manager = AsyncMock()
    mock_hive = MagicMock(spec=Hive)
    mock_hive.id = "h-test"
    mock_hive_manager.get_hive.return_value = mock_hive

    from app.api.v1.endpoints.logs import get_execution_logger, get_goal_engine, get_hive_manager
    fastapi_app.dependency_overrides[get_execution_logger] = lambda: mock_logger
    fastapi_app.dependency_overrides[get_goal_engine] = lambda: mock_goal_engine
    fastapi_app.dependency_overrides[get_hive_manager] = lambda: mock_hive_manager

    response = await client.get("/api/v1/hives/h-test/goals/g-test/logs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "log-123"
    assert data[0]["level"] == "info"

    fastapi_app.dependency_overrides.clear()
