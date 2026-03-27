from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from ..models.db_models import SkillModel
from ..models.skill import Skill
from ..utils.json_encoder import prepare_json_data
import json

class SkillRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, skill: Skill) -> Skill:
        data = prepare_json_data(skill.model_dump(by_alias=True))
        db_skill = SkillModel(
            id=skill.id,
            data=data
        )
        self.db.add(db_skill)
        await self.db.commit()
        await self.db.refresh(db_skill)
        return skill

    async def get(self, skill_id: str) -> Skill | None:
        result = await self.db.execute(
            select(SkillModel).where(SkillModel.id == skill_id)
        )
        db_skill = result.scalar_one_or_none()
        if db_skill:
            return Skill(**db_skill.data)
        return None

    async def get_all(self) -> list[Skill]:
        result = await self.db.execute(select(SkillModel))
        db_skills = result.scalars().all()
        return [Skill(**s.data) for s in db_skills]

    async def update(self, skill_id: str, updates: dict) -> Skill | None:
        skill = await self.get(skill_id)
        if not skill:
            return None
        data = prepare_json_data(updates)
        await self.db.execute(
            update(SkillModel)
            .where(SkillModel.id == skill_id)
            .values(data=data)
        )
        await self.db.commit()
        return skill

    async def delete(self, skill_id: str) -> bool:
        result = await self.db.execute(
            delete(SkillModel).where(SkillModel.id == skill_id)
        )
        await self.db.commit()
        return result.rowcount > 0
