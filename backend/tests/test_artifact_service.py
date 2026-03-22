import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.artifact_service import ArtifactService
from app.models.types import HiveArtifact
from datetime import datetime
import json
import os
from pathlib import Path

@pytest.mark.asyncio
async def test_create_artifact(tmp_path):
    service = ArtifactService()
    service.base_path = Path(tmp_path) / "artifacts"
    service.base_path.mkdir(parents=True, exist_ok=True)

    with patch('app.services.artifact_service.AsyncSessionLocal') as mock_session:
        mock_conn = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_conn
        service._get_next_version = AsyncMock(return_value=1)

        content = b"test content"
        artifact = await service.create_artifact(
            goal_id="g-test",
            task_id="t-test",
            file_path="test.txt",
            content=content,
            status="draft"
        )

        assert artifact.id.startswith("art-")
        assert artifact.goal_id == "g-test"
        assert artifact.task_id == "t-test"
        assert artifact.file_path == "test.txt"
        assert artifact.version == 1
        assert artifact.status == "draft"
        artifact_file = service.base_path / artifact.id
        assert artifact_file.exists()
        assert artifact_file.read_bytes() == content
        mock_conn.execute.assert_awaited_once()
        mock_conn.commit.assert_awaited_once()

@pytest.mark.asyncio
async def test_get_artifact():
    service = ArtifactService()
    mock_data = {
        "id": "art-123",
        "goal_id": "g-test",
        "task_id": "t-test",
        "file_path": "test.txt",
        "content": "",
        "version": 1,
        "status": "draft",
        "created_at": datetime.utcnow().isoformat()
    }
    with patch('app.services.artifact_service.AsyncSessionLocal') as mock_session:
        mock_conn = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_conn

        # Use AsyncMock for the result object
        mock_result = AsyncMock()
        mock_result.fetchone = AsyncMock(return_value=(mock_data,))
        mock_conn.execute.return_value = mock_result

        artifact = await service.get_artifact("art-123")
        assert artifact is not None
        assert artifact.id == "art-123"

@pytest.mark.asyncio
async def test_list_artifacts():
    service = ArtifactService()
    mock_data = [{
        "id": "art-123",
        "goal_id": "g-test",
        "task_id": "t-test",
        "file_path": "test.txt",
        "content": "",
        "version": 1,
        "status": "draft",
        "created_at": datetime.utcnow().isoformat()
    }]
    with patch('app.services.artifact_service.AsyncSessionLocal') as mock_session:
        mock_conn = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_conn

        # Use AsyncMock for the result object
        mock_result = AsyncMock()
        mock_result.fetchall = AsyncMock(return_value=[(mock_data[0],)])
        mock_conn.execute.return_value = mock_result

        artifacts = await service.list_artifacts("g-test")
        assert len(artifacts) == 1
        assert artifacts[0].id == "art-123"

@pytest.mark.asyncio
async def test_delete_artifact():
    service = ArtifactService()
    with patch('app.services.artifact_service.ArtifactService.get_artifact') as mock_get, \
         patch('app.services.artifact_service.AsyncSessionLocal') as mock_session, \
         patch('pathlib.Path.exists', return_value=True), \
         patch('pathlib.Path.unlink') as mock_unlink:

        mock_artifact = MagicMock(spec=HiveArtifact)
        mock_artifact.id = "art-123"
        mock_get.return_value = mock_artifact

        mock_conn = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_conn
        mock_conn.execute = AsyncMock()

        result = await service.delete_artifact("art-123")
        assert result is True
        mock_unlink.assert_called_once()
        mock_conn.execute.assert_awaited_once()
        mock_conn.commit.assert_awaited_once()
