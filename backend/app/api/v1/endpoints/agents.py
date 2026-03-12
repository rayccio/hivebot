from fastapi import APIRouter, HTTPException, Depends, Query, Request
from typing import List, Optional
import logging
from ....models.types import Agent, AgentCreate, AgentUpdate
from ....services.agent_manager import AgentManager
from ....services.docker_service import DockerService
from ....core.rate_limit import check_rate_limit

logger = logging.getLogger(__name__)
router = APIRouter()

async def get_agent_manager():
    try:
        docker_service = DockerService()
        docker_service.client.ping()
        logger.info("Docker client is responsive")
        return AgentManager(docker_service)
    except Exception as e:
        logger.exception("Failed to initialize DockerService or AgentManager")
        raise HTTPException(status_code=500, detail=f"Backend initialization error: {str(e)}")

@router.get("", response_model=List[Agent])
async def list_agents(
    channel_type: Optional[str] = Query(None, description="Filter agents that have this channel enabled"),
    manager: AgentManager = Depends(get_agent_manager)
):
    try:
        agents = await manager.list_agents()
        if channel_type:
            agents = [a for a in agents if any(ch for ch in a.channels if ch.type == channel_type and ch.enabled)]
        return agents
    except Exception as e:
        logger.exception("Failed to list agents")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("", response_model=Agent, status_code=201)
async def create_agent(agent_in: AgentCreate, manager: AgentManager = Depends(get_agent_manager)):
    try:
        logger.info(f"Creating agent with data: {agent_in.model_dump(by_alias=True)}")
        result = await manager.create_agent(agent_in)
        logger.info(f"Agent created successfully: {result.id}")
        return result
    except Exception as e:
        logger.exception("Failed to create agent")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/{agent_id}", response_model=Agent)
async def get_agent(agent_id: str, manager: AgentManager = Depends(get_agent_manager)):
    try:
        agent = await manager.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return agent
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get agent {agent_id}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.patch("/{agent_id}", response_model=Agent)
async def update_agent(agent_id: str, agent_update: AgentUpdate, manager: AgentManager = Depends(get_agent_manager)):
    try:
        agent = await manager.update_agent(agent_id, agent_update)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return agent
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to update agent {agent_id}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.delete("/{agent_id}", status_code=204)
async def delete_agent(agent_id: str, manager: AgentManager = Depends(get_agent_manager)):
    try:
        deleted = await manager.delete_agent(agent_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Agent not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to delete agent {agent_id}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/{agent_id}/execute", status_code=202)
async def execute_agent(
    request: Request,
    agent_id: str,
    payload: dict = None,
    simulation: bool = Query(False, description="Run in simulation mode (routes tool calls to simulator)"),
    manager: AgentManager = Depends(get_agent_manager)
):
    # Apply rate limiting
    await check_rate_limit(request, limit_key="execute")

    try:
        input_text = payload.get("input", "") if payload else ""
        success = await manager.execute_agent(agent_id, input_text, simulation)
        if not success:
            raise HTTPException(status_code=404, detail="Agent not found")
        return {"status": "execution triggered", "simulation": simulation}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to execute agent {agent_id}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.post("/{parent_id}/subagents/{child_id}", status_code=200)
async def add_sub_agent(parent_id: str, child_id: str, manager: AgentManager = Depends(get_agent_manager)):
    try:
        success = await manager.add_sub_agent(parent_id, child_id)
        if not success:
            raise HTTPException(status_code=404, detail="Parent or child agent not found")
        return {"status": "sub-agent added"}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to add sub-agent {child_id} to {parent_id}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
