import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.planner import Planner
from app.models.types import HiveTaskStatus
import json

@pytest.mark.asyncio
async def test_plan_success():
    planner = Planner()
    mock_secrets = {
        "providers": {
            "openai": {
                "models": {
                    "gpt-4o": {"is_primary": True, "enabled": True}
                }
            }
        }
    }
    mock_response = json.dumps({
        "tasks": [
            {
                "id": "task_1",
                "description": "Write code",
                "agent_type": "builder",
                "depends_on": [],
                "required_skills": ["python"]
            }
        ],
        "reasoning": "ok"
    })

    with patch('app.services.planner.settings.secrets.get', return_value=mock_secrets), \
         patch('app.services.planner.generate_with_messages', new_callable=AsyncMock) as mock_gen, \
         patch('app.services.planner.AsyncSessionLocal') as mock_session, \
         patch.object(planner, '_get_enabled_layers', new_callable=AsyncMock) as mock_get_layers:

        mock_get_layers.return_value = [('core', 'HiveBot Core', None)]

        mock_gen.return_value = mock_response
        mock_conn = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_conn

        # Mock for roles query (single column)
        mock_roles_result = MagicMock()
        mock_roles_result.fetchall.return_value = [("builder",), ("tester",)]
        # Mock for skills query (three columns)
        mock_skills_result = MagicMock()
        mock_skills_result.fetchall.return_value = [
            ("sk-1", "web_search", "Search the web"),
            ("sk-2", "run_code", "Execute code in a container")
        ]
        # The planner calls execute twice: once for roles, once for skills.
        # We need to return the appropriate mock for each call.
        mock_conn.execute.side_effect = [mock_roles_result, mock_skills_result]

        mock_conn.commit = AsyncMock()

        tasks = await planner.plan(
            goal_id="g-test",
            hive_id="h-test",
            goal_text="Build a todo app",
            hive_context="context",
            skills=[]
        )

        assert len(tasks) == 1
        assert tasks[0].goal_id == "g-test"
        assert tasks[0].hive_id == "h-test"
        assert tasks[0].description == "Write code"
        assert tasks[0].agent_type == "builder"
        assert tasks[0].status == HiveTaskStatus.PENDING
        mock_conn.commit.assert_awaited_once()

@pytest.mark.asyncio
async def test_plan_fallback_on_failure():
    planner = Planner()
    mock_secrets = {
        "providers": {
            "openai": {
                "models": {
                    "gpt-4o": {"is_primary": True, "enabled": True}
                }
            }
        }
    }
    with patch('app.services.planner.settings.secrets.get', return_value=mock_secrets), \
         patch('app.services.planner.generate_with_messages', new_callable=AsyncMock, side_effect=Exception("API error")), \
         patch('app.services.planner.AsyncSessionLocal') as mock_session, \
         patch.object(planner, '_get_enabled_layers', new_callable=AsyncMock) as mock_get_layers:

        mock_get_layers.return_value = [('core', 'HiveBot Core', None)]

        mock_conn = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_conn

        # Mock for roles query (single column)
        mock_roles_result = MagicMock()
        mock_roles_result.fetchall.return_value = [("builder",), ("tester",)]
        # Mock for skills query (three columns)
        mock_skills_result = MagicMock()
        mock_skills_result.fetchall.return_value = [
            ("sk-1", "web_search", "Search the web"),
            ("sk-2", "run_code", "Execute code in a container")
        ]
        mock_conn.execute.side_effect = [mock_roles_result, mock_skills_result]

        mock_conn.commit = AsyncMock()

        tasks = await planner.plan(
            goal_id="g-test",
            hive_id="h-test",
            goal_text="Build a todo app"
        )
        assert len(tasks) == 1
        assert tasks[0].description == "Build a todo app"
        assert tasks[0].agent_type == "builder"
        assert tasks[0].hive_id == "h-test"
        mock_conn.commit.assert_awaited_once()
