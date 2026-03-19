import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.execution_logger import ExecutionLogger
from app.models.types import ExecutionLogLevel
from datetime import datetime
import json

@pytest.mark.asyncio
async def test_log_execution():
    logger = ExecutionLogger()
    goal_id = "g-test"
    task_id = "t-test"
    agent_id = "b-test"
    level = ExecutionLogLevel.INFO
    message = "Test log message"
    iteration = 3

    with patch('app.services.execution_logger.AsyncSessionLocal') as mock_session:
        mock_conn = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_conn
        mock_conn.execute = AsyncMock()
        mock_conn.commit = AsyncMock()

        log = await logger.log(goal_id, level, message, task_id, agent_id, iteration)
        assert log.id.startswith("log-")
        assert log.goal_id == goal_id
        assert log.task_id == task_id
        assert log.agent_id == agent_id
        assert log.level == level
        assert log.message == message
        assert log.iteration == iteration
        mock_conn.execute.assert_awaited_once()
        mock_conn.commit.assert_awaited_once()

@pytest.mark.asyncio
async def test_get_logs_for_goal():
    logger = ExecutionLogger()
    goal_id = "g-test"
    mock_rows = [
        ("log-1", goal_id, None, None, "info", "msg1", None, datetime.utcnow()),
        ("log-2", goal_id, "t-1", "b-1", "warning", "msg2", 1, datetime.utcnow()),
    ]

    with patch('app.services.execution_logger.AsyncSessionLocal') as mock_session:
        mock_conn = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_conn
        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows
        mock_conn.execute.return_value = mock_result

        logs = await logger.get_logs_for_goal(goal_id, limit=10)
        assert len(logs) == 2
        assert logs[0].id == "log-1"
        assert logs[1].id == "log-2"
        assert logs[1].task_id == "t-1"
        assert logs[1].level == ExecutionLogLevel.WARNING
