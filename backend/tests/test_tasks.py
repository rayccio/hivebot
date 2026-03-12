import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException
from app.api.v1.endpoints.tasks import assign_task
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
    mock_task_manager.assign_task = AsyncMock(return_value=True)   # ensure it's an AsyncMock

    # Patch the redis methods directly to avoid any attribute confusion
    with patch('app.api.v1.endpoints.tasks.redis_service.zrem', new_callable=AsyncMock) as mock_zrem, \
         patch('app.api.v1.endpoints.tasks.redis_service.srem', new_callable=AsyncMock) as mock_srem, \
         patch('app.api.v1.endpoints.tasks.redis_service.publish', new_callable=AsyncMock) as mock_publish:

        result = await assign_task(
            hive_id="h-test",
            task_id="task1",
            agent_id="agent1",
            task_manager=mock_task_manager,
            agent_manager=mock_agent_manager
        )

        # Verify that assign_task was called
        mock_task_manager.assign_task.assert_awaited_once_with("task1", "agent1")

        # Now check the redis calls
        mock_zrem.assert_awaited_once_with("tasks:pending", "task1")
        mock_srem.assert_awaited_once_with("agents:idle", "agent1")
        mock_publish.assert_awaited_once()
        assert result == {"status": "assigned"}

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

    # Ensure the task returned has the correct status (sanity check)
    assert task.status == TaskStatus.ASSIGNED

    with patch('app.api.v1.endpoints.tasks.redis_service') as mock_redis:  # patch unused here
        with pytest.raises(HTTPException) as excinfo:
            await assign_task(
                hive_id="h-test",
                task_id="task1",
                agent_id="agent1",
                task_manager=mock_task_manager,
                agent_manager=mock_agent_manager
            )
        assert excinfo.value.status_code == 400
        assert "Task is assigned, cannot assign" in str(excinfo.value.detail)

    # Ensure assign_task was never called because we raised before
    mock_task_manager.assign_task.assert_not_called()
