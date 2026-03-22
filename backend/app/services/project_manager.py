import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import text
from ..core.database import AsyncSessionLocal
from ..models.types import Project
import logging

logger = logging.getLogger(__name__)

class ProjectManager:
    """Manages projects (top‑level containers for goals)."""

    async def create_project(
        self,
        hive_id: str,
        name: str,
        description: str,
        goal: str,
        root_goal_id: Optional[str] = None
    ) -> Project:
        """Create a new project."""
        project_id = f"p-{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow()
        project = Project(
            id=project_id,
            hive_id=hive_id,
            name=name,
            description=description,
            goal=goal,
            root_goal_id=root_goal_id,
            state="active",
            created_at=now,
            updated_at=now
        )
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("""
                    INSERT INTO projects (id, hive_id, name, description, goal, root_goal_id, state, created_at, updated_at)
                    VALUES (:id, :hive_id, :name, :description, :goal, :root_goal_id, :state, :created_at, :updated_at)
                """),
                {
                    "id": project_id,
                    "hive_id": hive_id,
                    "name": name,
                    "description": description,
                    "goal": goal,
                    "root_goal_id": root_goal_id,
                    "state": "active",
                    "created_at": now,
                    "updated_at": now
                }
            )
            await session.commit()
        logger.info(f"Created project {project_id} for hive {hive_id}")
        return project

    async def get_project(self, project_id: str) -> Optional[Project]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT data FROM projects WHERE id = :id"),
                {"id": project_id}
            )
            row = result.fetchone()
            if row:
                return Project.model_validate(row[0])
        return None

    async def list_projects(self, hive_id: str) -> List[Project]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT data FROM projects WHERE hive_id = :hive_id ORDER BY created_at DESC"),
                {"hive_id": hive_id}
            )
            rows = result.fetchall()
            return [Project.model_validate(r[0]) for r in rows]

    async def update_project_state(self, project_id: str, state: str) -> Optional[Project]:
        project = await self.get_project(project_id)
        if not project:
            return None
        project.state = state
        project.updated_at = datetime.utcnow()
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE projects SET data = :data WHERE id = :id"),
                {"data": project.model_dump_json(), "id": project_id}
            )
            await session.commit()
        return project
