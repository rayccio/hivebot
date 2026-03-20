# backend/app/services/hive_manager.py
import json
import os
from typing import Dict, Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..models.types import Hive, HiveCreate, HiveUpdate, Agent, Message, FileEntry
from ..models.types import HiveTaskStatus
from ..core.config import settings
from ..core.database import AsyncSessionLocal
from ..repositories.hive_repository import HiveRepository
from ..repositories.agent_repository import AgentRepository
from .task_manager import TaskManager
import uuid
import shutil
import logging

logger = logging.getLogger(__name__)

class HiveManager:
    def __init__(self, agent_manager):
        self.agent_manager = agent_manager
        self.repo = HiveRepository

    async def _get_session_and_repo(self):
        session = AsyncSessionLocal()
        return HiveRepository(session), session

    async def _get_agent_repo(self, session: AsyncSession):
        return AgentRepository(session)

    async def create_hive(self, hive_in: HiveCreate) -> Hive:
        hive_id = f"h-{uuid.uuid4().hex[:4]}"
        hive_dir = settings.AGENTS_DIR / hive_id
        hive_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.utcnow()
        hive = Hive(
            id=hive_id,
            name=hive_in.name,
            description=hive_in.description,
            agent_ids=[],
            global_user_md=hive_in.global_user_md,
            messages=[],
            global_files=[],
            hive_mind_config={"access_level": "ISOLATED", "shared_hive_ids": []},
            created_at=now,
            updated_at=now
        )
        repo, session = await self._get_session_and_repo()
        try:
            created = await repo.create(hive)
        finally:
            await session.close()
        logger.info(f"Created hive {hive_id}")
        return created

    async def get_hive(self, hive_id: str) -> Optional[Hive]:
        repo, session = await self._get_session_and_repo()
        try:
            hive = await repo.get(hive_id)
            if not hive:
                return None
            agent_ids = hive.agent_ids
            agents = []
            if agent_ids:
                agent_repo = await self._get_agent_repo(session)
                for aid in agent_ids:
                    agent = await agent_repo.get(aid)
                    if agent:
                        agents.append(agent)
            hive.agents = agents
            return hive
        finally:
            await session.close()

    async def list_hives(self) -> List[Hive]:
        repo, session = await self._get_session_and_repo()
        try:
            hives = await repo.get_all()
            agent_repo = await self._get_agent_repo(session)
            for hive in hives:
                agent_ids = hive.agent_ids
                agents = []
                for aid in agent_ids:
                    agent = await agent_repo.get(aid)
                    if agent:
                        agents.append(agent)
                hive.agents = agents
            return hives
        finally:
            await session.close()

    async def update_hive(self, hive_id: str, hive_update: HiveUpdate) -> Optional[Hive]:
        repo, session = await self._get_session_and_repo()
        try:
            hive = await repo.get(hive_id)
            if not hive:
                return None
            update_data = hive_update.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(hive, field):
                    setattr(hive, field, value)
            hive.updated_at = datetime.utcnow()
            await repo.update(hive_id, hive.model_dump(by_alias=True))
            return await self.get_hive(hive_id)
        finally:
            await session.close()

    async def delete_hive(self, hive_id: str) -> bool:
        repo, session = await self._get_session_and_repo()
        try:
            deleted = await repo.delete(hive_id)
            if deleted:
                hive_dir = settings.AGENTS_DIR / hive_id
                if hive_dir.exists():
                    shutil.rmtree(hive_dir, ignore_errors=True)
            return deleted
        finally:
            await session.close()

    async def add_agent(self, hive_id: str, agent: Agent) -> Optional[Hive]:
        repo, session = await self._get_session_and_repo()
        try:
            hive = await repo.get(hive_id)
            if not hive:
                return None
            if agent.id not in hive.agent_ids:
                hive.agent_ids.append(agent.id)
                hive.updated_at = datetime.utcnow()
                await repo.update(hive_id, hive.model_dump(by_alias=True))
            return await self.get_hive(hive_id)
        finally:
            await session.close()

    async def remove_agent(self, hive_id: str, agent_id: str) -> Optional[Hive]:
        repo, session = await self._get_session_and_repo()
        try:
            hive = await repo.get(hive_id)
            if not hive:
                return None
            if agent_id in hive.agent_ids:
                hive.agent_ids.remove(agent_id)
                hive.updated_at = datetime.utcnow()
                await repo.update(hive_id, hive.model_dump(by_alias=True))
            return await self.get_hive(hive_id)
        finally:
            await session.close()

    async def add_message(self, hive_id: str, message: Message) -> Optional[Hive]:
        repo, session = await self._get_session_and_repo()
        try:
            hive = await repo.get(hive_id)
            if not hive:
                return None
            messages = hive.messages
            messages.append(message)
            if len(messages) > 100:
                messages = messages[-100:]
            hive.messages = messages
            hive.updated_at = datetime.utcnow()
            await repo.update(hive_id, hive.model_dump(by_alias=True))
            return await self.get_hive(hive_id)
        finally:
            await session.close()

    async def add_global_file(self, hive_id: str, file_entry: FileEntry) -> Optional[Hive]:
        repo, session = await self._get_session_and_repo()
        try:
            hive = await repo.get(hive_id)
            if not hive:
                return None
            files = hive.global_files
            files.append(file_entry)
            hive.global_files = files
            hive.updated_at = datetime.utcnow()
            await repo.update(hive_id, hive.model_dump(by_alias=True))
            return await self.get_hive(hive_id)
        finally:
            await session.close()

    async def remove_global_file(self, hive_id: str, file_id: str) -> Optional[Hive]:
        repo, session = await self._get_session_and_repo()
        try:
            hive = await repo.get(hive_id)
            if not hive:
                return None
            files = [f for f in hive.global_files if f.id != file_id]
            hive.global_files = files
            hive.updated_at = datetime.utcnow()
            await repo.update(hive_id, hive.model_dump(by_alias=True))
            return await self.get_hive(hive_id)
        finally:
            await session.close()

    async def get_active_agents(self, hive_id: str) -> List[Agent]:
        task_manager = TaskManager()
        tasks = await task_manager.list_tasks_for_hive(hive_id)
        active_agent_ids = set()
        for t in tasks:
            if t.status in (HiveTaskStatus.ASSIGNED, HiveTaskStatus.RUNNING) and t.assigned_agent_id:
                active_agent_ids.add(t.assigned_agent_id)
        agents = []
        for aid in active_agent_ids:
            agent = await self.agent_manager.get_agent(aid)
            if agent:
                agents.append(agent)
        return agents
