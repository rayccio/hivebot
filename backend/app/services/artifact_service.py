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
import json

logger = logging.getLogger(__name__)

class ArtifactService:
    """Manages artifacts (files) associated with goals and tasks."""

    def __init__(self):
        self.base_path = settings.DATA_DIR / "artifacts"
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def _get_lifecycle(self, layer_id: str) -> dict:
        """Fetch the lifecycle JSON for a layer. Return default if not found."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT lifecycle FROM layers WHERE id = :id"),
                {"id": layer_id}
            )
            row = await result.fetchone()
            if row and row[0]:
                return row[0]
            # Default lifecycle
            return {
                "states": ["draft", "built", "tested", "final"],
                "transitions": {
                    "draft": ["built"],
                    "built": ["tested"],
                    "tested": ["final"],
                }
            }

    async def _get_next_version(self, goal_id: str, task_id: str, file_path: str) -> int:
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
            max_version = await result.scalar()
            return (max_version or 0) + 1

    async def create_artifact(
        self,
        goal_id: str,
        task_id: str,
        file_path: str,
        content: bytes,
        status: str = "draft",
        layer_id: Optional[str] = None,
        parent_artifact_id: Optional[str] = None
    ) -> HiveArtifact:
        if ".." in file_path or file_path.startswith("/"):
            raise ValueError("Invalid file path")

        if not layer_id:
            layer_id = "core"

        version = await self._get_next_version(goal_id, task_id, file_path)
        artifact_id = f"art-{uuid.uuid4().hex[:8]}"

        artifact_file = self.base_path / artifact_id
        async with aiofiles.open(artifact_file, "wb") as f:
            await f.write(content)

        # If no parent provided, try to get the latest version of the same file
        if not parent_artifact_id:
            latest = await self.get_latest_artifact(goal_id, task_id, file_path)
            if latest:
                parent_artifact_id = latest.id

        # Determine initial status from lifecycle's first state
        lifecycle = await self._get_lifecycle(layer_id)
        states = lifecycle.get("states", [])
        if not states:
            initial_status = "draft"
        else:
            initial_status = states[0]

        artifact = HiveArtifact(
            id=artifact_id,
            goal_id=goal_id,
            task_id=task_id,
            file_path=file_path,
            content="",
            version=version,
            status=initial_status,
            created_at=datetime.utcnow(),
            parent_artifact_id=parent_artifact_id,
            layer_id=layer_id
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
            row = await result.fetchone()
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
            rows = await result.fetchall()
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
            row = await result.fetchone()
            if row:
                return HiveArtifact.model_validate(row[0])
        return None

    async def update_artifact_status(self, artifact_id: str, new_status: str) -> Optional[HiveArtifact]:
        artifact = await self.get_artifact(artifact_id)
        if not artifact:
            return None

        lifecycle = await self._get_lifecycle(artifact.layer_id)
        current_status = artifact.status
        transitions = lifecycle.get("transitions", {})

        allowed_next = transitions.get(current_status, [])
        if new_status not in allowed_next:
            raise ValueError(f"Invalid transition from {current_status} to {new_status}. Allowed: {allowed_next}")

        artifact.status = new_status
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
