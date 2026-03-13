import json
import os
from typing import Dict, Optional, List, Set
from datetime import datetime
from ..models.types import Agent, AgentCreate, AgentUpdate, AgentStatus, ChannelConfig, MetaInfo, ReasoningConfig, ReportingTarget
from ..core.config import settings
from .docker_service import DockerService
from .redis_service import redis_service
from ..repositories.agent_repository import AgentRepository
from ..core.database import AsyncSessionLocal
from ..constants import INITIAL_SOUL, INITIAL_IDENTITY, INITIAL_TOOLS
from .hive_manager import HiveManager
import uuid
import shutil
import logging

logger = logging.getLogger(__name__)

class AgentManager:
    def __init__(self, docker_service: DockerService):
        self.docker = docker_service
        self.cache: Dict[str, Agent] = {}

    async def _get_repo(self):
        session = AsyncSessionLocal()
        return AgentRepository(session), session

    async def _publish_config_update(self, agent: Agent, changed_types: Set[str]):
        for ch_type in changed_types:
            logger.info(f"Publishing config update for agent {agent.id} on channel type {ch_type}")
            await redis_service.publish(f"config:bridge:{ch_type}", json.dumps({"agent_id": agent.id}))

    async def create_agent(self, agent_in: AgentCreate) -> Agent:
        agent_id = f"b-{uuid.uuid4().hex[:4]}"
        user_uid = agent_in.user_uid or settings.DEFAULT_AGENT_UID
        internal_api_key = settings.secrets.get("INTERNAL_API_KEY")
        if not internal_api_key:
            raise RuntimeError("Internal API key not configured")

        container_id = ""  # empty means no container by default

        agent_dir = settings.AGENTS_DIR / agent_id
        agent_dir.mkdir(parents=True, exist_ok=True)
        with open(agent_dir / "soul.md", "w") as f:
            f.write(agent_in.soul_md)
        with open(agent_dir / "identity.md", "w") as f:
            f.write(agent_in.identity_md)
        with open(agent_dir / "tools.md", "w") as f:
            f.write(agent_in.tools_md)

        files_dir = agent_dir / "files"
        files_dir.mkdir(exist_ok=True)

        agent = Agent(
            id=agent_id,
            name=agent_in.name,
            role=agent_in.role,
            soul_md=agent_in.soul_md,
            identity_md=agent_in.identity_md,
            tools_md=agent_in.tools_md,
            status=AgentStatus.IDLE,
            reasoning=agent_in.reasoning,
            reporting_target=agent_in.reporting_target,
            parent_id=agent_in.parent_id,
            sub_agent_ids=[],
            memory={"short_term": [], "summary": "", "token_count": 0},
            last_active=datetime.utcnow(),
            container_id=container_id,
            user_uid=user_uid,
            local_files=[],
            channels=agent_in.channels or [],
            skills=[],
            meta={}
        )

        repo, session = await self._get_repo()
        try:
            await repo.create(agent)
        finally:
            await session.close()

        self.cache[agent_id] = agent

        if agent.parent_id and agent.parent_id in self.cache:
            parent = self.cache[agent.parent_id]
            parent.sub_agent_ids.append(agent_id)
            await self.update_agent(parent.id, AgentUpdate(sub_agent_ids=parent.sub_agent_ids))

        channel_types = {ch.type for ch in agent.channels if ch.enabled}
        if channel_types:
            await self._publish_config_update(agent, channel_types)

        logger.info(f"Created bot {agent_id} (worker-based)")
        return agent

    async def add_sub_agent(self, parent_id: str, child_id: str) -> bool:
        repo, session = await self._get_repo()
        try:
            parent = await repo.get(parent_id)
            child = await repo.get(child_id)
            if not parent or not child:
                return False

            if child.parent_id and child.parent_id != parent_id:
                old_parent = await repo.get(child.parent_id)
                if old_parent and child_id in old_parent.sub_agent_ids:
                    old_parent.sub_agent_ids.remove(child_id)
                    await repo.update(old_parent.id, {"sub_agent_ids": old_parent.sub_agent_ids})

            child.parent_id = parent_id
            if child_id not in parent.sub_agent_ids:
                parent.sub_agent_ids.append(child_id)

            await repo.update(parent_id, {"sub_agent_ids": parent.sub_agent_ids})
            await repo.update(child_id, {"parent_id": parent_id})
        finally:
            await session.close()

        if parent_id in self.cache:
            self.cache[parent_id].sub_agent_ids = parent.sub_agent_ids
        if child_id in self.cache:
            self.cache[child_id].parent_id = parent_id

        logger.info(f"Bot {child_id} now child of {parent_id}")
        return True

    async def get_agent(self, agent_id: str) -> Optional[Agent]:
        if agent_id in self.cache:
            agent = self.cache[agent_id]
        else:
            repo, session = await self._get_repo()
            try:
                agent = await repo.get(agent_id)
            finally:
                await session.close()
            if agent:
                self.cache[agent_id] = agent

        if agent and agent.container_id:
            status = self.docker.get_container_status(agent.container_id)
            agent.status = self._map_docker_status(status)

        return agent

    async def list_agents(self) -> List[Agent]:
        repo, session = await self._get_repo()
        try:
            agents = await repo.get_all()
        finally:
            await session.close()

        container_map = self.docker.list_containers()
        for agent in agents:
            if agent.container_id:
                if agent.container_id in container_map:
                    agent.status = self._map_docker_status(container_map[agent.container_id]["status"])
                else:
                    agent.status = AgentStatus.OFFLINE
            else:
                # worker-based agent: status is stored in DB (updated by worker)
                pass
            self.cache[agent.id] = agent

        return agents

    async def get_agents_by_channel_type(self, channel_type: str) -> List[Agent]:
        all_agents = await self.list_agents()
        return [a for a in all_agents if any(ch for ch in a.channels if ch.type == channel_type and ch.enabled)]

    async def update_agent(self, agent_id: str, agent_update: AgentUpdate) -> Optional[Agent]:
        agent = await self.get_agent(agent_id)
        if not agent:
            return None

        update_data = agent_update.model_dump(exclude_unset=True, by_alias=False)

        old_enabled_channels = {ch.id: ch for ch in agent.channels if ch.enabled}
        old_types = {ch.type for ch in agent.channels if ch.enabled}

        for field, value in update_data.items():
            if field == "channels" and value is not None:
                converted = []
                for ch_dict in value:
                    if isinstance(ch_dict, dict):
                        converted.append(ChannelConfig(**ch_dict))
                    else:
                        converted.append(ch_dict)
                setattr(agent, field, converted)
            elif field == "meta" and value is not None:
                if isinstance(value, dict):
                    current_meta = agent.meta.model_dump() if agent.meta else {}
                    current_meta.update(value)
                    agent.meta = MetaInfo(**current_meta)
                else:
                    agent.meta = value
            elif field != "skills":
                setattr(agent, field, value)

        new_enabled_channels = {ch.id: ch for ch in agent.channels if ch.enabled}
        new_types = {ch.type for ch in agent.channels if ch.enabled}
        changed_types = old_types.symmetric_difference(new_types)

        common_ids = set(old_enabled_channels.keys()) & set(new_enabled_channels.keys())
        for ch_id in common_ids:
            old_ch = old_enabled_channels[ch_id]
            new_ch = new_enabled_channels[ch_id]
            if old_ch.credentials != new_ch.credentials:
                changed_types.add(old_ch.type)

        if "soul_md" in update_data or "identity_md" in update_data or "tools_md" in update_data:
            agent_dir = settings.AGENTS_DIR / agent_id
            if "soul_md" in update_data:
                with open(agent_dir / "soul.md", "w") as f:
                    f.write(agent.soul_md)
            if "identity_md" in update_data:
                with open(agent_dir / "identity.md", "w") as f:
                    f.write(agent.identity_md)
            if "tools_md" in update_data:
                with open(agent_dir / "tools.md", "w") as f:
                    f.write(agent.tools_md)

        agent.last_active = datetime.utcnow()

        repo, session = await self._get_repo()
        try:
            updated = await repo.update(agent_id, agent.model_dump(by_alias=True))
        finally:
            await session.close()

        self.cache[agent_id] = agent

        if changed_types:
            logger.info(f"Agent {agent_id} channel changes detected: {changed_types}")
            await self._publish_config_update(agent, changed_types)

        return agent

    async def delete_agent(self, agent_id: str) -> bool:
        agent = await self.get_agent(agent_id)
        if not agent:
            return False

        channel_types = {ch.type for ch in agent.channels if ch.enabled}

        if agent.parent_id:
            parent = await self.get_agent(agent.parent_id)
            if parent and agent_id in parent.sub_agent_ids:
                parent.sub_agent_ids.remove(agent_id)
                await self.update_agent(parent.id, AgentUpdate(sub_agent_ids=parent.sub_agent_ids))

        if agent.container_id:
            self.docker.stop_container(agent.container_id)

        repo, session = await self._get_repo()
        try:
            deleted = await repo.delete(agent_id)
        finally:
            await session.close()

        if not deleted:
            return False

        if agent_id in self.cache:
            del self.cache[agent_id]

        shutil.rmtree(settings.AGENTS_DIR / agent_id, ignore_errors=True)
        await redis_service.clear_conversation(agent_id)

        if channel_types:
            for ch_type in channel_types:
                await redis_service.publish(f"config:bridge:{ch_type}", json.dumps({"agent_id": agent_id}))

        return True

    async def execute_agent(self, agent_id: str, input_text: str = "", simulation: bool = False) -> bool:
        agent = await self.get_agent(agent_id)
        if not agent:
            return False

        message = {
            "type": "think",
            "input": input_text,
            "config": agent.reasoning.model_dump(),
            "timestamp": datetime.utcnow().isoformat(),
            "simulation": simulation
        }
        await redis_service.publish(f"agent:{agent_id}", message)

        await self.update_agent(agent_id, AgentUpdate(status=AgentStatus.RUNNING))
        return True

    def _map_docker_status(self, docker_status: str) -> AgentStatus:
        if docker_status == "running":
            return AgentStatus.RUNNING
        elif docker_status in ("exited", "dead"):
            return AgentStatus.ERROR
        elif docker_status == "paused":
            return AgentStatus.IDLE
        else:
            return AgentStatus.OFFLINE

    # --- NEW: Spawn agent for a task ---
    async def spawn_agent_for_task(self, hive_id: str, required_skill_ids: List[str]) -> Optional[Agent]:
        """Create a new agent with the required skills and add it to the hive."""
        from .skill_manager import SkillManager
        skill_manager = SkillManager()

        # Build a default agent configuration
        agent_in = AgentCreate(
            name="Auto-spawned Agent",
            role="Worker",
            soulMd=INITIAL_SOUL,
            identityMd=INITIAL_IDENTITY,
            toolsMd=INITIAL_TOOLS,
            reasoning=ReasoningConfig(
                model="openai/gpt-4o",  # or use global default
                temperature=0.7,
                topP=1.0,
                maxTokens=150,
                use_global_default=True
            ),
            reporting_target=ReportingTarget.PARENT,
            parent_id=None,
            user_uid=settings.DEFAULT_AGENT_UID,
            channels=[]
        )
        agent = await self.create_agent(agent_in)

        # Install the required skills
        for skill_id in required_skill_ids:
            skill = await skill_manager.get_skill(skill_id)
            if not skill:
                continue
            # Get the latest active version
            versions = await skill_manager.list_versions(skill.id)
            active_versions = [v for v in versions if v.is_active]
            if active_versions:
                latest = max(active_versions, key=lambda v: v.created_at)
                await skill_manager.install_skill(agent.id, skill.id, latest.id, {})

        # Add agent to the hive
        hive_manager = HiveManager(self)  # pass self as agent_manager
        await hive_manager.add_agent(hive_id, agent)

        logger.info(f"Spawned agent {agent.id} for hive {hive_id} with skills {required_skill_ids}")
        return agent
