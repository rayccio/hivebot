import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException
from datetime import datetime
from app.api.v1.endpoints.plan import create_plan, GoalRequest
from app.models.task import Task, TaskStatus

@pytest.mark.asyncio
async def test_create_plan_with_scheduler_enabled():
    # Mock dependencies
    mock_task_manager = AsyncMock()
    mock_agent_manager = AsyncMock()
    mock_hive_manager = AsyncMock()
    mock_hive = MagicMock()
    mock_hive.global_user_md = "test context"
    mock_hive_manager.get_hive = AsyncMock(return_value=mock_hive)

    # Mock planner
    mock_planner = AsyncMock()
    mock_planner.plan.return_value = {
        "tasks": [
            {"id": "task1", "description": "Do something", "depends_on": []}
        ],
        "reasoning": "ok"
    }

    # Mock task graph creation
    mock_graph = MagicMock()
    mock_graph.goal_id = "g-test"
    mock_task_manager.create_task_graph.return_value = mock_graph

    # Patch redis zadd and settings.SCHEDULER_ENABLED
    with patch('app.services.redis_service.redis_service.zadd', new_callable=AsyncMock) as mock_zadd, \
         patch('app.core.config.settings.SCHEDULER_ENABLED', True):

        # Call endpoint
        request = GoalRequest(goal="Test goal")
        result = await create_plan(
            hive_id="h-test",
            goal_req=request,
            task_manager=mock_task_manager,
            agent_manager=mock_agent_manager
        )

        # Verify redis zadd called once
        mock_zadd.assert_awaited_once()
        args = mock_zadd.call_args[0]
        assert args[0] == "tasks:pending"
        # The task id is dynamic, so we just check it's a string and score is a float
        assert isinstance(list(args[1].keys())[0], str)
        assert isinstance(list(args[1].values())[0], float)

@pytest.mark.asyncio
async def test_create_plan_with_scheduler_disabled():
    # Mock dependencies
    mock_task_manager = AsyncMock()
    mock_agent_manager = AsyncMock()
    mock_hive_manager = AsyncMock()
    mock_hive = MagicMock()
    mock_hive.global_user_md = "test context"
    mock_hive_manager.get_hive = AsyncMock(return_value=mock_hive)

    mock_planner = AsyncMock()
    mock_planner.plan.return_value = {
        "tasks": [{"id": "task1", "description": "Do something", "depends_on": []}],
        "reasoning": "ok"
    }
    mock_graph = MagicMock()
    mock_graph.goal_id = "g-test"
    mock_task_manager.create_task_graph.return_value = mock_graph

    with patch('app.services.redis_service.redis_service.zadd', new_callable=AsyncMock) as mock_zadd, \
         patch('app.core.config.settings.SCHEDULER_ENABLED', False):

        request = GoalRequest(goal="Test goal")
        result = await create_plan(
            hive_id="h-test",
            goal_req=request,
            task_manager=mock_task_manager,
            agent_manager=mock_agent_manager
        )

        # Verify redis not called
        mock_zadd.assert_not_called()
