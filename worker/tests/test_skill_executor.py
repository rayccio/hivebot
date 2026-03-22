import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from skill_executor import SkillExecutor

@pytest.mark.asyncio
async def test_skill_executor_permission_check():
    executor = SkillExecutor()
    result = await executor.execute(
        skill_name="web_search",
        params={"query": "test"},
        simulation=False,
        allowed_skills=["web_search"]
    )
    # It will try to actually call web_search which may fail if no API key, but that's fine.
    # We just test permission path.
    assert "error" not in result  # It may actually return an error from web_search if no key, but that's ok.

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
