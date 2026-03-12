import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
import json

# Import from the scheduler package (absolute import)
from scheduler.main import (
    populate_pending_tasks,
    populate_idle_agents,
    maintenance_loop,
    assignment_loop,
)

@pytest.mark.asyncio
async def test_populate_pending_tasks():
    mock_pg = AsyncMock()
    mock_redis = AsyncMock()

    mock_pg.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(return_value=[
        {'id': 'task1', 'created_at': datetime(2025, 1, 1, 12, 0, 0)},
        {'id': 'task2', 'created_at': datetime(2025, 1, 1, 12, 5, 0)},
    ])

    await populate_pending_tasks(mock_pg, mock_redis)

    assert mock_redis.zadd.call_count == 2
    mock_redis.zadd.assert_any_call("tasks:pending", {"task1": 1735732800000.0})
    mock_redis.zadd.assert_any_call("tasks:pending", {"task2": 1735733100000.0})

@pytest.mark.asyncio
async def test_populate_idle_agents():
    mock_pg = AsyncMock()
    mock_redis = AsyncMock()

    mock_pg.acquire.return_value.__aenter__.return_value.fetch = AsyncMock(return_value=[
        {'id': 'agent1'},
        {'id': 'agent2'},
    ])

    await populate_idle_agents(mock_pg, mock_redis)

    assert mock_redis.sadd.call_count == 2
    mock_redis.sadd.assert_any_call("agents:idle", "agent1")
    mock_redis.sadd.assert_any_call("agents:idle", "agent2")

@pytest.mark.asyncio
async def test_maintenance_loop_removes_non_pending():
    mock_pg = AsyncMock()
    mock_redis = AsyncMock()

    mock_redis.zrange = AsyncMock(return_value=["task1", "task2"])

    async def mock_fetchval(query, task_id):
        if task_id == "task1":
            return "assigned"
        elif task_id == "task2":
            return "pending"
        return None
    mock_pg.acquire.return_value.__aenter__.return_value.fetchval = mock_fetchval

    task = asyncio.create_task(maintenance_loop(mock_pg, mock_redis))
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    mock_redis.zrem.assert_awaited_once_with("tasks:pending", "task1")

@pytest.mark.asyncio
async def test_assignment_loop_matches_and_assigns():
    mock_pg = AsyncMock()
    mock_redis = AsyncMock()

    mock_redis.zrange = AsyncMock(return_value=[("task1", 123456.0)])

    task_data = {
        'status': 'pending',
        'description': 'Test task',
        'input_data': {},
        'goal_id': 'goal1',
        'hive_id': 'hive1'
    }
    async def mock_fetchrow(query, task_id):
        if task_id == "task1":
            return {
                'data': json.dumps(task_data),
                'required_skills': ['skill1']
            }
        return None
    mock_pg.acquire.return_value.__aenter__.return_value.fetchrow = mock_fetchrow

    mock_redis.smembers = AsyncMock(return_value={"agent1", "agent2"})

    agent1_data = {'skills': [{'skillId': 'skill1'}]}
    agent2_data = {'skills': [{'skillId': 'skill2'}]}
    async def mock_fetch(query, agent_ids):
        return [
            {'id': 'agent1', 'data': json.dumps(agent1_data)},
            {'id': 'agent2', 'data': json.dumps(agent2_data)},
        ]
    mock_pg.acquire.return_value.__aenter__.return_value.fetch = mock_fetch

    mock_pg.acquire.return_value.__aenter__.return_value.execute = AsyncMock()
    mock_redis.publish = AsyncMock()

    task = asyncio.create_task(assignment_loop(mock_pg, mock_redis))
    await asyncio.sleep(0.1)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    mock_redis.zrem.assert_awaited_once_with("tasks:pending", "task1")
    mock_redis.srem.assert_awaited_once_with("agents:idle", "agent1")
    mock_redis.publish.assert_awaited_once()
    assert mock_redis.publish.call_args[0][0] == "agent:agent1"
