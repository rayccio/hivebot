import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from skill_executor import SkillExecutor

@pytest.mark.asyncio
async def test_skill_executor_permission_check():
    executor = SkillExecutor()

    with patch('skill_executor.AsyncSessionLocal') as mock_session:
        mock_conn = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_conn

        # Create a mock result proxy for the skills query
        mock_skill_result = MagicMock()
        mock_skill_result.scalar.return_value = "sk-123"

        # Create a mock result proxy for the versions query
        mock_version_result = MagicMock()
        mock_version_result.fetchone.return_value = ("sv-123", {
            "code": "def run(input, config): return {'result': 'ok'}",
            "language": "python"
        })

        # Side effect that returns the appropriate mock result based on the query text
        async def execute_side_effect(query, params):
            if "SELECT id FROM skills" in query.text:
                return mock_skill_result
            else:
                return mock_version_result

        mock_conn.execute = AsyncMock(side_effect=execute_side_effect)

        # Mock container manager
        with patch('skill_executor.container_manager.run_skill_in_container', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {"result": "ok"}

            result = await executor.execute(
                skill_name="web_search",
                params={"query": "test"},
                simulation=False,
                allowed_skills=["web_search"]
            )
            assert "error" not in result
            mock_run.assert_awaited_once()

    # Test disallowed skill
    result = await executor.execute(
        skill_name="web_search",
        params={"query": "test"},
        simulation=False,
        allowed_skills=["run_code"]
    )
    assert "error" in result
    assert "not in allowed skills list" in result["error"]


@pytest.mark.asyncio
async def test_skill_executor_simulation():
    executor = SkillExecutor()
    with patch.object(executor, '_call_simulator', new_callable=AsyncMock) as mock_sim:
        mock_sim.return_value = {"simulated": True}
        result = await executor.execute(
            skill_name="web_search",
            params={"query": "test"},
            simulation=True,
            allowed_skills=["web_search"]
        )
        assert result == {"simulated": True}
        mock_sim.assert_awaited_once_with("web_search", {"query": "test"})
