from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import Optional
from ....services.execution_logger import ExecutionLogger
from ....models.types import ExecutionLogLevel
from ....core.config import settings
import secrets
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/logs", tags=["internal-logs"])

class ExecutionLogCreate(BaseModel):
    goal_id: str
    level: str
    message: str
    task_id: Optional[str] = None
    agent_id: Optional[str] = None
    iteration: Optional[int] = None

async def verify_internal_token(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    scheme, token = authorization.split()
    if scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization scheme")
    expected = settings.secrets.get("INTERNAL_API_KEY")
    if not expected:
        raise HTTPException(status_code=500, detail="Internal API key not configured")
    if not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail="Invalid token")
    return token

@router.post("/execution", status_code=201)
async def create_execution_log(
    log_data: ExecutionLogCreate,
    token: str = Depends(verify_internal_token)
):
    """Internal endpoint for workers to submit execution logs."""
    try:
        level = ExecutionLogLevel(log_data.level)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid log level: {log_data.level}")

    logger_instance = ExecutionLogger()
    await logger_instance.log(
        goal_id=log_data.goal_id,
        level=level,
        message=log_data.message,
        task_id=log_data.task_id,
        agent_id=log_data.agent_id,
        iteration=log_data.iteration
    )
    return {"status": "logged"}
