from typing import List, Optional
from datetime import datetime
from ..core.database import AsyncSessionLocal
from ..repositories.skill_suggestion_repository import SkillSuggestionRepository
from ..repositories.skill_repository import SkillRepository
from ..models.skill import SkillSuggestion, SkillSuggestionCreate, SkillCreate, SkillType, SkillVisibility

class SkillSuggestionManager:
    async def _get_repo(self):
        session = AsyncSessionLocal()
        return SkillSuggestionRepository(session), session

    async def _get_skill_repo(self, session):
        return SkillRepository(session)

    async def create_suggestion(self, suggestion_in: SkillSuggestionCreate) -> SkillSuggestion:
        repo, session = await self._get_repo()
        try:
            suggestion = await repo.create(suggestion_in)
            return suggestion
        finally:
            await session.close()

    async def get_all_unresolved(self) -> List[SkillSuggestion]:
        repo, session = await self._get_repo()
        try:
            return await repo.get_all_unresolved()
        finally:
            await session.close()

    async def get_suggestion(self, suggestion_id: str) -> Optional[SkillSuggestion]:
        repo, session = await self._get_repo()
        try:
            return await repo.get(suggestion_id)
        finally:
            await session.close()

    async def delete_suggestion(self, suggestion_id: str) -> bool:
        repo, session = await self._get_repo()
        try:
            return await repo.delete(suggestion_id)
        finally:
            await session.close()

    async def create_skill_from_suggestion(self, suggestion_id: str) -> Optional[SkillCreate]:
        repo, session = await self._get_repo()
        try:
            suggestion = await repo.get(suggestion_id)
            if not suggestion or suggestion.resolved:
                return None

            # Create a stub skill
            skill_in = SkillCreate(
                name=suggestion.skill_name,
                description=f"Auto‑created from suggestion for task: {suggestion.task_description[:100]}",
                type=SkillType.TOOL,
                visibility=SkillVisibility.PRIVATE,
                tags=["suggested"],
                metadata={
                    "from_suggestion": suggestion_id,
                    "goal_id": suggestion.goal_id,
                    "task_id": suggestion.task_id
                }
            )
            skill_repo = await self._get_skill_repo(session)
            from .skill_manager import SkillManager
            # Use SkillManager to create the skill (handles ID generation, timestamps)
            skill_manager = SkillManager()
            # We need to call create_skill, which expects its own session; easier: use skill_repo directly
            # But SkillManager uses its own session management. To avoid complexity, we'll call SkillManager's create_skill.
            # However, we're inside a transaction; better to use SkillManager with the same session? Not easily.
            # Simpler: create the skill using SkillManager (new session) and then mark suggestion resolved.
            await session.close()  # close current session before calling SkillManager
            skill_manager = SkillManager()
            skill = await skill_manager.create_skill(skill_in)

            # Mark suggestion resolved (new session)
            repo2, session2 = await self._get_repo()
            try:
                await repo2.mark_resolved(suggestion_id)
            finally:
                await session2.close()

            return skill
        except Exception as e:
            await session.rollback()
            raise e
