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
        return Project(
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

    async def get_project(self, project_id: str) -> Optional[Project]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT id, hive_id, name, description, goal, root_goal_id, state, created_at, updated_at FROM projects WHERE id = :id"),
                {"id": project_id}
            )
            row = result.fetchone()
            if row:
                return Project(
                    id=row[0],
                    hive_id=row[1],
                    name=row[2],
                    description=row[3],
                    goal=row[4],
                    root_goal_id=row[5],
                    state=row[6],
                    created_at=row[7],
                    updated_at=row[8]
                )
        return None

    async def list_projects(self, hive_id: str) -> List[Project]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT id, hive_id, name, description, goal, root_goal_id, state, created_at, updated_at FROM projects WHERE hive_id = :hive_id ORDER BY created_at DESC"),
                {"hive_id": hive_id}
            )
            rows = result.fetchall()
            projects = []
            for row in rows:
                projects.append(Project(
                    id=row[0],
                    hive_id=row[1],
                    name=row[2],
                    description=row[3],
                    goal=row[4],
                    root_goal_id=row[5],
                    state=row[6],
                    created_at=row[7],
                    updated_at=row[8]
                ))
            return projects

    async def update_project_state(self, project_id: str, state: str) -> Optional[Project]:
        now = datetime.utcnow()
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    UPDATE projects
                    SET state = :state, updated_at = :updated_at
                    WHERE id = :id
                    RETURNING id, hive_id, name, description, goal, root_goal_id, state, created_at, updated_at
                """),
                {"id": project_id, "state": state, "updated_at": now}
            )
            row = result.fetchone()
            if row:
                return Project(
                    id=row[0],
                    hive_id=row[1],
                    name=row[2],
                    description=row[3],
                    goal=row[4],
                    root_goal_id=row[5],
                    state=row[6],
                    created_at=row[7],
                    updated_at=row[8]
                )
        return None
