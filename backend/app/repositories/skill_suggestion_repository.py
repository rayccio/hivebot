from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from ..models.db_models import SkillSuggestionModel
from ..models.skill import SkillSuggestion, SkillSuggestionCreate
from ..utils.json_encoder import prepare_json_data
from datetime import datetime
import json
import uuid

class SkillSuggestionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, suggestion_in: SkillSuggestionCreate) -> SkillSuggestion:
        suggestion_id = f"ss-{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow()
        db_suggestion = SkillSuggestionModel(
            id=suggestion_id,
            skill_name=suggestion_in.skill_name,
            goal_id=suggestion_in.goal_id,
            goal_description=suggestion_in.goal_description,
            task_id=suggestion_in.task_id,
            task_description=suggestion_in.task_description,
            suggested_by=suggestion_in.suggested_by,
            resolved=False,
            created_at=now,
            resolved_at=None
        )
        self.db.add(db_suggestion)
        await self.db.commit()
        await self.db.refresh(db_suggestion)
        # Return as Pydantic model
        return SkillSuggestion(
            id=db_suggestion.id,
            skill_name=db_suggestion.skill_name,
            goal_id=db_suggestion.goal_id,
            goal_description=db_suggestion.goal_description,
            task_id=db_suggestion.task_id,
            task_description=db_suggestion.task_description,
            suggested_by=db_suggestion.suggested_by,
            resolved=db_suggestion.resolved,
            created_at=db_suggestion.created_at,
            resolved_at=db_suggestion.resolved_at
        )

    async def get_all_unresolved(self) -> list[SkillSuggestion]:
        result = await self.db.execute(
            select(SkillSuggestionModel).where(SkillSuggestionModel.resolved == False).order_by(SkillSuggestionModel.created_at.desc())
        )
        rows = result.scalars().all()
        return [SkillSuggestion(
            id=r.id,
            skill_name=r.skill_name,
            goal_id=r.goal_id,
            goal_description=r.goal_description,
            task_id=r.task_id,
            task_description=r.task_description,
            suggested_by=r.suggested_by,
            resolved=r.resolved,
            created_at=r.created_at,
            resolved_at=r.resolved_at
        ) for r in rows]

    async def get(self, suggestion_id: str) -> SkillSuggestion | None:
        result = await self.db.execute(
            select(SkillSuggestionModel).where(SkillSuggestionModel.id == suggestion_id)
        )
        r = result.scalar_one_or_none()
        if not r:
            return None
        return SkillSuggestion(
            id=r.id,
            skill_name=r.skill_name,
            goal_id=r.goal_id,
            goal_description=r.goal_description,
            task_id=r.task_id,
            task_description=r.task_description,
            suggested_by=r.suggested_by,
            resolved=r.resolved,
            created_at=r.created_at,
            resolved_at=r.resolved_at
        )

    async def mark_resolved(self, suggestion_id: str) -> bool:
        result = await self.db.execute(
            update(SkillSuggestionModel)
            .where(SkillSuggestionModel.id == suggestion_id)
            .values(resolved=True, resolved_at=datetime.utcnow())
        )
        await self.db.commit()
        return result.rowcount > 0

    async def delete(self, suggestion_id: str) -> bool:
        result = await self.db.execute(
            delete(SkillSuggestionModel).where(SkillSuggestionModel.id == suggestion_id)
        )
        await self.db.commit()
        return result.rowcount > 0
