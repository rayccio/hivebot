import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException
from app.api.v1.endpoints.tasks import assign_task, CompleteTaskRequest
from app.models.task import Task, TaskStatus
from datetime import datetime

@pytest.mark.asyncio
async def test_assign_task_removes_from_redis():
    mock_task_manager = AsyncMock()
    mock_agent_manager = AsyncMock()

    task = Task(
        id="task1",
        hive_id="h-test",
        goal_id="g-test",
        description="test",
        status=TaskStatus.PENDING,
        created_at=datetime.utcnow()
    )
    agent = MagicMock()
    agent.id = "agent1"

    mock_task_manager.get_task.return_value = task
    mock_agent_manager.get_agent.return_value = agent
    mock_task_manager.assign_task.return_value = True

    # Replace the entire redis_service in the tasks module with a mock
    mock_redis = AsyncMock()
    mock_redis.zrem = AsyncMock()
    mock_redis.srem = AsyncMock()
    mock_redis.publish = AsyncMock()

    with patch('app.api.v1.endpoints.tasks.redis_service', mock_redis):
        result = await assign_task(
            hive_id="h-test",
            task_id="task1",
            agent_id="agent1",
            task_manager=mock_task_manager,
            agent_manager=mock_agent_manager
        )

        mock_redis.zrem.assert_awaited_once_with("tasks:pending", "task1")
        mock_redis.srem.assert_awaited_once_with("agents:idle", "agent1")
        mock_redis.publish.assert_awaited_once()

@pytest.mark.asyncio
async def test_assign_task_non_pending_fails():
    mock_task_manager = AsyncMock()
    mock_agent_manager = AsyncMock()

    task = Task(
        id="task1",
        hive_id="h-test",
        goal_id="g-test",
        description="test",
        status=TaskStatus.ASSIGNED,  # not pending
        created_at=datetime.utcnow()
    )
    agent = MagicMock()
    agent.id = "agent1"

    mock_task_manager.get_task.return_value = task
    mock_agent_manager.get_agent.return_value = agent

    # Replace redis_service with a mock (it won't be called anyway)
    mock_redis = AsyncMock()
    with patch('app.api.v1.endpoints.tasks.redis_service', mock_redis):
        with pytest.raises(HTTPException) as excinfo:
            await assign_task(
                hive_id="h-test",
                task_id="task1",
                agent_id="agent1",
                task_manager=mock_task_manager,
                agent_manager=mock_agent_manager
            )
        assert excinfo.value.status_code == 400
