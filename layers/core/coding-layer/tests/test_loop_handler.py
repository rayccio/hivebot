import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from loop import CodingLoopHandler

@pytest.mark.asyncio
async def test_loop_handler_success_first_try():
    handler = CodingLoopHandler()

    # Mock call_ai_delta to return success
    async def mock_call_ai_delta(agent_id, user_input, model_config, system_prompt_override=None, retries=1):
        if "Generate the code" in user_input:
            return "def test(): return True"
        elif "Write and run tests" in user_input:
            return '{"passed": true, "errors": []}'
        elif "Review the code" in user_input:
            return '{"issues": [], "approved": true}'
        else:
            return ""

    mock_save_artifact = AsyncMock(return_value={"id": "art-123"})
    mock_update_artifact_status = AsyncMock()
    mock_skill_executor = AsyncMock()

    result = await handler.run(
        agent_id="b-test",
        task_id="t-test",
        description="Write a test function",
        input_data={},
        goal_id="g-test",
        hive_id="h-test",
        project_id=None,
        skill_executor=mock_skill_executor,
        call_ai_delta=mock_call_ai_delta,
        save_artifact=mock_save_artifact,
        update_artifact_status=mock_update_artifact_status
    )

    assert result["success"] is True
    assert result["iterations"] == 1
    assert mock_save_artifact.call_count == 4  # code, test, review, final
    mock_update_artifact_status.assert_any_call("h-test", "g-test", "art-123", "built")
    mock_update_artifact_status.assert_any_call("h-test", "g-test", "art-123", "tested")
    mock_update_artifact_status.assert_any_call("h-test", "g-test", "art-123", "reviewed")
    mock_update_artifact_status.assert_any_call("h-test", "g-test", "art-123", "final")

@pytest.mark.asyncio
async def test_loop_handler_test_failure_then_fix():
    handler = CodingLoopHandler()
    handler.MAX_ITERATIONS = 2

    call_count = 0
    async def mock_call_ai_delta(agent_id, user_input, model_config, system_prompt_override=None, retries=1):
        nonlocal call_count
        call_count += 1
        if "Generate the code" in user_input:
            if call_count == 1:
                return "def test(): return False"
            elif call_count == 4:  # fixer
                return "def test(): return True"
            else:
                return "def test(): return True"
        elif "Write and run tests" in user_input:
            if call_count == 2:
                return '{"passed": false, "errors": ["Expected True got False"]}'
            else:
                return '{"passed": true, "errors": []}'
        elif "Review the code" in user_input:
            return '{"issues": [], "approved": true}'
        else:
            return ""

    mock_save_artifact = AsyncMock(return_value={"id": "art-123"})
    mock_update_artifact_status = AsyncMock()
    mock_skill_executor = AsyncMock()

    result = await handler.run(
        agent_id="b-test",
        task_id="t-test",
        description="Write a test function",
        input_data={},
        goal_id="g-test",
        hive_id="h-test",
        project_id=None,
        skill_executor=mock_skill_executor,
        call_ai_delta=mock_call_ai_delta,
        save_artifact=mock_save_artifact,
        update_artifact_status=mock_update_artifact_status
    )

    assert result["success"] is True
    assert result["iterations"] == 2
    # Expect 2 iterations: builder1, test1, fixer, builder2, test2, review, final = 7 saves
    assert mock_save_artifact.call_count == 7
