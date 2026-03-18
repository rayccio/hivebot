# scheduler/tests/test_orchestrator.py
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import json
from datetime import datetime

# We'll test the functions from scheduler.main
import sys
sys.path.append('..')
from scheduler.main import are_dependencies_met

@pytest.mark.asyncio
async def test_are_dependencies_met_true():
    mock_pg = AsyncMock()
    mock_conn = AsyncMock()
    # Make acquire return the connection when awaited
    mock_pg.acquire = AsyncMock(return_value=mock_conn)
    # Make the connection itself an async context manager
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    # Mock fetch to return rows with completed status
    async def mock_fetch(query, *args):
        return [{'data': json.dumps({'status': 'completed'})}]
    mock_conn.fetch = AsyncMock(side_effect=mock_fetch)

    result = await are_dependencies_met(mock_pg, "task1", ["dep1", "dep2"])
    assert result is True

@pytest.mark.asyncio
async def test_are_dependencies_met_false():
    mock_pg = AsyncMock()
    mock_conn = AsyncMock()
    mock_pg.acquire = AsyncMock(return_value=mock_conn)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    async def mock_fetch(query, *args):
        # Simulate that one dependency is not completed
        if args[0][0] == "dep1":
            return [{'data': json.dumps({'status': 'completed'})}]
        else:
            return [{'data': json.dumps({'status': 'pending'})}]
    mock_conn.fetch = AsyncMock(side_effect=mock_fetch)

    result = await are_dependencies_met(mock_pg, "task1", ["dep1", "dep2"])
    assert result is False
