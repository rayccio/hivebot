from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from pydantic import BaseModel
from ....services.task_manager import TaskManager
from ....services.planner import Planner
from ....services.agent_manager import AgentManager
from ....services.docker_service import DockerService
from ....services.redis_service import redis_service
from ....services.skill_manager import SkillManager
from ....services.skill_suggestion_manager import SkillSuggestionManager
from ....models.task import Task, TaskStatus
from ....services.hive_manager import HiveManager
from ....core.config import settings
import uuid
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hives/{hive_id}/plan", tags=["planning"])

class GoalRequest(BaseModel):
    goal: str
    auto_spawn: bool = True  # NEW: whether to spawn agents if none idle

async def get_task_manager():
    return TaskManager()

async def get_agent_manager():
    docker_service = DockerService()
    return AgentManager(docker_service)

async def get_skill_manager():
    return SkillManager()

async def get_suggestion_manager():
    return SkillSuggestionManager()

@router.post("")
async def create_plan(
    hive_id: str,
    goal_req: GoalRequest,
    task_manager: TaskManager = Depends(get_task_manager),
    agent_manager: AgentManager = Depends(get_agent_manager),
    skill_manager: SkillManager = Depends(get_skill_manager),
    suggestion_manager: SkillSuggestionManager = Depends(get_suggestion_manager)
):
    """Decompose a goal into a task graph and optionally execute immediately."""
    goal_text = goal_req.goal
    if not goal_text:
        raise HTTPException(status_code=400, detail="Goal text required")

    # Get hive context
    hive_manager = HiveManager(agent_manager)
    hive = await hive_manager.get_hive(hive_id)
    if not hive:
        raise HTTPException(status_code=404, detail="Hive not found")
    context = hive.global_user_md

    # Fetch all skills
    all_skills = await skill_manager.list_skills()
    skills_list = [{"id": s.id, "name": s.name, "description": s.description} for s in all_skills]

    planner = Planner()
    try:
        plan = await planner.plan(goal_text, context, skills_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Planning failed: {e}")

    # Build name->id mapping for skills
    skill_map = {s["name"].lower(): s["id"] for s in skills_list}

    # Convert plan tasks to Task objects
    tasks = []
    task_id_map = {}
    missing_skill_tasks = []

    for t in plan["tasks"]:
        real_id = f"t-{uuid.uuid4().hex[:8]}"
        task_id_map[t["id"]] = real_id

        req_skill_names = t.get("required_skills", [])
        req_skill_ids = []
        missing_names = []
        for name in req_skill_names:
            skill_id = skill_map.get(name.lower())
            if skill_id:
                req_skill_ids.append(skill_id)
            else:
                missing_names.append(name)

        task = Task(
            id=real_id,
            hive_id=hive_id,
            goal_id="",
            description=t["description"],
            status=TaskStatus.PENDING,
            created_at=datetime.utcnow(),
            required_skills=req_skill_ids,
            depends_on=t.get("depends_on", [])
        )
        tasks.append(task)

        if missing_names:
            missing_skill_tasks.append({
                "real_id": real_id,
                "task_dict": t,
                "missing_names": missing_names
            })

    # Build edges and update depends_on
    edges = []
    for t in plan["tasks"]:
        real_id = task_id_map[t["id"]]
        task_obj = next(task for task in tasks if task.id == real_id)
        real_deps = []
        for dep in t.get("depends_on", []):
            if dep in task_id_map:
                real_deps.append(task_id_map[dep])
                edges.append({"from": task_id_map[dep], "to": real_id})
        task_obj.depends_on = real_deps

    # Create graph
    graph = await task_manager.create_task_graph(hive_id, goal_text, tasks, edges)

    for task in tasks:
        task.goal_id = graph.goal_id

    # Create skill suggestions for missing skills
    for item in missing_skill_tasks:
        for name in item["missing_names"]:
            suggestion_in = SkillSuggestionCreate(
                skill_name=name,
                goal_id=graph.goal_id,
                goal_description=goal_text,
                task_id=item["real_id"],
                task_description=item["task_dict"]["description"],
                suggested_by="planner"
            )
            await suggestion_manager.create_suggestion(suggestion_in)

    # --- Immediate execution logic ---
    if settings.SCHEDULER_ENABLED:
        # Push tasks to Redis pending queue
        for task in tasks:
            score = task.created_at.timestamp() * 1000
            await redis_service.zadd("tasks:pending", task.id, score)
        logger.info(f"Pushed {len(tasks)} tasks to Redis pending queue")

        # If auto_spawn is enabled, check for idle agents and assign immediately
        if goal_req.auto_spawn:
            # Get idle agents from Redis
            idle_agents = await redis_service.smembers("agents:idle")
            if not idle_agents:
                # No idle agents – spawn new ones based on task requirements
                logger.info("No idle agents, spawning new agents for tasks")
                # Collect unique required skills across all tasks
                all_required_skill_ids = set()
                for task in tasks:
                    all_required_skill_ids.update(task.required_skills)
                # For each required skill, we might need multiple agents; for simplicity, spawn one agent per task
                # But we'll spawn a pool of agents with the combined skills
                # We'll use a simple heuristic: spawn one agent that has all required skills (if possible)
                # In a real system, you'd have a more sophisticated matching.
                # For now, we'll spawn one agent per task that has its required skills.
                spawned_agents = []
                for task in tasks:
                    # Find or create an agent with the required skills
                    agent = await agent_manager.spawn_agent_for_task(hive_id, task.required_skills)
                    if agent:
                        spawned_agents.append(agent.id)
                        # Mark as idle
                        await redis_service.sadd("agents:idle", agent.id)
                logger.info(f"Spawned {len(spawned_agents)} new agents")

    return {"goal_id": graph.goal_id, "tasks": tasks, "edges": edges}
