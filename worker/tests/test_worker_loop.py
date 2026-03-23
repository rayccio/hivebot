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
from worker.main import parse_allowed_tools, process_task_assign
from worker.loop_handler import DefaultLoopHandler

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
async def test_default_loop_handler_success_first_try():
    agent_id = "b-test"
    task_id = "t-test"
    description = "Write a function that returns True"
    input_data = {}
    goal_id = "g-test"
    hive_id = "h-test"
    project_id = "p-test"

    # Mock call_ai_delta
    async def mock_call_ai_delta(agent_id, user_input, model_config, system_prompt_override=None, retries=1):
        # Return different responses based on the prompt content
        if "Generate the code" in user_input:
            return "def test_func(): return True"
        elif "Write and run tests" in user_input:
            return '{"passed": true, "errors": []}'
        else:
            return ""

    mock_save_artifact = AsyncMock()
    mock_skill_executor = AsyncMock()

    handler = DefaultLoopHandler()
    result = await handler.run(
        agent_id=agent_id,
        task_id=task_id,
        description=description,
        input_data=input_data,
        goal_id=goal_id,
        hive_id=hive_id,
        project_id=project_id,
        skill_executor=mock_skill_executor,
        call_ai_delta=mock_call_ai_delta,
        save_artifact=mock_save_artifact
    )

    assert result["success"] is True
    assert result["iterations"] == 1
    assert mock_save_artifact.call_count == 3  # code, test result, final

@pytest.mark.asyncio
async def test_default_loop_handler_failure_then_fix():
    agent_id = "b-test"
    task_id = "t-test"
    description = "Write a function that returns True"
    input_data = {}
    goal_id = "g-test"
    hive_id = "h-test"
    project_id = "p-test"

    # Simulate first test fails, then fix
    call_count = 0
    async def mock_call_ai_delta(agent_id, user_input, model_config, system_prompt_override=None, retries=1):
        nonlocal call_count
        call_count += 1
        if "Generate the code" in user_input:
            if call_count == 1:
                return "def test_func(): return False"   # first builder
            elif call_count == 4:
                return "def test_func(): return True"    # fixer
            elif call_count == 5:
                return "def test_func(): return True"    # second builder
            else:
                return "def test_func(): return True"
        elif "Write and run tests" in user_input:
            if call_count == 2:
                return '{"passed": false, "errors": ["Expected True got False"]}'
            elif call_count == 6:
                return '{"passed": true, "errors": []}'
            else:
                return '{"passed": true, "errors": []}'
        elif "List the issues" in user_input:
            return "The function returns False instead of True"
        else:
            return ""

    mock_save_artifact = AsyncMock()
    mock_skill_executor = AsyncMock()

    # Patch MAX_ITERATIONS to 2 to speed up test
    with patch('worker.loop_handler.DefaultLoopHandler.MAX_ITERATIONS', 2):
        handler = DefaultLoopHandler()
        result = await handler.run(
            agent_id=agent_id,
            task_id=task_id,
            description=description,
            input_data=input_data,
            goal_id=goal_id,
            hive_id=hive_id,
            project_id=project_id,
            skill_executor=mock_skill_executor,
            call_ai_delta=mock_call_ai_delta,
            save_artifact=mock_save_artifact
        )

    assert result["success"] is True
    assert result["iterations"] == 2
    # Expected calls: builder1, test1, reviewer, fixer, builder2, test2, final = 7
    assert mock_save_artifact.call_count == 7

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
        "tools_md": "## Permitted Tools\n- run_code",
        "skills": [{"skillId": "run_code", "enabled": True}]
    }

    # Mock call_ai_delta to simulate the loop handler calls
    async def mock_call_ai_delta(agent_id, user_input, model_config, system_prompt_override=None, retries=1):
        if "Generate the code" in user_input:
            return "def test_func(): return True"
        elif "Write and run tests" in user_input:
            return '{"passed": true, "errors": []}'
        else:
            return ""

    with patch('worker.main.get_agent_from_db', new_callable=AsyncMock) as mock_get, \
         patch('worker.main.update_agent_state', new_callable=AsyncMock) as mock_update, \
         patch('worker.main.loop_handler_registry.get') as mock_registry_get, \
         patch('worker.main.loop_handler_registry.default') as mock_registry_default, \
         patch('worker.main.register_agent_idle', new_callable=AsyncMock) as mock_register, \
         patch('worker.main.redis.from_url', new_callable=AsyncMock) as mock_redis, \
         patch('worker.main.log_execution', new_callable=AsyncMock) as mock_log, \
         patch('worker.main.call_ai_delta', new_callable=AsyncMock) as mock_call_ai_delta_patch:

        mock_get.return_value = agent_data
        mock_call_ai_delta_patch.side_effect = mock_call_ai_delta

        # Mock the task DB fetch
        with patch('worker.main.AsyncSessionLocal') as mock_session:
            mock_conn = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_conn
            mock_result = MagicMock()
            mock_result.fetchone.return_value = (json.dumps({"loop_handler": "default", "project_id": "p-test"}),)
            mock_conn.execute.return_value = mock_result

            # Mock the loop handler
            mock_registry_get.return_value = DefaultLoopHandler
            mock_registry_default.return_value = DefaultLoopHandler

            mock_redis_client = AsyncMock()
            mock_redis_client.publish = AsyncMock()
            mock_redis_client.close = AsyncMock()
            mock_redis.return_value = mock_redis_client

            await process_task_assign(agent_id, task_id, description, input_data, goal_id, hive_id, simulation=False)

            mock_register.assert_awaited_once_with(agent_id)
            mock_redis_client.publish.assert_awaited_once()
