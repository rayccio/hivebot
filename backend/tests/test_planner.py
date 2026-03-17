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
         patch('app.services.planner.AsyncSessionLocal') as mock_session:

        mock_gen.return_value = mock_response
        mock_conn = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_conn
        mock_conn.execute = AsyncMock()
        mock_conn.commit = AsyncMock()

        tasks = await planner.plan(
            goal_id="g-test",
            goal_text="Build a todo app",
            hive_context="context",
            skills=[]
        )

        assert len(tasks) == 1
        assert tasks[0].goal_id == "g-test"
        assert tasks[0].description == "Write code"
        assert tasks[0].agent_type == "builder"
        assert tasks[0].status == HiveTaskStatus.PENDING
        assert mock_conn.execute.call_count >= 2  # at least inserts and updates
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
         patch('app.services.planner.AsyncSessionLocal') as mock_session:

        mock_conn = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_conn
        mock_conn.execute = AsyncMock()
        mock_conn.commit = AsyncMock()

        tasks = await planner.plan("g-test", "Build a todo app")
        assert len(tasks) == 1
        assert tasks[0].description == "Build a todo app"
        assert tasks[0].agent_type == "builder"
