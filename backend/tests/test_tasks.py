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

    # Patch the individual redis methods on the real redis_service object
    with patch('app.services.redis_service.redis_service.zrem', new_callable=AsyncMock) as mock_zrem, \
         patch('app.services.redis_service.redis_service.srem', new_callable=AsyncMock) as mock_srem, \
         patch('app.services.redis_service.redis_service.publish', new_callable=AsyncMock) as mock_publish:

        result = await assign_task(
            hive_id="h-test",
            task_id="task1",
            agent_id="agent1",
            task_manager=mock_task_manager,
            agent_manager=mock_agent_manager
        )

        mock_zrem.assert_awaited_once_with("tasks:pending", "task1")
        mock_srem.assert_awaited_once_with("agents:idle", "agent1")
        mock_publish.assert_awaited_once()

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

    # Patch redis methods (they won't be called because exception should be raised)
    with patch('app.services.redis_service.redis_service.zrem', new_callable=AsyncMock), \
         patch('app.services.redis_service.redis_service.srem', new_callable=AsyncMock), \
         patch('app.services.redis_service.redis_service.publish', new_callable=AsyncMock):

        with pytest.raises(HTTPException) as excinfo:
            await assign_task(
                hive_id="h-test",
                task_id="task1",
                agent_id="agent1",
                task_manager=mock_task_manager,
                agent_manager=mock_agent_manager
            )
        assert excinfo.value.status_code == 400
