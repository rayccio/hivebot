import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json

@pytest.mark.asyncio
async def test_coding_planner_success():
    # Mock the LLM response
    mock_response = {
        "tasks": [
            {
                "id": "task_1",
                "description": "Create frontend",
                "agent_type": "frontend-developer",
                "depends_on": [],
                "required_skills": ["html_builder", "css_styling"]
            },
            {
                "id": "task_2",
                "description": "Create backend API",
                "agent_type": "backend-developer",
                "depends_on": [],
                "required_skills": ["rest_api"]
            }
        ],
        "reasoning": "split frontend/backend"
    }

    # Mock the settings.secrets.get to return a provider config
    mock_provider_config = {
        "providers": {
            "openai": {
                "models": {
                    "gpt-4o": {"is_primary": True, "enabled": True}
                }
            }
        }
    }

    with patch('planner.planner.generate_with_messages', new_callable=AsyncMock) as mock_gen, \
         patch('planner.planner.settings.secrets.get', return_value=mock_provider_config):
        mock_gen.return_value = json.dumps(mock_response)

        # Import after patching to ensure the module uses the patched dependencies
        from planner.planner import CodingPlanner
        planner = CodingPlanner()
        tasks = await planner.plan(
            goal_text="Build a web app",
            hive_context="",
            skills=[
                {"id": "sk1", "name": "html_builder", "description": "Builds HTML"},
                {"id": "sk2", "name": "css_styling", "description": "Styles"},
                {"id": "sk3", "name": "rest_api", "description": "API"},
            ],
            roles=["frontend-developer", "backend-developer"]
        )

        assert len(tasks) == 2
        assert tasks[0].description == "Create frontend"
        assert tasks[0].agent_type == "frontend-developer"
        assert tasks[0].required_skills == ["sk1", "sk2"]  # IDs mapped
        assert tasks[0].loop_handler == "coding_loop"
        assert tasks[1].description == "Create backend API"
        assert tasks[1].required_skills == ["sk3"]

@pytest.mark.asyncio
async def test_coding_planner_fallback():
    # Mock settings to return a provider config (required for fallback path)
    mock_provider_config = {
        "providers": {
            "openai": {
                "models": {
                    "gpt-4o": {"is_primary": True, "enabled": True}
                }
            }
        }
    }

    with patch('planner.planner.generate_with_messages', new_callable=AsyncMock, side_effect=Exception("AI error")), \
         patch('planner.planner.settings.secrets.get', return_value=mock_provider_config):
        from planner.planner import CodingPlanner
        planner = CodingPlanner()
        tasks = await planner.plan(
            goal_text="Build a web app",
            hive_context="",
            skills=[],
            roles=[]
        )

        assert len(tasks) == 1
        assert tasks[0].description == "Build a web app"
        assert tasks[0].agent_type == "builder"
        assert tasks[0].required_skills == []
        assert tasks[0].loop_handler == "coding_loop"
