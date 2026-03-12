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

    # Patch HiveManager inside the endpoint
    with patch('app.api.v1.endpoints.plan.HiveManager', return_value=mock_hive_manager):
        # Mock planner
        mock_planner = AsyncMock()
        mock_planner.plan.return_value = {
            "tasks": [
                {"id": "task1", "description": "Do something", "depends_on": []}
            ],
            "reasoning": "ok"
        }
        with patch('app.api.v1.endpoints.plan.Planner', return_value=mock_planner):
            # Mock task graph creation
            mock_graph = MagicMock()
            mock_graph.goal_id = "g-test"
            mock_task_manager.create_task_graph.return_value = mock_graph

            # Patch redis zadd and the settings object inside the plan module
            mock_settings = MagicMock()
            mock_settings.SCHEDULER_ENABLED = True
            with patch('app.services.redis_service.redis_service.zadd', new_callable=AsyncMock) as mock_zadd, \
                 patch('app.api.v1.endpoints.plan.settings', mock_settings):

                request = GoalRequest(goal="Test goal")
                result = await create_plan(
                    hive_id="h-test",
                    goal_req=request,
                    task_manager=mock_task_manager,
                    agent_manager=mock_agent_manager
                )

                mock_zadd.assert_awaited_once()
                args = mock_zadd.call_args[0]
                assert args[0] == "tasks:pending"
                assert isinstance(list(args[1].keys())[0], str)
                assert isinstance(list(args[1].values())[0], float)

@pytest.mark.asyncio
async def test_create_plan_with_scheduler_disabled():
    mock_task_manager = AsyncMock()
    mock_agent_manager = AsyncMock()
    mock_hive_manager = AsyncMock()
    mock_hive = MagicMock()
    mock_hive.global_user_md = "test context"
    mock_hive_manager.get_hive = AsyncMock(return_value=mock_hive)

    with patch('app.api.v1.endpoints.plan.HiveManager', return_value=mock_hive_manager):
        mock_planner = AsyncMock()
        mock_planner.plan.return_value = {
            "tasks": [{"id": "task1", "description": "Do something", "depends_on": []}],
            "reasoning": "ok"
        }
        with patch('app.api.v1.endpoints.plan.Planner', return_value=mock_planner):
            mock_graph = MagicMock()
            mock_graph.goal_id = "g-test"
            mock_task_manager.create_task_graph.return_value = mock_graph

            mock_settings = MagicMock()
            mock_settings.SCHEDULER_ENABLED = False
            with patch('app.services.redis_service.redis_service.zadd', new_callable=AsyncMock) as mock_zadd, \
                 patch('app.api.v1.endpoints.plan.settings', mock_settings):

                request = GoalRequest(goal="Test goal")
                result = await create_plan(
                    hive_id="h-test",
                    goal_req=request,
                    task_manager=mock_task_manager,
                    agent_manager=mock_agent_manager
                )

                mock_zadd.assert_not_called()
