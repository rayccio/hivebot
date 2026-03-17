# backend/app/api/v1/endpoints/goals.py
from fastapi import APIRouter, HTTPException, Depends, Body
from typing import List
from ....services.goal_engine import GoalEngine
from ....services.planner import Planner
from ....services.hive_manager import HiveManager
from ....services.agent_manager import AgentManager
from ....services.docker_service import DockerService
from ....models.types import HiveGoal, HiveTask
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

@router.post("", response_model=GoalResponse)
async def create_goal(
    hive_id: str,
    request: GoalCreateRequest,
    goal_engine: GoalEngine = Depends(get_goal_engine),
    planner: Planner = Depends(get_planner),
    hive_manager: HiveManager = Depends(get_hive_manager)
):
    # Verify hive exists
    hive = await hive_manager.get_hive(hive_id)
    if not hive:
        raise HTTPException(status_code=404, detail="Hive not found")

    # Create goal
    goal = await goal_engine.create_goal(
        hive_id=hive_id,
        description=request.description,
        constraints=request.constraints,
        success_criteria=request.success_criteria
    )

    # Fetch skills for planner (optional)
    from ....services.skill_manager import SkillManager
    skill_manager = SkillManager()
    all_skills = await skill_manager.list_skills()
    skills_list = [{"id": s.id, "name": s.name, "description": s.description} for s in all_skills]

    # Plan tasks
    try:
        tasks = await planner.plan(
            goal_id=goal.id,
            goal_text=request.description,
            hive_context=hive.global_user_md,
            skills=skills_list
        )
    except Exception as e:
        logger.error(f"Planning failed for goal {goal.id}: {e}")
        # Still return goal, but with empty tasks? Better to fail.
        raise HTTPException(status_code=500, detail=f"Planning failed: {str(e)}")

    # Update goal status to PLANNING (or directly to EXECUTING?)
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

# Optional: endpoint to get tasks for a goal
@router.get("/{goal_id}/tasks", response_model=List[HiveTask])
async def get_goal_tasks(
    hive_id: str,
    goal_id: str,
    db = Depends(...)  # we'll use raw SQL for simplicity
):
    # Verify goal belongs to hive (we'll do a quick check)
    goal_engine = GoalEngine()
    goal = await goal_engine.get_goal(goal_id)
    if not goal or goal.hive_id != hive_id:
        raise HTTPException(status_code=404, detail="Goal not found")

    from sqlalchemy import text
    from ....core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("SELECT data FROM tasks WHERE data->>'goal_id' = :goal_id"),
            {"goal_id": goal_id}
        )
        rows = result.fetchall()
        return [HiveTask.model_validate_json(r[0]) for r in rows]
