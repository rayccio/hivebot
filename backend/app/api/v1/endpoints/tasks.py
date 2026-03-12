from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional, Any
from pydantic import BaseModel
from ....services.task_manager import TaskManager
from ....services.agent_manager import AgentManager
from ....services.docker_service import DockerService
from ....services.redis_service import redis_service
from ....models.task import Task, TaskStatus
from datetime import datetime
import json

router = APIRouter(prefix="/hives/{hive_id}/tasks", tags=["tasks"])

class CompleteTaskRequest(BaseModel):
    output: Any

async def get_task_manager():
    return TaskManager()

async def get_agent_manager():
    docker_service = DockerService()
    return AgentManager(docker_service)

@router.get("", response_model=List[Task])
async def list_tasks(
    hive_id: str,
    task_manager: TaskManager = Depends(get_task_manager)
):
    return await task_manager.list_tasks_for_hive(hive_id)

@router.get("/{task_id}", response_model=Task)
async def get_task(
    hive_id: str,
    task_id: str,
    task_manager: TaskManager = Depends(get_task_manager)
):
    task = await task_manager.get_task(task_id)
    if not task or task.hive_id != hive_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.post("/{task_id}/assign")
async def assign_task(
    hive_id: str,
    task_id: str,
    agent_id: str,
    task_manager: TaskManager = Depends(get_task_manager),
    agent_manager: AgentManager = Depends(get_agent_manager)
):
    task = await task_manager.get_task(task_id)
    if not task or task.hive_id != hive_id:
        raise HTTPException(status_code=404, detail="Task not found")
    agent = await agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    success = await task_manager.assign_task(task_id, agent_id)
    if not success:
        raise HTTPException(status_code=400, detail="Assignment failed")

    message = {
        "type": "task_assign",
        "task_id": task_id,
        "description": task.description,
        "goal_id": task.goal_id,
        "input_data": task.input_data
    }
    await redis_service.publish(f"agent:{agent_id}", message)

    return {"status": "assigned"}

@router.post("/{task_id}/complete")
async def complete_task(
    hive_id: str,
    task_id: str,
    payload: CompleteTaskRequest,
    task_manager: TaskManager = Depends(get_task_manager)
):
    task = await task_manager.get_task(task_id)
    if not task or task.hive_id != hive_id:
        raise HTTPException(status_code=404, detail="Task not found")

    task = await task_manager.update_task(
        task_id,
        status=TaskStatus.COMPLETED,
        output_data=payload.output,
        completed_at=datetime.utcnow()
    )
    return task
