import os
import shutil
import uuid
from datetime import datetime
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, status
from fastapi.responses import FileResponse
from ....services.agent_manager import AgentManager
from ....services.docker_service import DockerService
from ....services.embedding_client import trigger_file_embedding
from ....services.vector_service import vector_service
from ....models.types import FileEntry, AgentUpdate
from ....core.config import settings

router = APIRouter()

async def get_agent_manager():
    docker_service = DockerService()
    return AgentManager(docker_service)

def validate_filename(filename: str) -> str:
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return filename

@router.post("/agents/{agent_id}/files")
async def upload_agent_file(
    agent_id: str,
    file: UploadFile = File(...),
    manager: AgentManager = Depends(get_agent_manager)
):
    """Upload a file to the agent's files directory."""
    agent = await manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Validate file size
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size: {settings.MAX_UPLOAD_SIZE} bytes"
        )
    
    safe_filename = validate_filename(file.filename)
    
    agent_dir = settings.AGENTS_DIR / agent_id
    files_dir = agent_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = files_dir / safe_filename
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
    
    file_entry = FileEntry(
        id=str(uuid.uuid4()),
        name=safe_filename,
        type=safe_filename.split('.')[-1] if '.' in safe_filename else "bin",
        content="",
        size=os.path.getsize(file_path),
        uploaded_at=datetime.utcnow().isoformat()
    )
    
    agent.local_files.append(file_entry)
    update = AgentUpdate(local_files=agent.local_files)
    await manager.update_agent(agent_id, update)

    # --- Trigger embedding for text files ---
    if file_entry.type in ['md', 'txt', 'json']:
        await trigger_file_embedding(str(file_path), agent.hive_id, file_entry.id, agent_id)

    return file_entry

@router.get("/agents/{agent_id}/files", response_model=List[FileEntry])
async def list_agent_files(
    agent_id: str,
    manager: AgentManager = Depends(get_agent_manager)
):
    agent = await manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.local_files

@router.get("/agents/{agent_id}/files/{file_id}")
async def download_agent_file(
    agent_id: str,
    file_id: str,
    manager: AgentManager = Depends(get_agent_manager)
):
    agent = await manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    file_entry = next((f for f in agent.local_files if f.id == file_id), None)
    if not file_entry:
        raise HTTPException(status_code=404, detail="File not found")
    
    agent_dir = settings.AGENTS_DIR / agent_id
    file_path = agent_dir / "files" / file_entry.name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    return FileResponse(file_path, filename=file_entry.name)

@router.delete("/agents/{agent_id}/files/{file_id}")
async def delete_agent_file(
    agent_id: str,
    file_id: str,
    manager: AgentManager = Depends(get_agent_manager)
):
    agent = await manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    file_entry = next((f for f in agent.local_files if f.id == file_id), None)
    if not file_entry:
        raise HTTPException(status_code=404, detail="File not found")
    
    agent_dir = settings.AGENTS_DIR / agent_id
    file_path = agent_dir / "files" / file_entry.name
    if file_path.exists():
        file_path.unlink()
    
    agent.local_files = [f for f in agent.local_files if f.id != file_id]
    update = AgentUpdate(local_files=agent.local_files)
    await manager.update_agent(agent_id, update)

    # --- Delete vectors associated with this file ---
    await vector_service.delete_by_file(file_id)

    return {"status": "deleted"}
