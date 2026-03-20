import json
import os
from typing import Dict, Optional, List
from datetime import datetime
from ..models.types import HiveTask, HiveTaskStatus
from ..core.config import settings
from ..core.database import AsyncSessionLocal
from ..repositories.task_repository import TaskRepository
import uuid
import logging

logger = logging.getLogger(__name__)

class TaskManager:
    def __init__(self):
        self.repo = TaskRepository

    async def _get_repo(self):
        session = AsyncSessionLocal()
        return TaskRepository(session), session

    async def create_task_graph(self, hive_id: str, goal: str, tasks: List[HiveTask], edges: List[Dict[str, str]]) -> dict:
        goal_id = f"g-{uuid.uuid4().hex[:8]}"
        for task in tasks:
            task.goal_id = goal_id
            task.hive_id = hive_id
        repo, session = await self._get_repo()
        try:
            for task in tasks:
                await repo.create(task)
        finally:
            await session.close()
        return {"goal_id": goal_id, "tasks": tasks}

    async def get_task_graph(self, goal_id: str) -> Optional[List[HiveTask]]:
        repo, session = await self._get_repo()
        try:
            tasks = await repo.get_by_goal_id(goal_id)
            return tasks
        finally:
            await session.close()

    async def get_task(self, task_id: str) -> Optional[HiveTask]:
        repo, session = await self._get_repo()
        try:
            return await repo.get(task_id)
        finally:
            await session.close()

    async def update_task(self, task_id: str, **updates) -> Optional[HiveTask]:
        repo, session = await self._get_repo()
        try:
            task = await repo.get(task_id)
            if not task:
                return None
            for k, v in updates.items():
                if hasattr(task, k):
                    setattr(task, k, v)
            await repo.update(task_id, task.model_dump(by_alias=True))
            return task
        finally:
            await session.close()

    async def assign_task(self, task_id: str, agent_id: str) -> bool:
        return await self.update_task(task_id, assigned_agent_id=agent_id, status=HiveTaskStatus.ASSIGNED) is not None

    async def list_tasks_for_hive(self, hive_id: str) -> List[HiveTask]:
        repo, session = await self._get_repo()
        try:
            return await repo.get_by_hive_id(hive_id)
        finally:
            await session.close()

    async def list_graphs_for_hive(self, hive_id: str) -> List[dict]:
        repo, session = await self._get_repo()
        try:
            tasks = await repo.get_by_hive_id(hive_id)
            graphs = {}
            for t in tasks:
                if t.goal_id not in graphs:
                    graphs[t.goal_id] = []
                graphs[t.goal_id].append(t)
            result = []
            for goal_id, task_list in graphs.items():
                if task_list:
                    result.append({
                        "goal_id": goal_id,
                        "goal_description": task_list[0].description,
                        "hive_id": hive_id,
                        "tasks": task_list,
                        "created_at": task_list[0].created_at
                    })
            return result
        finally:
            await session.close()

    async def list_tasks_for_agent(self, agent_id: str) -> List[HiveTask]:
        repo, session = await self._get_repo()
        try:
            return await repo.get_by_agent_id(agent_id)
        finally:
            await session.close()
