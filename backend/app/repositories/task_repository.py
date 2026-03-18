from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, text
from ..models.db_models import TaskModel
from ..models.types import HiveTask
from ..utils.json_encoder import prepare_json_data
import json
from typing import List, Optional

class TaskRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, task: HiveTask) -> HiveTask:
        data = prepare_json_data(task.model_dump(by_alias=True))
        db_task = TaskModel(
            id=task.id,
            data=data
        )
        self.db.add(db_task)
        await self.db.commit()
        await self.db.refresh(db_task)
        return task

    async def get(self, task_id: str) -> Optional[HiveTask]:
        result = await self.db.execute(
            select(TaskModel).where(TaskModel.id == task_id)
        )
        db_task = result.scalar_one_or_none()
        if db_task:
            return HiveTask.model_validate(db_task.data)
        return None

    async def get_all(self) -> List[HiveTask]:
        result = await self.db.execute(select(TaskModel))
        db_tasks = result.scalars().all()
        return [HiveTask.model_validate(t.data) for t in db_tasks]

    async def get_by_hive_id(self, hive_id: str) -> List[HiveTask]:
        """Return all tasks belonging to a hive (by checking data->>'hiveId')."""
        result = await self.db.execute(
            text("SELECT data FROM tasks WHERE data->>'hiveId' = :hive_id"),
            {"hive_id": hive_id}
        )
        rows = result.fetchall()
        return [HiveTask.model_validate(r[0]) for r in rows]

    async def get_by_goal_id(self, goal_id: str) -> List[HiveTask]:
        result = await self.db.execute(
            text("SELECT data FROM tasks WHERE data->>'goalId' = :goal_id"),
            {"goal_id": goal_id}
        )
        rows = result.fetchall()
        return [HiveTask.model_validate(r[0]) for r in rows]

    async def update(self, task_id: str, updates: dict) -> Optional[HiveTask]:
        task = await self.get(task_id)
        if not task:
            return None
        for k, v in updates.items():
            if hasattr(task, k):
                setattr(task, k, v)
        data = prepare_json_data(task.model_dump(by_alias=True))
        await self.db.execute(
            update(TaskModel)
            .where(TaskModel.id == task_id)
            .values(data=data)
        )
        await self.db.commit()
        return task

    async def delete(self, task_id: str) -> bool:
        result = await self.db.execute(
            delete(TaskModel).where(TaskModel.id == task_id)
        )
        await self.db.commit()
        return result.rowcount > 0

