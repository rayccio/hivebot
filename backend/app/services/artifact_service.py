import os
import aiofiles
import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import text
from ..core.database import AsyncSessionLocal
from ..core.config import settings
from ..models.types import HiveArtifact
import logging

logger = logging.getLogger(__name__)

class ArtifactService:
    """Manages artifacts (files) associated with goals and tasks."""

    def __init__(self):
        self.base_path = settings.DATA_DIR / "artifacts"
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def _get_next_version(self, goal_id: str, task_id: str, file_path: str) -> int:
        """Get the next version number for a given file path within a goal/task."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT MAX((data->>'version')::int) FROM artifacts
                    WHERE data->>'goal_id' = :goal_id
                      AND data->>'task_id' = :task_id
                      AND data->>'file_path' = :file_path
                """),
                {"goal_id": goal_id, "task_id": task_id, "file_path": file_path}
            )
            max_version = result.scalar()
            return (max_version or 0) + 1

    async def create_artifact(
        self,
        goal_id: str,
        task_id: str,
        file_path: str,
        content: bytes,
        status: str = "draft"
    ) -> HiveArtifact:
        """Create a new artifact (new version)."""
        if ".." in file_path or file_path.startswith("/"):
            raise ValueError("Invalid file path")

        version = await self._get_next_version(goal_id, task_id, file_path)
        artifact_id = f"art-{uuid.uuid4().hex[:8]}"

        artifact_file = self.base_path / artifact_id
        async with aiofiles.open(artifact_file, "wb") as f:
            await f.write(content)

        artifact = HiveArtifact(
            id=artifact_id,
            goal_id=goal_id,
            task_id=task_id,
            file_path=file_path,
            content="",
            version=version,
            status=status,
            created_at=datetime.utcnow()
        )

        async with AsyncSessionLocal() as session:
            await session.execute(
                text("INSERT INTO artifacts (id, data) VALUES (:id, :data)"),
                {"id": artifact_id, "data": artifact.model_dump_json()}
            )
            await session.commit()

        logger.info(f"Created artifact {artifact_id} (v{version}) for goal {goal_id}")
        return artifact

    async def get_artifact(self, artifact_id: str) -> Optional[HiveArtifact]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT data FROM artifacts WHERE id = :id"),
                {"id": artifact_id}
            )
            row = result.fetchone()
            if row:
                return HiveArtifact.model_validate(row[0])
        return None

    async def list_artifacts(self, goal_id: str, task_id: Optional[str] = None) -> List[HiveArtifact]:
        async with AsyncSessionLocal() as session:
            query = "SELECT data FROM artifacts WHERE data->>'goal_id' = :goal_id"
            params = {"goal_id": goal_id}
            if task_id:
                query += " AND data->>'task_id' = :task_id"
                params["task_id"] = task_id
            query += " ORDER BY (data->>'created_at')::timestamptz DESC"
            result = await session.execute(text(query), params)
            rows = result.fetchall()
            return [HiveArtifact.model_validate(r[0]) for r in rows]

    async def get_latest_artifact(self, goal_id: str, task_id: str, file_path: str) -> Optional[HiveArtifact]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""
                    SELECT data FROM artifacts
                    WHERE data->>'goal_id' = :goal_id
                      AND data->>'task_id' = :task_id
                      AND data->>'file_path' = :file_path
                    ORDER BY (data->>'version')::int DESC
                    LIMIT 1
                """),
                {"goal_id": goal_id, "task_id": task_id, "file_path": file_path}
            )
            row = result.fetchone()
            if row:
                return HiveArtifact.model_validate(row[0])
        return None

    async def update_artifact_status(self, artifact_id: str, status: str) -> Optional[HiveArtifact]:
        artifact = await self.get_artifact(artifact_id)
        if not artifact:
            return None
        artifact.status = status
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE artifacts SET data = :data WHERE id = :id"),
                {"data": artifact.model_dump_json(), "id": artifact_id}
            )
            await session.commit()
        return artifact

    async def delete_artifact(self, artifact_id: str) -> bool:
        artifact = await self.get_artifact(artifact_id)
        if not artifact:
            return False
        artifact_file = self.base_path / artifact_id
        if artifact_file.exists():
            artifact_file.unlink()
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("DELETE FROM artifacts WHERE id = :id"),
                {"id": artifact_id}
            )
            await session.commit()
        logger.info(f"Deleted artifact {artifact_id}")
        return True

    async def read_artifact_content(self, artifact_id: str) -> Optional[bytes]:
        artifact_file = self.base_path / artifact_id
        if not artifact_file.exists():
            return None
        async with aiofiles.open(artifact_file, "rb") as f:
            return await f.read()
