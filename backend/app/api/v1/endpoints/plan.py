from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from pydantic import BaseModel
from ....services.task_manager import TaskManager
from ....services.planner import Planner
from ....services.agent_manager import AgentManager
from ....services.docker_service import DockerService
from ....models.task import Task, TaskStatus
from ....services.hive_manager import HiveManager
import uuid
from datetime import datetime

router = APIRouter(prefix="/hives/{hive_id}/plan", tags=["planning"])

class GoalRequest(BaseModel):
    goal: str

async def get_task_manager():
    return TaskManager()

async def get_agent_manager():
    docker_service = DockerService()
    return AgentManager(docker_service)

@router.post("")
async def create_plan(
    hive_id: str,
    goal_req: GoalRequest,
    task_manager: TaskManager = Depends(get_task_manager),
    agent_manager: AgentManager = Depends(get_agent_manager)
):
    """Decompose a goal into a task graph and store it."""
    goal_text = goal_req.goal
    if not goal_text:
        raise HTTPException(status_code=400, detail="Goal text required")

    # Get hive context (global user md)
    hive_manager = HiveManager(agent_manager)
    hive = await hive_manager.get_hive(hive_id)
    if not hive:
        raise HTTPException(status_code=404, detail="Hive not found")
    context = hive.global_user_md

    planner = Planner()
    try:
        plan = await planner.plan(goal_text, context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Planning failed: {e}")

    # Convert plan tasks to actual Task objects with UUIDs
    tasks = []
    task_id_map = {}  # map temp ids to real ids
    for t in plan["tasks"]:
        real_id = f"t-{uuid.uuid4().hex[:8]}"
        task_id_map[t["id"]] = real_id
        task = Task(
            id=real_id,
            hive_id=hive_id,
            goal_id="",  # will set after graph created
            description=t["description"],
            status=TaskStatus.PENDING,
            created_at=datetime.utcnow()
        )
        tasks.append(task)

    # Build edges using real IDs
    edges = []
    for t in plan["tasks"]:
        for dep in t.get("depends_on", []):
            if dep in task_id_map and t["id"] in task_id_map:
                edges.append({
                    "from": task_id_map[dep],
                    "to": task_id_map[t["id"]]
                })

    # Create graph (goal_id will be generated)
    graph = await task_manager.create_task_graph(hive_id, goal_text, tasks, edges)

    # Update each task with the goal_id
    for task in tasks:
        task.goal_id = graph.goal_id
    task_manager._save()  # quick save

    return {"goal_id": graph.goal_id, "tasks": tasks, "edges": edges}
