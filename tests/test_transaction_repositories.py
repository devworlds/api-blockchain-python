import datetime
from unittest.mock import MagicMock

import pytest

from app.domain.transaction.entity import Transaction as TransactionEntity
from app.domain.transaction.repository import TransactionRepository
from app.infrastructure.blockchain.transaction.node_repository import (
    Web3TransactionRepository,
)
from app.infrastructure.db.transaction.postgresql_repository import (
    PostgreSQLTransactionRepository,
)


class DummyTransactionRepository(TransactionRepository):
    def is_token_transaction(self, transaction_hash: str) -> bool:
        return transaction_hash.startswith("0x")

    def get_transaction(self, transaction_hash: str) -> dict:
        return {"hash": transaction_hash}

    def is_valid_transaction(self, transaction_hash: str) -> bool:
        return True


def test_dummy_transaction_repository():
    repo = DummyTransactionRepository()
    assert repo.is_token_transaction("0xabc")
    assert repo.get_transaction("0xabc")["hash"] == "0xabc"
    assert repo.is_valid_transaction("0xabc")


def test_web3_transaction_repository_methods():
    web3 = MagicMock()
    tx = MagicMock()
    tx.input = "0x"  # ETH transaction has empty input
    tx.value = 123
    tx.to = "0xto"
    tx.__getitem__.side_effect = lambda k: {"from": "0xfrom"}[k]
    tx.hash.hex.return_value = "0xhash"
    tx.blockNumber = 100
    web3.eth.get_transaction.return_value = tx
    web3.eth.block_number = 106  # 7 confirmations
    repo = Web3TransactionRepository(web3)
    result = repo.get_transaction("0xabc")
    assert result["input"] == "0x"
    assert result["value"] == 123
    assert result["to"] == "0xto"
    assert result["from"] == "0xfrom"
    assert result["hash"] == "0xhash"
    assert repo.is_token_transaction("0xabc") is False  # ETH transaction
    assert (
        repo.is_valid_transaction("0xabc", require_confirmations=False) is True
    )  # Test without confirmations
    assert (
        repo.is_valid_transaction(
            "0xabc", require_confirmations=True, min_confirmations=6
        )
        is True
    )  # Test with confirmations


def test_web3_transaction_repository_token_methods():
    web3 = MagicMock()
    tx = MagicMock()
    tx.input = "0xa9059cbb000000000000000000000000"  # Token transaction with data
    web3.eth.get_transaction.return_value = tx
    repo = Web3TransactionRepository(web3)
    assert repo.is_token_transaction("0xabc") is True  # Token transaction


import asyncio
import types


class AsyncContextManagerMock:
    def __init__(self, obj):
        self.obj = obj

    async def __aenter__(self):
        return self.obj

    async def __aexit__(self, exc_type, exc, tb):
        pass


@pytest.mark.asyncio
async def test_postgresql_transaction_repository_methods():
    pool = MagicMock()
    repo = PostgreSQLTransactionRepository(pool)
    # save_transaction
    tx = TransactionEntity(
        hash="0xhash",
        asset="ETH",
        address_from="0xfrom",
        address_to="0xto",
        value=1,
        is_token=False,
        type="onchain",
        status="pending",
        effective_fee=1,
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
        deleted_at=None,
        contract_address=None,
    )
    conn = MagicMock()
    pool.acquire.return_value = AsyncContextManagerMock(conn)
    from unittest.mock import AsyncMock

    conn.execute = AsyncMock()
    await repo.save_transaction(tx)
    conn.execute.assert_called()
    # get_transaction_by_hash
    conn.fetchrow = AsyncMock(
        return_value={
            "hash": "0xhash",
            "asset": "ETH",
            "address_from": "0xfrom",
            "address_to": "0xto",
            "value": 1,
            "is_token": False,
            "type": "onchain",
            "status": "pending",
            "effective_fee": 1,
            "created_at": datetime.datetime.now(),
            "updated_at": datetime.datetime.now(),
            "deleted_at": None,
            "contract_address": None,
        }
    )
    result = await repo.get_transaction_by_hash("0xhash")
    assert result.hash == "0xhash"
    assert result.asset == "ETH"
    assert result.address_from == "0xfrom"
    assert result.address_to == "0xto"
    assert result.value == 1
    assert result.is_token is False
    assert result.type == "onchain"
    assert result.status == "pending"
    assert result.effective_fee == 1


def test_web3_transaction_repository_confirmations():
    web3 = MagicMock()
    tx = MagicMock()
    tx.blockNumber = 100
    web3.eth.get_transaction.return_value = tx
    web3.eth.block_number = 106  # 7 confirmations
    repo = Web3TransactionRepository(web3)

    # Test confirmations calculation
    confirmations = repo.get_transaction_confirmations("0xabc")
    assert confirmations == 7

    # Test confirmed transaction
    assert repo.is_transaction_confirmed("0xabc", 6) is True
    assert repo.is_transaction_confirmed("0xabc", 8) is False

    # Test pending transaction
    tx.blockNumber = None
    confirmations = repo.get_transaction_confirmations("0xabc")
    assert confirmations == 0
    assert repo.is_transaction_confirmed("0xabc", 1) is False


def test_web3_transaction_repository_valid_with_confirmations():
    web3 = MagicMock()
    tx = MagicMock()
    tx.blockNumber = 100
    tx.hash = MagicMock()
    web3.eth.get_transaction.return_value = tx
    web3.eth.block_number = 106  # 7 confirmations
    repo = Web3TransactionRepository(web3)

    # Test valid with confirmations
    assert (
        repo.is_valid_transaction(
            "0xabc", require_confirmations=True, min_confirmations=6
        )
        is True
    )
    assert (
        repo.is_valid_transaction(
            "0xabc", require_confirmations=True, min_confirmations=8
        )
        is False
    )

    # Test valid without confirmation requirement
    assert repo.is_valid_transaction("0xabc", require_confirmations=False) is True


