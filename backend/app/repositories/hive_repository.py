# backend/app/repositories/hive_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from ..models.db_models import HiveModel
from ..models.types import Hive
from ..utils.json_encoder import prepare_json_data
import json

class HiveRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, hive: Hive) -> Hive:
        # Exclude 'agents' field from being stored
        data = prepare_json_data(hive.model_dump(by_alias=True, exclude={'agents'}))
        db_hive = HiveModel(
            id=hive.id,
            data=data
        )
        self.db.add(db_hive)
        await self.db.commit()
        await self.db.refresh(db_hive)
        return hive

    async def get(self, hive_id: str) -> Hive | None:
        result = await self.db.execute(
            select(HiveModel).where(HiveModel.id == hive_id)
        )
        db_hive = result.scalar_one_or_none()
        if db_hive:
            return Hive(**db_hive.data)
        return None

    async def get_all(self) -> list[Hive]:
        result = await self.db.execute(select(HiveModel))
        db_hives = result.scalars().all()
        return [Hive(**h.data) for h in db_hives]

    async def update(self, hive_id: str, updates: dict) -> Hive | None:
        data = prepare_json_data(updates)
        # Remove 'agents' key if present (since it's not stored)
        data.pop('agents', None)
        await self.db.execute(
            update(HiveModel)
            .where(HiveModel.id == hive_id)
            .values(data=data)
        )
        await self.db.commit()
        return await self.get(hive_id)

    async def delete(self, hive_id: str) -> bool:
        result = await self.db.execute(
            delete(HiveModel).where(HiveModel.id == hive_id)
        )
        await self.db.commit()
        return result.rowcount > 0
