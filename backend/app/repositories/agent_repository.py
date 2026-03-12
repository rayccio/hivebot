from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from ..models.db_models import AgentModel
from ..models.types import Agent
from ..utils.json_encoder import prepare_json_data
import json

class AgentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, agent: Agent) -> Agent:
        data = prepare_json_data(agent.dict(by_alias=True))
        # agent.status might be an enum or a string; handle both
        status_value = agent.status.value if hasattr(agent.status, 'value') else agent.status
        db_agent = AgentModel(
            id=agent.id,
            data=data,
            container_id=agent.container_id,
            status=status_value
        )
        self.db.add(db_agent)
        await self.db.commit()
        await self.db.refresh(db_agent)
        return agent

    async def get(self, agent_id: str) -> Agent | None:
        result = await self.db.execute(
            select(AgentModel).where(AgentModel.id == agent_id)
        )
        db_agent = result.scalar_one_or_none()
        if db_agent:
            return Agent(**db_agent.data)
        return None

    async def get_all(self) -> list[Agent]:
        result = await self.db.execute(select(AgentModel))
        db_agents = result.scalars().all()
        return [Agent(**a.data) for a in db_agents]

    async def update(self, agent_id: str, updates: dict) -> Agent | None:
        agent = await self.get(agent_id)
        if not agent:
            return None
        for k, v in updates.items():
            if hasattr(agent, k):
                setattr(agent, k, v)
        data = prepare_json_data(agent.dict(by_alias=True))
        status_value = agent.status.value if hasattr(agent.status, 'value') else agent.status
        await self.db.execute(
            update(AgentModel)
            .where(AgentModel.id == agent_id)
            .values(data=data, status=status_value)
        )
        await self.db.commit()
        return agent

    async def delete(self, agent_id: str) -> bool:
        result = await self.db.execute(
            delete(AgentModel).where(AgentModel.id == agent_id)
        )
        await self.db.commit()
        return result.rowcount > 0
