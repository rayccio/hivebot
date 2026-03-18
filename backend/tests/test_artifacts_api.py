import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app as fastapi_app
from app.models.types import HiveArtifact, Hive
from datetime import datetime
import json

# Import the dependency functions to override
from app.api.v1.endpoints.artifacts import get_artifact_service, get_hive_manager

@pytest.mark.asyncio
async def test_list_artifacts_api(client: AsyncClient):
    mock_service = AsyncMock()
    mock_artifact = HiveArtifact(
        id="art-123",
        goal_id="g-test",
        task_id="t-test",
        file_path="test.txt",
        content="",
        version=1,
        status="draft",
        created_at=datetime.utcnow()
    )
    mock_service.list_artifacts.return_value = [mock_artifact]

    mock_hive_manager = AsyncMock()
    mock_hive = MagicMock(spec=Hive)
    mock_hive.id = "h-test"
    mock_hive_manager.get_hive = AsyncMock(return_value=mock_hive)

    # Override dependencies
    fastapi_app.dependency_overrides[get_artifact_service] = lambda: mock_service
    fastapi_app.dependency_overrides[get_hive_manager] = lambda: mock_hive_manager

    response = await client.get("/api/v1/hives/h-test/goals/g-test/artifacts")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "art-123"

    # Clean up
    fastapi_app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_create_artifact_api(client: AsyncClient):
    mock_service = AsyncMock()
    mock_artifact = HiveArtifact(
        id="art-123",
        goal_id="g-test",
        task_id="t-test",
        file_path="test.txt",
        content="",
        version=1,
        status="draft",
        created_at=datetime.utcnow()
    )
    mock_service.create_artifact.return_value = mock_artifact

    mock_hive_manager = AsyncMock()
    mock_hive = MagicMock(spec=Hive)
    mock_hive.id = "h-test"
    mock_hive_manager.get_hive = AsyncMock(return_value=mock_hive)

    fastapi_app.dependency_overrides[get_artifact_service] = lambda: mock_service
    fastapi_app.dependency_overrides[get_hive_manager] = lambda: mock_hive_manager

    files = {'file': ('test.txt', b'hello world', 'text/plain')}
    data = {'task_id': 't-test', 'file_path': 'test.txt', 'status': 'draft'}
    response = await client.post(
        "/api/v1/hives/h-test/goals/g-test/artifacts",
        data=data,
        files=files
    )
    assert response.status_code == 201
    assert response.json()["id"] == "art-123"

    fastapi_app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_download_artifact_api(client: AsyncClient):
    mock_service = AsyncMock()
    mock_artifact = HiveArtifact(
        id="art-123",
        goal_id="g-test",
        task_id="t-test",
        file_path="test.txt",
        content="",
        version=1,
        status="draft",
        created_at=datetime.utcnow()
    )
    mock_service.get_artifact.return_value = mock_artifact
    mock_service.read_artifact_content.return_value = b"hello world"

    mock_hive_manager = AsyncMock()
    mock_hive = MagicMock(spec=Hive)
    mock_hive.id = "h-test"
    mock_hive_manager.get_hive = AsyncMock(return_value=mock_hive)

    fastapi_app.dependency_overrides[get_artifact_service] = lambda: mock_service
    fastapi_app.dependency_overrides[get_hive_manager] = lambda: mock_hive_manager

    with patch('app.api.v1.endpoints.artifacts.tempfile.NamedTemporaryFile') as mock_temp, \
         patch('os.unlink'):
        mock_temp.return_value.__enter__.return_value.name = "/tmp/xyz"
        response = await client.get("/api/v1/hives/h-test/goals/g-test/artifacts/art-123")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/octet-stream"
        assert response.headers["content-disposition"] == 'attachment; filename="test.txt"'

    fastapi_app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_update_artifact_status_api(client: AsyncClient):
    mock_service = AsyncMock()
    mock_artifact = HiveArtifact(
        id="art-123",
        goal_id="g-test",
        task_id="t-test",
        file_path="test.txt",
        content="",
        version=1,
        status="tested",
        created_at=datetime.utcnow()
    )
    mock_service.update_artifact_status.return_value = mock_artifact

    mock_hive_manager = AsyncMock()
    mock_hive = MagicMock(spec=Hive)
    mock_hive.id = "h-test"
    mock_hive_manager.get_hive = AsyncMock(return_value=mock_hive)

    fastapi_app.dependency_overrides[get_artifact_service] = lambda: mock_service
    fastapi_app.dependency_overrides[get_hive_manager] = lambda: mock_hive_manager

    response = await client.patch(
        "/api/v1/hives/h-test/goals/g-test/artifacts/art-123/status",
        data={"status": "tested"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "tested"

    fastapi_app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_delete_artifact_api(client: AsyncClient):
    mock_service = AsyncMock()
    mock_service.get_artifact.return_value = HiveArtifact(
        id="art-123",
        goal_id="g-test",
        task_id="t-test",
        file_path="test.txt",
        content="",
        version=1,
        status="draft",
        created_at=datetime.utcnow()
    )
    mock_service.delete_artifact.return_value = True

    mock_hive_manager = AsyncMock()
    mock_hive = MagicMock(spec=Hive)
    mock_hive.id = "h-test"
    mock_hive_manager.get_hive = AsyncMock(return_value=mock_hive)

    fastapi_app.dependency_overrides[get_artifact_service] = lambda: mock_service
    fastapi_app.dependency_overrides[get_hive_manager] = lambda: mock_hive_manager

    response = await client.delete("/api/v1/hives/h-test/goals/g-test/artifacts/art-123")
    assert response.status_code == 204

    fastapi_app.dependency_overrides.clear()
