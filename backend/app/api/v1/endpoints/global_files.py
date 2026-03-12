import os
import shutil
import uuid
from datetime import datetime
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import FileResponse
from ....core.config import settings
from ....models.types import FileEntry
from ....services.embedding_client import trigger_file_embedding
from ....services.vector_service import vector_service

router = APIRouter(tags=["global-files"])

GLOBAL_FILES_DIR = settings.GLOBAL_FILES_DIR  # still called GLOBAL_FILES_DIR, but will be system‑wide

def validate_filename(filename: str) -> str:
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return filename

@router.post("")
async def upload_global_file(file: UploadFile = File(...)):
    """Upload a global file accessible to all agents."""
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size: {settings.MAX_UPLOAD_SIZE} bytes"
        )
    
    safe_filename = validate_filename(file.filename)
    file_path = GLOBAL_FILES_DIR / safe_filename
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

    # --- Trigger embedding for text files, using hive_id "global" ---
    if file_entry.type in ['md', 'txt', 'json']:
        await trigger_file_embedding(str(file_path), "global", file_entry.id)

    return file_entry

@router.get("", response_model=List[FileEntry])
async def list_global_files():
    files = []
    for filename in os.listdir(GLOBAL_FILES_DIR):
        file_path = GLOBAL_FILES_DIR / filename
        if file_path.is_file():
            files.append(FileEntry(
                id=filename,
                name=filename,
                type=filename.split('.')[-1] if '.' in filename else "bin",
                content="",
                size=os.path.getsize(file_path),
                uploaded_at=datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
            ))
    return files

@router.get("/{filename}")
async def download_global_file(filename: str):
    safe_filename = validate_filename(filename)
    file_path = GLOBAL_FILES_DIR / safe_filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=safe_filename)

@router.delete("/{filename}")
async def delete_global_file(filename: str):
    safe_filename = validate_filename(filename)
    file_path = GLOBAL_FILES_DIR / safe_filename
    if file_path.exists():
        file_path.unlink()
        # Delete vectors – we need to know file_id; we used filename as id
        await vector_service.delete_by_file(filename)
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="File not found")
