import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.economy_engine import EconomyEngine
from app.models.types import AccountType, Currency, TransactionType
from datetime import datetime
import json

@pytest.mark.asyncio
async def test_create_account():
    engine = EconomyEngine()
    with patch('app.services.economy_engine.AsyncSessionLocal') as mock_session:
        mock_conn = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_conn
        mock_conn.execute = AsyncMock()
        mock_conn.commit = AsyncMock()

        account = await engine.create_account("owner1", AccountType.HIVE, Currency.SIM)
        assert account.id.startswith("acc-")
        assert account.owner_id == "owner1"
        assert account.owner_type == AccountType.HIVE
        assert account.balance == 0.0
        mock_conn.execute.assert_awaited_once()
        mock_conn.commit.assert_awaited_once()

@pytest.mark.asyncio
async def test_get_account():
    engine = EconomyEngine()
    mock_data = {
        "id": "acc-123",
        "owner_id": "owner1",
        "owner_type": "hive",
        "currency": "sim",
        "balance": 100.0,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    with patch('app.services.economy_engine.AsyncSessionLocal') as mock_session:
        mock_conn = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_conn

        # Use MagicMock for fetchone (not AsyncMock)
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (json.dumps(mock_data),)
        mock_conn.execute.return_value = mock_result

        account = await engine.get_account("acc-123")
        assert account is not None
        assert account.id == "acc-123"
        assert account.balance == 100.0

@pytest.mark.asyncio
async def test_update_balance():
    engine = EconomyEngine()
    with patch.object(engine, 'get_account') as mock_get, \
         patch('app.services.economy_engine.AsyncSessionLocal') as mock_session:

        mock_account = MagicMock()
        mock_account.balance = 50.0
        mock_get.return_value = mock_account

        mock_conn = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_conn
        mock_conn.execute = AsyncMock()
        mock_conn.commit = AsyncMock()

        updated = await engine.update_balance("acc-123", 30.0)
        assert updated is not None
        assert mock_account.balance == 80.0
        mock_conn.execute.assert_awaited_once()
        mock_conn.commit.assert_awaited_once()

@pytest.mark.asyncio
async def test_transfer_success():
    engine = EconomyEngine()
    with patch.object(engine, 'get_account') as mock_get, \
         patch.object(engine, 'update_balance') as mock_update, \
         patch.object(engine, 'create_transaction') as mock_create_tx, \
         patch.object(engine, 'complete_transaction') as mock_complete:

        mock_from = MagicMock()
        mock_from.id = "from"
        mock_from.currency = Currency.SIM
        mock_to = MagicMock()
        mock_to.id = "to"
        mock_to.currency = Currency.SIM
        mock_get.side_effect = [mock_from, mock_to]

        mock_update.side_effect = [mock_from, mock_to]  # simulate successful updates

        mock_tx = MagicMock()
        mock_tx.id = "tx-123"
        mock_create_tx.return_value = mock_tx

        mock_complete.return_value = mock_tx

        tx = await engine.transfer("from", "to", 50.0, "test transfer")
        assert tx is not None
        mock_create_tx.assert_awaited_once()
        mock_update.assert_any_call("from", -50.0)
        mock_update.assert_any_call("to", 50.0)
        mock_complete.assert_awaited_once_with("tx-123", success=True)

@pytest.mark.asyncio
async def test_transfer_insufficient_funds():
    engine = EconomyEngine()
    with patch.object(engine, 'get_account') as mock_get, \
         patch.object(engine, 'update_balance') as mock_update, \
         patch.object(engine, 'create_transaction') as mock_create_tx, \
         patch.object(engine, 'complete_transaction') as mock_complete:

        mock_from = MagicMock()
        mock_from.id = "from"
        mock_from.currency = Currency.SIM
        mock_to = MagicMock()
        mock_to.id = "to"
        mock_to.currency = Currency.SIM
        mock_get.side_effect = [mock_from, mock_to]

        # update_balance returns None for source (insufficient funds)
        mock_update.side_effect = [None, None]

        mock_tx = MagicMock()
        mock_tx.id = "tx-123"
        mock_create_tx.return_value = mock_tx

        tx = await engine.transfer("from", "to", 50.0)
        assert tx is None
        mock_create_tx.assert_awaited_once()
        mock_complete.assert_awaited_once_with("tx-123", success=False)
