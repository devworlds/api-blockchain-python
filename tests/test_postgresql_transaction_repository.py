import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.domain.transaction.entity import Transaction as TransactionEntity
from app.infrastructure.db.transaction.postgresql_repository import (
    PostgreSQLTransactionRepository,
)


class TestPostgreSQLTransactionRepository:
    """Test PostgreSQL Transaction Repository"""

    @pytest.fixture
    def mock_pool(self):
        """Create mock connection pool"""
        pool = Mock()
        conn = AsyncMock()

        # Mock the async context manager
        async_context = AsyncMock()
        async_context.__aenter__ = AsyncMock(return_value=conn)
        async_context.__aexit__ = AsyncMock(return_value=None)
        pool.acquire.return_value = async_context

        return pool, conn

    @pytest.fixture
    def repository(self, mock_pool):
        """Create repository instance with mock pool"""
        pool, conn = mock_pool
        return PostgreSQLTransactionRepository(pool), conn

    @pytest.fixture
    def sample_transaction(self):
        """Create sample transaction entity"""
        return TransactionEntity(
            hash="0x123abc",
            asset="ETH",
            address_from="0xfrom",
            address_to="0xto",
            value=1000000000000000000,
            is_token=False,
            type="withdraw",
            status="pending",
            effective_fee=21000000000000000,
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
            deleted_at=None,
        )

    @pytest.mark.asyncio
    async def test_create_repository(self):
        """Test repository creation with connection pool"""
        with patch("asyncpg.create_pool") as mock_create_pool:
            mock_pool = Mock()

            # Make the mock awaitable
            async def mock_create():
                return mock_pool

            mock_create_pool.return_value = mock_create()

            repo = await PostgreSQLTransactionRepository.create("postgresql://test")

            assert isinstance(repo, PostgreSQLTransactionRepository)
            assert repo._pool == mock_pool
            mock_create_pool.assert_called_once_with(dsn="postgresql://test")

    @pytest.mark.asyncio
    async def test_save_transaction(self, repository, sample_transaction):
        """Test saving a transaction"""
        repo, conn = repository

        await repo.save_transaction(sample_transaction)

        conn.execute.assert_called_once()
        call_args = conn.execute.call_args[0]
        assert "INSERT INTO transactions" in call_args[0]
        assert "ON CONFLICT (hash) DO NOTHING" in call_args[0]
        assert call_args[1] == sample_transaction.hash
        assert call_args[2] == sample_transaction.asset

    @pytest.mark.asyncio
    async def test_update_transaction_status_success(self, repository):
        """Test updating transaction status successfully"""
        repo, conn = repository
        conn.execute.return_value = "UPDATE 1"

        result = await repo.update_transaction_status("0x123", "confirmed")

        assert result is True
        conn.execute.assert_called_once()
        call_args = conn.execute.call_args[0]
        assert "UPDATE transactions SET status" in call_args[0]
        assert call_args[1] == "confirmed"
        assert call_args[3] == "0x123"

    @pytest.mark.asyncio
    async def test_update_transaction_status_not_found(self, repository):
        """Test updating transaction status when transaction not found"""
        repo, conn = repository
        conn.execute.return_value = "UPDATE 0"

        result = await repo.update_transaction_status("0x999", "confirmed")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_transaction_by_hash_found(self, repository, sample_transaction):
        """Test getting transaction by hash when found"""
        repo, conn = repository

        # Mock database row
        mock_row = {
            "hash": sample_transaction.hash,
            "asset": sample_transaction.asset,
            "address_from": sample_transaction.address_from,
            "address_to": sample_transaction.address_to,
            "value": sample_transaction.value,
            "is_token": sample_transaction.is_token,
            "type": sample_transaction.type,
            "status": sample_transaction.status,
            "effective_fee": sample_transaction.effective_fee,
            "created_at": sample_transaction.created_at,
            "updated_at": sample_transaction.updated_at,
            "deleted_at": sample_transaction.deleted_at,
        }
        conn.fetchrow.return_value = mock_row

        result = await repo.get_transaction_by_hash("0x123abc")

        assert isinstance(result, TransactionEntity)
        assert result.hash == sample_transaction.hash
        assert result.asset == sample_transaction.asset
        assert result.status == sample_transaction.status
        conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_transaction_by_hash_not_found(self, repository):
        """Test getting transaction by hash when not found"""
        repo, conn = repository
        conn.fetchrow.return_value = None

        result = await repo.get_transaction_by_hash("0x999")

        assert result is None
        conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_transactions(self, repository, sample_transaction):
        """Test listing transactions with pagination"""
        repo, conn = repository

        # Mock database rows
        mock_row = {
            "hash": sample_transaction.hash,
            "asset": sample_transaction.asset,
            "address_from": sample_transaction.address_from,
            "address_to": sample_transaction.address_to,
            "value": sample_transaction.value,
            "is_token": sample_transaction.is_token,
            "type": sample_transaction.type,
            "status": sample_transaction.status,
            "effective_fee": sample_transaction.effective_fee,
            "created_at": sample_transaction.created_at,
            "updated_at": sample_transaction.updated_at,
            "deleted_at": sample_transaction.deleted_at,
        }
        conn.fetch.return_value = [mock_row, mock_row]

        result = await repo.list_transactions(limit=10, offset=5)

        assert len(result) == 2
        assert all(isinstance(tx, TransactionEntity) for tx in result)
        conn.fetch.assert_called_once()
        call_args = conn.fetch.call_args[0]
        assert "ORDER BY created_at DESC LIMIT" in call_args[0]
        assert call_args[1] == 10  # limit
        assert call_args[2] == 5  # offset

    @pytest.mark.asyncio
    async def test_list_transactions_default_pagination(self, repository):
        """Test listing transactions with default pagination"""
        repo, conn = repository
        conn.fetch.return_value = []

        result = await repo.list_transactions()

        assert result == []
        call_args = conn.fetch.call_args[0]
        assert call_args[1] == 100  # default limit
        assert call_args[2] == 0  # default offset

    @pytest.mark.asyncio
    async def test_get_pending_transactions(self, repository, sample_transaction):
        """Test getting pending transactions"""
        repo, conn = repository

        # Mock database row
        mock_row = {
            "hash": sample_transaction.hash,
            "asset": sample_transaction.asset,
            "address_from": sample_transaction.address_from,
            "address_to": sample_transaction.address_to,
            "value": sample_transaction.value,
            "is_token": sample_transaction.is_token,
            "type": sample_transaction.type,
            "status": "pending",
            "effective_fee": sample_transaction.effective_fee,
            "created_at": sample_transaction.created_at,
            "updated_at": sample_transaction.updated_at,
            "deleted_at": sample_transaction.deleted_at,
        }
        conn.fetch.return_value = [mock_row]

        result = await repo.get_pending_transactions(max_age_hours=12)

        assert len(result) == 1
        assert result[0].status == "pending"
        conn.fetch.assert_called_once()
        call_args = conn.fetch.call_args[0]
        assert "status IN ('pending', 'confirming')" in call_args[0]
        assert call_args[1] == 12  # max_age_hours

    @pytest.mark.asyncio
    async def test_get_pending_transactions_default_age(self, repository):
        """Test getting pending transactions with default age"""
        repo, conn = repository
        conn.fetch.return_value = []

        result = await repo.get_pending_transactions()

        assert result == []
        call_args = conn.fetch.call_args[0]
        assert call_args[1] == 24  # default max_age_hours

    @pytest.mark.asyncio
    async def test_get_transaction_with_confirmations_found(
        self, repository, sample_transaction
    ):
        """Test getting transaction with confirmations when found"""
        repo, conn = repository

        # Mock the get_transaction_by_hash method
        repo.get_transaction_by_hash = AsyncMock(return_value=sample_transaction)

        # Mock web3_repo
        mock_web3_repo = Mock()
        mock_web3_repo.get_transaction_confirmations.return_value = 15

        result = await repo.get_transaction_with_confirmations("0x123", mock_web3_repo)

        assert result is not None
        assert result["hash"] == sample_transaction.hash
        assert result["confirmations"] == 15
        assert result["is_confirmed"] is True
        assert result["status"] == sample_transaction.status
        mock_web3_repo.get_transaction_confirmations.assert_called_once_with("0x123")

    @pytest.mark.asyncio
    async def test_get_transaction_with_confirmations_not_found(self, repository):
        """Test getting transaction with confirmations when not found"""
        repo, conn = repository

        # Mock the get_transaction_by_hash method
        repo.get_transaction_by_hash = AsyncMock(return_value=None)

        mock_web3_repo = Mock()

        result = await repo.get_transaction_with_confirmations("0x999", mock_web3_repo)

        assert result is None
        mock_web3_repo.get_transaction_confirmations.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_transaction_with_confirmations_web3_error(
        self, repository, sample_transaction
    ):
        """Test getting transaction with confirmations when web3 fails"""
        repo, conn = repository

        # Mock the get_transaction_by_hash method
        repo.get_transaction_by_hash = AsyncMock(return_value=sample_transaction)

        # Mock web3_repo to raise exception
        mock_web3_repo = Mock()
        mock_web3_repo.get_transaction_confirmations.side_effect = Exception(
            "Web3 error"
        )

        result = await repo.get_transaction_with_confirmations("0x123", mock_web3_repo)

        assert result is not None
        assert result["confirmations"] == 0  # Default when web3 fails
        assert result["is_confirmed"] is False
        mock_web3_repo.get_transaction_confirmations.assert_called_once_with("0x123")
