from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from ....services.execution_logger import ExecutionLogger
from ....services.goal_engine import GoalEngine
from ....models.types import ExecutionLog, ExecutionLogLevel
from ....services.hive_manager import HiveManager
from ....services.agent_manager import AgentManager
from ....services.docker_service import DockerService
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/hives/{hive_id}/goals/{goal_id}/logs", tags=["logs"])

async def get_execution_logger():
    return ExecutionLogger()

async def get_goal_engine():
    return GoalEngine()

async def get_hive_manager():
    docker = DockerService()
    agent_manager = AgentManager(docker)
    return HiveManager(agent_manager)

@router.get("", response_model=List[ExecutionLog])
async def get_execution_logs(
    hive_id: str,
    goal_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    level: Optional[ExecutionLogLevel] = Query(None),
    logger_instance: ExecutionLogger = Depends(get_execution_logger),
    goal_engine: GoalEngine = Depends(get_goal_engine),
    hive_manager: HiveManager = Depends(get_hive_manager)
):
    """Retrieve execution logs for a specific goal."""
    # Verify hive exists and goal belongs to hive
    hive = await hive_manager.get_hive(hive_id)
    if not hive:
        raise HTTPException(status_code=404, detail="Hive not found")
    goal = await goal_engine.get_goal(goal_id)
    if not goal or goal.hive_id != hive_id:
        raise HTTPException(status_code=404, detail="Goal not found")

    logs = await logger_instance.get_logs_for_goal(goal_id, limit=limit, offset=offset, level=level)
    return logs

@router.get("/tasks/{task_id}", response_model=List[ExecutionLog])
async def get_task_execution_logs(
    hive_id: str,
    goal_id: str,
    task_id: str,
    limit: int = Query(50, ge=1, le=200),
    logger_instance: ExecutionLogger = Depends(get_execution_logger),
    goal_engine: GoalEngine = Depends(get_goal_engine),
    hive_manager: HiveManager = Depends(get_hive_manager)
):
    """Retrieve execution logs for a specific task within a goal."""
    # Verify goal exists and belongs to hive
    hive = await hive_manager.get_hive(hive_id)
    if not hive:
        raise HTTPException(status_code=404, detail="Hive not found")
    goal = await goal_engine.get_goal(goal_id)
    if not goal or goal.hive_id != hive_id:
        raise HTTPException(status_code=404, detail="Goal not found")

    logs = await logger_instance.get_logs_for_task(goal_id, task_id, limit=limit)
    return logs
