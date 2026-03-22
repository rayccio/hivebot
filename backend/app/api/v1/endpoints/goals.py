# backend/app/api/v1/endpoints/goals.py
from fastapi import APIRouter, HTTPException, Depends, Body
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from ....services.goal_engine import GoalEngine
from ....services.planner import Planner
from ....services.hive_manager import HiveManager
from ....services.agent_manager import AgentManager
from ....services.docker_service import DockerService
from ....services.project_manager import ProjectManager
from ....core.database import get_db
from ....models.types import HiveGoal, HiveTask, HiveGoalStatus
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/hives/{hive_id}/goals", tags=["goals"])

class GoalCreateRequest(BaseModel):
    description: str
    constraints: dict = {}
    success_criteria: List[str] = []

class GoalResponse(BaseModel):
    goal: HiveGoal
    tasks: List[HiveTask]

async def get_goal_engine():
    return GoalEngine()

async def get_planner():
    return Planner()

async def get_hive_manager():
    docker = DockerService()
    agent_manager = AgentManager(docker)
    return HiveManager(agent_manager)

async def get_project_manager():
    return ProjectManager()

@router.post("", response_model=GoalResponse)
async def create_goal(
    hive_id: str,
    request: GoalCreateRequest,
    goal_engine: GoalEngine = Depends(get_goal_engine),
    planner: Planner = Depends(get_planner),
    hive_manager: HiveManager = Depends(get_hive_manager),
    project_manager: ProjectManager = Depends(get_project_manager)
):
    hive = await hive_manager.get_hive(hive_id)
    if not hive:
        raise HTTPException(status_code=404, detail="Hive not found")

    goal = await goal_engine.create_goal(
        hive_id=hive_id,
        description=request.description,
        constraints=request.constraints,
        success_criteria=request.success_criteria
    )

    # Create a project for this goal
    project = await project_manager.create_project(
        hive_id=hive_id,
        name=f"Project for goal {goal.id}",
        description=goal.description,
        goal=goal.description,
        root_goal_id=goal.id
    )

    from ....services.skill_manager import SkillManager
    skill_manager = SkillManager()
    all_skills = await skill_manager.list_skills()
    skills_list = [{"id": s.id, "name": s.name, "description": s.description} for s in all_skills]

    try:
        tasks = await planner.plan(
            goal_id=goal.id,
            hive_id=hive_id,
            goal_text=request.description,
            hive_context=hive.global_user_md,
            skills=skills_list,
            project_id=project.id   # <-- pass project_id
        )
    except Exception as e:
        logger.error(f"Planning failed for goal {goal.id}: {e}")
        raise HTTPException(status_code=500, detail=f"Planning failed: {str(e)}")

    await goal_engine.update_goal_status(goal.id, HiveGoalStatus.PLANNING)

    return GoalResponse(goal=goal, tasks=tasks)

@router.get("", response_model=List[HiveGoal])
async def list_goals(
    hive_id: str,
    goal_engine: GoalEngine = Depends(get_goal_engine)
):
    return await goal_engine.list_goals_for_hive(hive_id)

@router.get("/{goal_id}", response_model=HiveGoal)
async def get_goal(
    hive_id: str,
    goal_id: str,
    goal_engine: GoalEngine = Depends(get_goal_engine)
):
    goal = await goal_engine.get_goal(goal_id)
    if not goal or goal.hive_id != hive_id:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal

@router.get("/{goal_id}/tasks", response_model=List[HiveTask])
async def get_goal_tasks(
    hive_id: str,
    goal_id: str,
    db: AsyncSession = Depends(get_db)
):
    goal_engine = GoalEngine()
    goal = await goal_engine.get_goal(goal_id)
    if not goal or goal.hive_id != hive_id:
        raise HTTPException(status_code=404, detail="Goal not found")

    result = await db.execute(
        text("SELECT data FROM tasks WHERE data->>'goal_id' = :goal_id"),
        {"goal_id": goal_id}
    )
    rows = result.fetchall()
    return [HiveTask.model_validate(r[0]) for r in rows]

@router.post("/{goal_id}/cancel", response_model=HiveGoal)
async def cancel_goal(
    hive_id: str,
    goal_id: str,
    goal_engine: GoalEngine = Depends(get_goal_engine),
    hive_manager: HiveManager = Depends(get_hive_manager)
):
    hive = await hive_manager.get_hive(hive_id)
    if not hive:
        raise HTTPException(status_code=404, detail="Hive not found")
    goal = await goal_engine.get_goal(goal_id)
    if not goal or goal.hive_id != hive_id:
        raise HTTPException(status_code=404, detail="Goal not found")
    cancelled = await goal_engine.cancel_goal(goal_id)
    return cancelled
