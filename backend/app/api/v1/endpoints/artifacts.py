from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form, Query
from fastapi.responses import FileResponse
from typing import List, Optional
from ....services.artifact_service import ArtifactService
from ....services.hive_manager import HiveManager
from ....services.agent_manager import AgentManager
from ....services.docker_service import DockerService
from ....models.types import HiveArtifact
import logging
import os
import tempfile

logger = logging.getLogger(__name__)

# Router with prefix that includes the hive_id and goal_id path parameters
router = APIRouter(prefix="/hives/{hive_id}/goals/{goal_id}/artifacts", tags=["artifacts"])

async def get_artifact_service():
    return ArtifactService()

async def get_hive_manager():
    docker = DockerService()
    agent_manager = AgentManager(docker)
    return HiveManager(agent_manager)

@router.get("", response_model=List[HiveArtifact])
async def list_artifacts(
    hive_id: str,
    goal_id: str,
    task_id: Optional[str] = Query(None, description="Filter by task ID"),
    artifact_service: ArtifactService = Depends(get_artifact_service),
    hive_manager: HiveManager = Depends(get_hive_manager)
):
    hive = await hive_manager.get_hive(hive_id)
    if not hive:
        raise HTTPException(status_code=404, detail="Hive not found")
    artifacts = await artifact_service.list_artifacts(goal_id, task_id)
    return artifacts

@router.post("", response_model=HiveArtifact, status_code=201)
async def create_artifact(
    hive_id: str,
    goal_id: str,
    task_id: str = Form(...),
    file_path: str = Form(...),
    file: UploadFile = File(...),
    status: str = Form("draft"),
    artifact_service: ArtifactService = Depends(get_artifact_service),
    hive_manager: HiveManager = Depends(get_hive_manager)
):
    hive = await hive_manager.get_hive(hive_id)
    if not hive:
        raise HTTPException(status_code=404, detail="Hive not found")
    content = await file.read()
    try:
        artifact = await artifact_service.create_artifact(
            goal_id=goal_id,
            task_id=task_id,
            file_path=file_path,
            content=content,
            status=status
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return artifact

@router.get("/{artifact_id}", response_class=FileResponse)
async def download_artifact(
    hive_id: str,
    goal_id: str,
    artifact_id: str,
    artifact_service: ArtifactService = Depends(get_artifact_service),
    hive_manager: HiveManager = Depends(get_hive_manager)
):
    hive = await hive_manager.get_hive(hive_id)
    if not hive:
        raise HTTPException(status_code=404, detail="Hive not found")
    artifact = await artifact_service.get_artifact(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    if artifact.goal_id != goal_id:
        raise HTTPException(status_code=404, detail="Artifact not found in this goal")

    content = await artifact_service.read_artifact_content(artifact_id)
    if content is None:
        raise HTTPException(status_code=404, detail="Artifact file not found")

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    from starlette.background import BackgroundTask
    def cleanup():
        os.unlink(tmp_path)

    return FileResponse(
        path=tmp_path,
        filename=os.path.basename(artifact.file_path),
        media_type="application/octet-stream",
        background=BackgroundTask(cleanup)
    )

@router.patch("/{artifact_id}/status", response_model=HiveArtifact)
async def update_artifact_status(
    hive_id: str,
    goal_id: str,
    artifact_id: str,
    status: str = Form(...),
    artifact_service: ArtifactService = Depends(get_artifact_service),
    hive_manager: HiveManager = Depends(get_hive_manager)
):
    hive = await hive_manager.get_hive(hive_id)
    if not hive:
        raise HTTPException(status_code=404, detail="Hive not found")
    artifact = await artifact_service.update_artifact_status(artifact_id, status)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    if artifact.goal_id != goal_id:
        raise HTTPException(status_code=404, detail="Artifact not found in this goal")
    return artifact

@router.delete("/{artifact_id}", status_code=204)
async def delete_artifact(
    hive_id: str,
    goal_id: str,
    artifact_id: str,
    artifact_service: ArtifactService = Depends(get_artifact_service),
    hive_manager: HiveManager = Depends(get_hive_manager)
):
    hive = await hive_manager.get_hive(hive_id)
    if not hive:
        raise HTTPException(status_code=404, detail="Hive not found")
    artifact = await artifact_service.get_artifact(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    if artifact.goal_id != goal_id:
        raise HTTPException(status_code=404, detail="Artifact not found in this goal")
    deleted = await artifact_service.delete_artifact(artifact_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Artifact not found")
