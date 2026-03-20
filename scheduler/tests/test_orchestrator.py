# scheduler/tests/test_orchestrator.py
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import json
from datetime import datetime
import os
import tempfile

# Set log directory to a temporary location before importing scheduler.main
os.environ['HIVEBOT_LOG_DIR'] = tempfile.mkdtemp()

# We'll test the functions from scheduler.main
import sys
sys.path.append('..')
from scheduler.main import are_dependencies_met

@pytest.mark.asyncio
async def test_are_dependencies_met_true():
    mock_pg = MagicMock()
    mock_conn = AsyncMock()
    # Create a mock context manager that acquire() returns
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    mock_pg.acquire = MagicMock(return_value=mock_cm)

    # Mock fetch to return rows with completed status for all tasks
    async def mock_fetch(query, *args):
        task_ids = args[0]  # list of task ids
        results = []
        for tid in task_ids:
            results.append({'data': json.dumps({'status': 'completed'})})
        return results
    mock_conn.fetch = AsyncMock(side_effect=mock_fetch)

    result = await are_dependencies_met(mock_pg, "task1", ["dep1", "dep2"])
    assert result is True

@pytest.mark.asyncio
async def test_are_dependencies_met_false():
    mock_pg = MagicMock()
    mock_conn = AsyncMock()
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_cm.__aexit__ = AsyncMock(return_value=None)
    mock_pg.acquire = MagicMock(return_value=mock_cm)

    async def mock_fetch(query, *args):
        task_ids = args[0]
        results = []
        for tid in task_ids:
            if tid == "dep1":
                status = 'completed'
            else:
                status = 'pending'  # dep2 is pending
            results.append({'data': json.dumps({'status': status})})
        return results
    mock_conn.fetch = AsyncMock(side_effect=mock_fetch)

    result = await are_dependencies_met(mock_pg, "task1", ["dep1", "dep2"])
    assert result is False
