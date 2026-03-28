# backend/app/services/goal_engine.py
import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import text
from ..core.database import AsyncSessionLocal
from ..models.types import HiveGoal, HiveGoalStatus, HiveTaskStatus
import logging

logger = logging.getLogger(__name__)

class GoalEngine:
    """Manages the lifecycle of a Hive Goal."""

    async def create_goal(self, hive_id: str, description: str, constraints: dict = None, success_criteria: list = None) -> HiveGoal:
        goal_id = f"g-{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow()
        goal = HiveGoal(
            id=goal_id,
            hive_id=hive_id,
            description=description,
            constraints=constraints or {},
            success_criteria=success_criteria or [],
            status=HiveGoalStatus.CREATED,
            created_at=now,
            completed_at=None
        )
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("""
                    INSERT INTO goals (id, data)
                    VALUES (:id, :data)
                """),
                {"id": goal_id, "data": goal.model_dump_json()}
            )
            await session.commit()
        logger.info(f"Created goal {goal_id} for hive {hive_id}")
        return goal

    async def get_goal(self, goal_id: str) -> Optional[HiveGoal]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT data FROM goals WHERE id = :id"),
                {"id": goal_id}
            )
            row = result.fetchone()
            if row:
                return HiveGoal.model_validate(row[0])
        return None

    async def update_goal_status(self, goal_id: str, status: HiveGoalStatus) -> Optional[HiveGoal]:
        goal = await self.get_goal(goal_id)
        if not goal:
            return None
        goal.status = status
        if status == HiveGoalStatus.COMPLETED:
            goal.completed_at = datetime.utcnow()
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE goals SET data = :data WHERE id = :id"),
                {"data": goal.model_dump_json(), "id": goal_id}
            )
            await session.commit()
        return goal

    async def cancel_goal(self, goal_id: str) -> Optional[HiveGoal]:
        goal = await self.get_goal(goal_id)
        if not goal:
            return None
        if goal.status in (HiveGoalStatus.COMPLETED, HiveGoalStatus.FAILED):
            return goal

        goal.status = HiveGoalStatus.FAILED
        goal.completed_at = datetime.utcnow()
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE goals SET data = :data WHERE id = :id"),
                {"data": goal.model_dump_json(), "id": goal_id}
            )
            # Update all pending/assigned tasks to CANCELLED using JSONB merge
            await session.execute(
                text("""
                    UPDATE tasks
                    SET data = data || '{"status": "cancelled"}'
                    WHERE data->>'goalId' = :goal_id
                      AND (data->>'status' IN ('pending', 'assigned', 'running'))
                """),
                {"goal_id": goal_id}
            )
            await session.commit()
        logger.info(f"Goal {goal_id} cancelled")
        return goal

    async def list_goals_for_hive(self, hive_id: str) -> List[HiveGoal]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT data FROM goals WHERE data->>'hive_id' = :hive_id ORDER BY (data->>'created_at')::timestamptz DESC"),
                {"hive_id": hive_id}
            )
            rows = result.fetchall()
            return [HiveGoal.model_validate(r[0]) for r in rows]

    async def list_goals_by_status(self, statuses: List[HiveGoalStatus]) -> List[HiveGoal]:
        status_strings = [s.value for s in statuses]
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT data FROM goals WHERE data->>'status' = ANY(:statuses) ORDER BY (data->>'created_at')::timestamptz"),
                {"statuses": status_strings}
            )
            rows = result.fetchall()
            return [HiveGoal.model_validate(r[0]) for r in rows]