def test_web3_transaction_repository_get_transaction_transfers_eth():
    web3 = MagicMock()
    tx = MagicMock()
    tx.input = "0x"
    tx.value = 123
    tx.to = "0xto"
    tx.__getitem__.side_effect = lambda k: {"from": "0xfrom", "to": "0xto"}[k]
    tx.hash.hex.return_value = "0xhash"
    web3.eth.get_transaction.return_value = tx
    # Receipt sem logs de token
    receipt = MagicMock()
    receipt.logs = []
    web3.eth.get_transaction_receipt.return_value = receipt
    repo = Web3TransactionRepository(web3)
    transfers = repo.get_transaction_transfers("0xabc")
    assert len(transfers) == 1
    assert transfers[0]["asset"] == "eth"
    assert transfers[0]["from"] == "0xfrom"
    assert transfers[0]["to"] == "0xto"
    assert transfers[0]["value"] == 123


def test_web3_transaction_repository_get_transaction_transfers_token():
    web3 = MagicMock()
    tx = MagicMock()
    tx.input = "0xa9059cbb..."
    tx.value = 0
    tx.to = "0xcontract"
    tx.__getitem__.side_effect = lambda k: {"from": "0xfrom", "to": "0xcontract"}[k]
    tx.hash.hex.return_value = "0xhash"
    web3.eth.get_transaction.return_value = tx
    # Receipt com um log de token
    log = MagicMock()
    topic0 = MagicMock()
    # Fix: Return without 0x prefix to match the implementation
    topic0.hex.return_value = (
        "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    )
    topic1 = MagicMock()
    topic1.hex.return_value = (
        "0000000000000000000000001111111111111111111111111111111111111111"
    )
    topic2 = MagicMock()
    topic2.hex.return_value = (
        "0000000000000000000000002222222222222222222222222222222222222222"
    )
    log.topics = [topic0, topic1, topic2]
    # Fix: Return bytes instead of hex string to match real Web3 behavior
    log.data = bytes.fromhex("03e8")  # 1000 em hexadecimal como bytes (pad com zero)
    receipt = MagicMock()
    receipt.logs = [log]
    web3.eth.get_transaction_receipt.return_value = receipt
    repo = Web3TransactionRepository(web3)
    transfers = repo.get_transaction_transfers("0xabc")
    assert len(transfers) == 1
    assert transfers[0]["asset"] == "token"
    assert (
        transfers[0]["from"]
        .lower()
        .endswith("1111111111111111111111111111111111111111")
    )
    assert (
        transfers[0]["to"].lower().endswith("2222222222222222222222222222222222222222")
    )
    assert transfers[0]["value"] == 1000


def test_web3_transaction_repository_get_transaction_transfers_multiple_tokens():
    web3 = MagicMock()
    tx = MagicMock()
    tx.input = "0xa9059cbb..."
    tx.value = 0
    tx.to = "0xcontract"
    tx.__getitem__.side_effect = lambda k: {"from": "0xfrom", "to": "0xcontract"}[k]
    tx.hash.hex.return_value = "0xhash"
    web3.eth.get_transaction.return_value = tx
    # Receipt com dois logs de token
    log1 = MagicMock()
    topic0_1 = MagicMock()
    # Fix: Return without 0x prefix to match the implementation
    topic0_1.hex.return_value = (
        "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    )
    topic1_1 = MagicMock()
    topic1_1.hex.return_value = (
        "000000000000000000000000aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )
    topic2_1 = MagicMock()
    topic2_1.hex.return_value = (
        "000000000000000000000000bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    )
    log1.topics = [topic0_1, topic1_1, topic2_1]
    # Fix: Return bytes instead of hex string to match real Web3 behavior
    log1.data = bytes.fromhex("01f4")  # 500 em hexadecimal como bytes (pad com zero)
    log2 = MagicMock()
    topic0_2 = MagicMock()
    # Fix: Return without 0x prefix to match the implementation
    topic0_2.hex.return_value = (
        "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    )
    topic1_2 = MagicMock()
    topic1_2.hex.return_value = (
        "000000000000000000000000cccccccccccccccccccccccccccccccccccccccc"
    )
    topic2_2 = MagicMock()
    topic2_2.hex.return_value = (
        "000000000000000000000000dddddddddddddddddddddddddddddddddddddddd"
    )
    log2.topics = [topic0_2, topic1_2, topic2_2]
    # Fix: Return bytes instead of hex string to match real Web3 behavior
    log2.data = bytes.fromhex("05dc")  # 1500 em hexadecimal como bytes (pad com zero)
    receipt = MagicMock()
    receipt.logs = [log1, log2]
    web3.eth.get_transaction_receipt.return_value = receipt
    repo = Web3TransactionRepository(web3)
    transfers = repo.get_transaction_transfers("0xabc")
    assert len(transfers) == 2
    assert (
        transfers[0]["from"]
        .lower()
        .endswith("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    )
    assert (
        transfers[0]["to"].lower().endswith("bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb")
    )
    assert transfers[0]["value"] == 500
    assert (
        transfers[1]["from"]
        .lower()
        .endswith("cccccccccccccccccccccccccccccccccccccccc")
    )
    assert (
        transfers[1]["to"].lower().endswith("dddddddddddddddddddddddddddddddddddddddd")
    )
    assert transfers[1]["value"] == 1500
