# backend/app/api/v1/endpoints/organization.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from ....models.types import Agent
from ....services.agent_manager import AgentManager
from ....services.docker_service import DockerService
from ....services.hive_manager import HiveManager
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/hives/{hive_id}/organization", tags=["organization"])

async def get_agent_manager():
    docker = DockerService()
    return AgentManager(docker)

async def get_hive_manager():
    docker = DockerService()
    agent_manager = AgentManager(docker)
    return HiveManager(agent_manager)

@router.get("/chart", response_model=List[Agent])
async def get_org_chart(
    hive_id: str,
    hive_manager: HiveManager = Depends(get_hive_manager)
):
    """Get all agents in the hive in a flat list (frontend will build tree)."""
    hive = await hive_manager.get_hive(hive_id)
    if not hive:
        raise HTTPException(status_code=404, detail="Hive not found")
    return hive.agents

@router.get("/agents/{agent_id}/team", response_model=List[Agent])
async def get_team(
    hive_id: str,
    agent_id: str,
    agent_manager: AgentManager = Depends(get_agent_manager),
    hive_manager: HiveManager = Depends(get_hive_manager)
):
    """Get all direct subordinates of an agent."""
    hive = await hive_manager.get_hive(hive_id)
    if not hive:
        raise HTTPException(status_code=404, detail="Hive not found")
    agent = await agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    # Optionally verify agent belongs to this hive
    if agent not in hive.agents:
        raise HTTPException(status_code=404, detail="Agent not in this hive")
    team = []
    for sub_id in agent.sub_agent_ids:
        sub = await agent_manager.get_agent(sub_id)
        if sub:
            team.append(sub)
    return team

@router.get("/agents/{agent_id}/managers", response_model=List[Agent])
async def get_managers(
    hive_id: str,
    agent_id: str,
    agent_manager: AgentManager = Depends(get_agent_manager),
    hive_manager: HiveManager = Depends(get_hive_manager)
):
    """Get the chain of command from this agent up to the top."""
    hive = await hive_manager.get_hive(hive_id)
    if not hive:
        raise HTTPException(status_code=404, detail="Hive not found")
    agent = await agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent not in hive.agents:
        raise HTTPException(status_code=404, detail="Agent not in this hive")
    managers = []
    current = agent
    while current.parent_id:
        parent = await agent_manager.get_agent(current.parent_id)
        if parent:
            managers.append(parent)
            current = parent
        else:
            break
    return managers
