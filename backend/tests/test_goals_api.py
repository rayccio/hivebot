import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app as fastapi_app
from app.models.types import HiveGoal, HiveGoalStatus, HiveTask, HiveTaskStatus, Hive
from datetime import datetime
import json

@pytest.mark.asyncio
async def test_create_goal_api(client: AsyncClient, session):
    # ---- NEW: Create a real hive in the test database ----
    from app.models.types import Hive, HiveMindConfig
    from app.core.database import AsyncSessionLocal
    import uuid
    hive_id = "h-test"
    hive_data = Hive(
        id=hive_id,
        name="Test Hive",
        description="",
        agent_ids=[],
        global_user_md="context",
        messages=[],
        global_files=[],
        hive_mind_config=HiveMindConfig(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    # Insert directly using SQLAlchemy model (the session fixture is a real async session)
    async with AsyncSessionLocal() as db_session:
        db_hive = HiveModel(id=hive_data.id, data=hive_data.model_dump(by_alias=True))
        db_session.add(db_hive)
        await db_session.commit()
    # -------------------------------------------------------

    # Mock dependencies
    mock_goal_engine = AsyncMock()
    mock_goal = HiveGoal(
        id="g-test",
        hive_id=hive_id,
        description="Test goal",
        constraints={},
        success_criteria=[],
        status=HiveGoalStatus.CREATED,
        created_at=datetime.utcnow()
    )
    mock_goal_engine.create_goal.return_value = mock_goal

    mock_planner = AsyncMock()
    mock_task = HiveTask(
        id="t-test",
        goal_id="g-test",
        hive_id=hive_id,
        description="Task",
        agent_type="builder",
        status=HiveTaskStatus.PENDING,
        depends_on=[],
        required_skills=[],
        created_at=datetime.utcnow()
    )
    mock_planner.plan.return_value = [mock_task]

    mock_hive_manager = AsyncMock()
    mock_hive = MagicMock(spec=Hive)
    mock_hive.global_user_md = "context"
    mock_hive_manager.get_hive.return_value = mock_hive

    # Apply dependency overrides
    from app.api.v1.endpoints.goals import get_goal_engine, get_planner, get_hive_manager
    fastapi_app.dependency_overrides[get_goal_engine] = lambda: mock_goal_engine
    fastapi_app.dependency_overrides[get_planner] = lambda: mock_planner
    fastapi_app.dependency_overrides[get_hive_manager] = lambda: mock_hive_manager

    # Patch SkillManager
    with patch('app.services.skill_manager.SkillManager') as MockSkillManager:
        mock_skill_manager = AsyncMock()
        mock_skill_manager.list_skills = AsyncMock(return_value=[])
        MockSkillManager.return_value = mock_skill_manager

        payload = {
            "description": "Test goal",
            "constraints": {},
            "success_criteria": []
        }
        response = await client.post(f"/api/v1/hives/{hive_id}/goals", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["goal"]["id"] == "g-test"
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["id"] == "t-test"

    fastapi_app.dependency_overrides.clear()
