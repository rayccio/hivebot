from typing import Optional
from datetime import datetime, timedelta
from ..core.database import AsyncSessionLocal
from sqlalchemy import text
from ..models.types import RiskPolicy, EconomyAccount, Transaction, TransactionType, AccountType
import logging
import uuid

logger = logging.getLogger(__name__)

class RiskManager:
    """Enforces risk policies on accounts."""

    async def get_policy(self, owner_id: str, owner_type: AccountType) -> Optional[RiskPolicy]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT data FROM risk_policies WHERE data->>'owner_id' = :owner_id AND data->>'owner_type' = :owner_type"),
                {"owner_id": owner_id, "owner_type": owner_type.value}
            )
            row = await result.first()          # <-- changed from fetchone()
            if row:
                return RiskPolicy.model_validate_json(row[0])
        return None

    async def create_policy(self, owner_id: str, owner_type: AccountType, **kwargs) -> RiskPolicy:
        policy_id = f"pol-{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow()
        policy = RiskPolicy(
            id=policy_id,
            owner_id=owner_id,
            owner_type=owner_type,
            max_loss_per_trade=kwargs.get("max_loss_per_trade", 0.0),
            max_daily_loss=kwargs.get("max_daily_loss", 0.0),
            max_position_size=kwargs.get("max_position_size", 0.0),
            kill_switch_enabled=kwargs.get("kill_switch_enabled", False),
            kill_switch_triggered=False,
            created_at=now,
            updated_at=now
        )
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("INSERT INTO risk_policies (id, data) VALUES (:id, :data)"),
                {"id": policy_id, "data": policy.model_dump_json()}
            )
            await session.commit()
        logger.info(f"Created risk policy {policy_id} for {owner_type} {owner_id}")
        return policy

    async def update_policy(self, policy_id: str, **updates) -> Optional[RiskPolicy]:
        policy = await self.get_policy_by_id(policy_id)
        if not policy:
            return None
        for k, v in updates.items():
            if hasattr(policy, k):
                setattr(policy, k, v)
        policy.updated_at = datetime.utcnow()
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE risk_policies SET data = :data WHERE id = :id"),
                {"data": policy.model_dump_json(), "id": policy_id}
            )
            await session.commit()
        return policy

    async def get_policy_by_id(self, policy_id: str) -> Optional[RiskPolicy]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT data FROM risk_policies WHERE id = :id"),
                {"id": policy_id}
            )
            row = await result.first()          # <-- changed from fetchone()
            if row:
                return RiskPolicy.model_validate_json(row[0])
        return None

    async def check_trade_allowed(self, account: EconomyAccount, amount: float) -> tuple[bool, str]:
        """Check if a trade of given amount is allowed under the account's risk policy."""
        policy = await self.get_policy(account.owner_id, account.owner_type)
        if not policy:
            return True, "No policy"
        if policy.kill_switch_enabled and policy.kill_switch_triggered:
            return False, "Kill switch triggered"
        if policy.max_loss_per_trade > 0 and amount < 0 and abs(amount) > policy.max_loss_per_trade:
            return False, f"Loss exceeds max per trade ({policy.max_loss_per_trade})"
        if policy.max_position_size > 0 and abs(amount) > policy.max_position_size:
            return False, f"Position size exceeds max ({policy.max_position_size})"
        # Daily loss check
        if policy.max_daily_loss > 0 and amount < 0:
            from .economy_engine import EconomyEngine
            econ = EconomyEngine()
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            transactions = await econ.list_transactions(account.id, limit=1000)
            today_loss = sum(
                t.amount for t in transactions
                if t.type in (TransactionType.TRADE, TransactionType.TRANSFER)
                and t.amount < 0
                and t.created_at >= today_start
            )
            if today_loss + amount < -policy.max_daily_loss:
                return False, f"Daily loss limit would be exceeded ({policy.max_daily_loss})"
        return True, "OK"

    async def trigger_kill_switch(self, owner_id: str, owner_type: AccountType) -> bool:
        """Trigger kill switch for an account (stop all trading)."""
        policy = await self.get_policy(owner_id, owner_type)
        if not policy:
            return False
        if not policy.kill_switch_enabled:
            return False
        policy.kill_switch_triggered = True
        policy.updated_at = datetime.utcnow()
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("UPDATE risk_policies SET data = :data WHERE id = :id"),
                {"data": policy.model_dump_json(), "id": policy.id}
            )
            await session.commit()
        logger.warning(f"Kill switch triggered for {owner_type} {owner_id}")
        return True
