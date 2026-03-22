from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from ..models.db_models import UserModel
from ..models.types import UserAccount
from ..utils.json_encoder import prepare_json_data
import json

class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user: UserAccount) -> UserAccount:
        data = prepare_json_data(user.model_dump(by_alias=True))
        db_user = UserModel(
            id=user.id,
            data=data
        )
        self.db.add(db_user)
        await self.db.commit()
        await self.db.refresh(db_user)
        return user

    async def get(self, user_id: str) -> UserAccount | None:
        result = await self.db.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        db_user = result.scalar_one_or_none()   # removed await
        if db_user:
            return UserAccount(**db_user.data)
        return None

    async def get_by_username(self, username: str) -> UserAccount | None:
        result = await self.db.execute(select(UserModel))
        db_users = result.scalars().all()
        for u in db_users:
            user = UserAccount(**u.data)
            if user.username == username:
                return user
        return None

    async def get_all(self) -> list[UserAccount]:
        result = await self.db.execute(select(UserModel))
        db_users = result.scalars().all()
        return [UserAccount(**u.data) for u in db_users]

    async def update(self, user_id: str, updates: dict) -> UserAccount | None:
        user = await self.get(user_id)
        if not user:
            return None
        data = prepare_json_data(updates)
        await self.db.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(data=data)
        )
        await self.db.commit()
        return user

    async def delete(self, user_id: str) -> bool:
        result = await self.db.execute(
            delete(UserModel).where(UserModel.id == user_id)
        )
        await self.db.commit()
        return result.rowcount > 0
