from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from ....services.skill_manager import SkillManager
from ....services.agent_manager import AgentManager
from ....services.docker_service import DockerService
from ....models.skill import AgentSkill

router = APIRouter(prefix="/agents/{agent_id}/skills", tags=["agent-skills"])

class InstallSkillRequest(BaseModel):
    version_id: Optional[str] = None
    config: Dict[str, Any] = {}

class UpdateSkillConfigRequest(BaseModel):
    config: Dict[str, Any]

async def get_skill_manager():
    return SkillManager()

async def get_agent_manager():
    docker_service = DockerService()
    return AgentManager(docker_service)

@router.get("", response_model=List[AgentSkill])
async def list_agent_skills(
    agent_id: str,
    skill_manager: SkillManager = Depends(get_skill_manager),
    agent_manager: AgentManager = Depends(get_agent_manager)
):
    agent = await agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return await skill_manager.get_agent_skills(agent_id)

@router.post("/{skill_id}/install", response_model=AgentSkill)
async def install_skill(
    agent_id: str,
    skill_id: str,
    request: InstallSkillRequest = None,
    skill_manager: SkillManager = Depends(get_skill_manager),
    agent_manager: AgentManager = Depends(get_agent_manager)
):
    agent = await agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    config = request.config if request else {}
    version_id = request.version_id if request else None
    try:
        agent_skill = await skill_manager.install_skill(agent_id, skill_id, version_id, config)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return agent_skill

@router.post("/{skill_id}/uninstall", status_code=204)
async def uninstall_skill(
    agent_id: str,
    skill_id: str,
    skill_manager: SkillManager = Depends(get_skill_manager),
    agent_manager: AgentManager = Depends(get_agent_manager)
):
    agent = await agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    deleted = await skill_manager.uninstall_skill(agent_id, skill_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Skill not installed on this agent")

@router.patch("/{skill_id}/config", response_model=AgentSkill)
async def update_skill_config(
    agent_id: str,
    skill_id: str,
    request: UpdateSkillConfigRequest,
    skill_manager: SkillManager = Depends(get_skill_manager),
    agent_manager: AgentManager = Depends(get_agent_manager)
):
    agent = await agent_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent_skill = await skill_manager.update_agent_skill_config(agent_id, skill_id, request.config)
    if not agent_skill:
        raise HTTPException(status_code=404, detail="Skill not installed on this agent")
    return agent_skill
