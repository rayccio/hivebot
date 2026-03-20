import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import json
from datetime import datetime
import sys
import os
import tempfile

# Set log directory to a temporary location before importing worker.main
os.environ['HIVEBOT_LOG_DIR'] = tempfile.mkdtemp()

sys.path.append('..')
from worker.main import execute_task_with_loop, process_task_assign, parse_allowed_tools

@pytest.mark.asyncio
async def test_parse_allowed_tools():
    tools_md = """## Permitted Tools
- web_search
- ssh_execute
- browser_action
- run_code
- api_call

## Prohibited
- write_file
"""
    allowed = parse_allowed_tools(tools_md)
    assert set(allowed) == {"web_search", "ssh_execute", "browser_action", "run_code", "api_call"}

def test_parse_allowed_tools_empty():
    assert parse_allowed_tools("") == []
    assert parse_allowed_tools("No dashes here") == []

@pytest.mark.asyncio
async def test_execute_task_with_loop_success_first_try():
    agent_id = "b-test"
    task_id = "t-test"
    description = "Write a function that returns True"
    input_data = {}
    goal_id = "g-test"
    hive_id = "h-test"
    agent_data = {"reasoning": {"model": "openai/gpt-4o"}, "tools_md": "- run_code"}
    allowed_tools = ["run_code"]

    with patch('worker.main.call_ai_delta', new_callable=AsyncMock) as mock_call, \
         patch('worker.main.save_artifact', new_callable=AsyncMock) as mock_save:

        mock_call.side_effect = [
            "def test_func(): return True",  # builder
            '{"passed": true, "errors": []}'  # tester
        ]

        success, iterations = await execute_task_with_loop(
            agent_id, task_id, description, input_data, goal_id, hive_id, agent_data, allowed_tools
        )

        assert success is True
        assert iterations == 1
        assert mock_call.call_count == 2
        assert mock_save.call_count == 3  # code, test result, final

@pytest.mark.asyncio
async def test_execute_task_with_loop_failure_then_fix():
    agent_id = "b-test"
    task_id = "t-test"
    description = "Write a function that returns True"
    input_data = {}
    goal_id = "g-test"
    hive_id = "h-test"
    agent_data = {"reasoning": {"model": "openai/gpt-4o"}, "tools_md": "- run_code"}
    allowed_tools = ["run_code"]

    with patch('worker.main.call_ai_delta', new_callable=AsyncMock) as mock_call, \
         patch('worker.main.save_artifact', new_callable=AsyncMock) as mock_save:

        with patch('worker.main.MAX_ITERATIONS', 2):
            mock_call.side_effect = [
                "def test_func(): return False",      # builder1
                '{"passed": false, "errors": ["Expected True got False"]}',  # tester1
                "The function returns False instead of True",  # reviewer
                "def test_func(): return True",       # fixer
                "def test_func(): return True",       # builder2 (iteration2)
                '{"passed": true, "errors": []}'      # tester2
            ]

            success, iterations = await execute_task_with_loop(
                agent_id, task_id, description, input_data, goal_id, hive_id, agent_data, allowed_tools
            )

            assert success is True
            assert iterations == 2
            assert mock_call.call_count == 6
            assert mock_save.call_count == 7  # code1, test1, issues, fixed, code2, test2, final

@pytest.mark.asyncio
async def test_process_task_assign_integration():
    agent_id = "b-test"
    task_id = "t-test"
    description = "Write a function"
    input_data = {}
    goal_id = "g-test"
    hive_id = "h-test"

    agent_data = {
        "status": "IDLE",
        "memory": {"shortTerm": [], "summary": "", "tokenCount": 0},
        "tools_md": "## Permitted Tools\n- run_code"
    }

    with patch('worker.main.get_agent_from_db', new_callable=AsyncMock) as mock_get, \
         patch('worker.main.update_agent_state', new_callable=AsyncMock) as mock_update, \
         patch('worker.main.execute_task_with_loop', new_callable=AsyncMock) as mock_loop, \
         patch('worker.main.register_agent_idle', new_callable=AsyncMock) as mock_register, \
         patch('worker.main.redis.from_url', new_callable=AsyncMock) as mock_redis:

        mock_get.return_value = agent_data
        mock_loop.return_value = (True, 2)

        mock_redis_client = AsyncMock()
        mock_redis_client.publish = AsyncMock()
        mock_redis_client.close = AsyncMock()
        mock_redis.return_value = mock_redis_client

        await process_task_assign(agent_id, task_id, description, input_data, goal_id, hive_id, simulation=False)

        mock_loop.assert_awaited_once_with(
            agent_id, task_id, description, input_data, goal_id, hive_id, agent_data, ["run_code"]
        )
        assert mock_update.await_count >= 2
        mock_register.assert_awaited_once_with(agent_id)
        mock_redis_client.publish.assert_awaited_once()
