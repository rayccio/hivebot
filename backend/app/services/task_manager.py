import json
import os
from typing import Dict, Optional, List
from datetime import datetime
from ..models.task import Task, TaskGraph, TaskStatus
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

    async def create_task_graph(self, hive_id: str, goal: str, tasks: List[Task], edges: List[Dict[str, str]]) -> TaskGraph:
        goal_id = f"g-{uuid.uuid4().hex[:8]}"
        for task in tasks:
            task.goal_id = goal_id
        graph = TaskGraph(
            goal_id=goal_id,
            goal_description=goal,
            hive_id=hive_id,
            tasks=tasks,
            edges=edges,
            created_at=datetime.utcnow()
        )
        repo, session = await self._get_repo()
        try:
            # Store each task individually
            for task in tasks:
                await repo.create(task)
        finally:
            await session.close()
        # Return a graph object (not stored)
        return graph

    async def get_task_graph(self, goal_id: str) -> Optional[TaskGraph]:
        repo, session = await self._get_repo()
        try:
            tasks = await repo.get_all()
            graph_tasks = [t for t in tasks if t.goal_id == goal_id]
            if not graph_tasks:
                return None
            # We need edges; they are not stored separately. For now, return without edges.
            graph = TaskGraph(
                goal_id=goal_id,
                goal_description=graph_tasks[0].goal_description if graph_tasks else "",
                hive_id=graph_tasks[0].hive_id,
                tasks=graph_tasks,
                edges=[],
                created_at=graph_tasks[0].created_at
            )
            return graph
        finally:
            await session.close()

    async def get_task(self, task_id: str) -> Optional[Task]:
        repo, session = await self._get_repo()
        try:
            return await repo.get(task_id)
        finally:
            await session.close()

    async def update_task(self, task_id: str, **updates) -> Optional[Task]:
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
        return await self.update_task(task_id, assigned_agent_id=agent_id, status=TaskStatus.ASSIGNED) is not None

    async def list_tasks_for_hive(self, hive_id: str) -> List[Task]:
        repo, session = await self._get_repo()
        try:
            tasks = await repo.get_all()
            return [t for t in tasks if t.hive_id == hive_id]
        finally:
            await session.close()

    async def list_graphs_for_hive(self, hive_id: str) -> List[TaskGraph]:
        repo, session = await self._get_repo()
        try:
            tasks = await repo.get_all()
            # Group by goal_id
            graphs = {}
            for t in tasks:
                if t.hive_id == hive_id:
                    if t.goal_id not in graphs:
                        graphs[t.goal_id] = []
                    graphs[t.goal_id].append(t)
            result = []
            for goal_id, task_list in graphs.items():
                if task_list:
                    graph = TaskGraph(
                        goal_id=goal_id,
                        goal_description=task_list[0].goal_description,
                        hive_id=hive_id,
                        tasks=task_list,
                        edges=[],
                        created_at=task_list[0].created_at
                    )
                    result.append(graph)
            return result
        finally:
            await session.close()
