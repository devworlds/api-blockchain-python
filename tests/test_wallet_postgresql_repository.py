import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from app.domain.wallet.entity import Wallet
from app.infrastructure.db.wallet.postgresql_repository import (
    EthereumWalletService,
    HashiCorpVaultService,
    PostgreSQLWalletRepository,
)


class TestHashiCorpVaultService:
    """Test HashiCorp Vault Service"""

    @pytest.fixture
    def mock_hvac_client(self):
        """Create mock HVAC client"""
        with patch("hvac.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_client.is_authenticated.return_value = True
            mock_client.secrets.kv.v2.create_or_update_secret.return_value = None
            mock_client.secrets.kv.v2.read_secret_version.return_value = {
                "data": {"data": {"private_key": "0x123abc"}}
            }
            yield mock_client

    def test_vault_service_init_authenticated(self, mock_hvac_client):
        """Test Vault service initialization when authenticated"""
        service = HashiCorpVaultService("http://vault:8200", "test-token")

        assert service.secret_path == "eth_wallets"
        mock_hvac_client.is_authenticated.assert_called_once()

    def test_vault_service_init_not_authenticated(self, mock_hvac_client):
        """Test Vault service initialization when not authenticated"""
        mock_hvac_client.is_authenticated.return_value = False

        service = HashiCorpVaultService("http://vault:8200", "invalid-token")

        assert service.secret_path == "eth_wallets"
        mock_hvac_client.is_authenticated.assert_called_once()

    def test_vault_service_custom_secret_path(self, mock_hvac_client):
        """Test Vault service with custom secret path"""
        service = HashiCorpVaultService(
            "http://vault:8200", "test-token", "custom_path"
        )

        assert service.secret_path == "custom_path"

    def test_store_private_key_success(self, mock_hvac_client):
        """Test storing private key successfully"""
        service = HashiCorpVaultService("http://vault:8200", "test-token")

        service.store_private_key("wallet_123", "0x123abc")

        mock_hvac_client.secrets.kv.v2.create_or_update_secret.assert_called_once_with(
            path="eth_wallets/wallet_123", secret={"private_key": "0x123abc"}
        )

    def test_store_private_key_error(self, mock_hvac_client):
        """Test storing private key with error"""
        mock_hvac_client.secrets.kv.v2.create_or_update_secret.side_effect = Exception(
            "Vault error"
        )
        service = HashiCorpVaultService("http://vault:8200", "test-token")

        with pytest.raises(Exception, match="Vault error"):
            service.store_private_key("wallet_123", "0x123abc")

    def test_get_private_key_success(self, mock_hvac_client):
        """Test retrieving private key successfully"""
        service = HashiCorpVaultService("http://vault:8200", "test-token")

        result = service.get_private_key("wallet_123")

        assert result == "0x123abc"
        mock_hvac_client.secrets.kv.v2.read_secret_version.assert_called_once_with(
            path="eth_wallets/wallet_123"
        )

    def test_get_private_key_not_found(self, mock_hvac_client):
        """Test retrieving private key when not found"""
        mock_hvac_client.secrets.kv.v2.read_secret_version.side_effect = Exception(
            "InvalidPath"
        )
        service = HashiCorpVaultService("http://vault:8200", "test-token")

        with pytest.raises(ValueError, match="Private key not found in Vault"):
            service.get_private_key("wallet_123")

    def test_get_private_key_404_error(self, mock_hvac_client):
        """Test retrieving private key with 404 error"""
        mock_hvac_client.secrets.kv.v2.read_secret_version.side_effect = Exception(
            "404"
        )
        service = HashiCorpVaultService("http://vault:8200", "test-token")

        with pytest.raises(ValueError, match="Private key not found in Vault"):
            service.get_private_key("wallet_123")

    def test_get_private_key_general_error(self, mock_hvac_client):
        """Test retrieving private key with general error"""
        mock_hvac_client.secrets.kv.v2.read_secret_version.side_effect = Exception(
            "Network error"
        )
        service = HashiCorpVaultService("http://vault:8200", "test-token")

        with pytest.raises(Exception, match="Network error"):
            service.get_private_key("wallet_123")


class TestEthereumWalletService:
    """Test Ethereum Wallet Service"""

    @pytest.fixture
    def mock_account(self):
        """Create mock Ethereum account"""
        with patch(
            "app.infrastructure.db.wallet.postgresql_repository.Account"
        ) as mock_account_class:
            mock_account = Mock()
            mock_account.address = "0x742d35Cc6634C0532925a3b8D0C9964b8d7B1234"
            mock_account.key.hex.return_value = "0x123abc456def"
            mock_account_class.create.return_value = mock_account
            mock_account_class.from_key.return_value = mock_account

            # Mock signed transaction
            mock_signed = Mock()
            mock_signed.raw_transaction.hex.return_value = "0xsigned_tx_data"
            mock_account.sign_transaction.return_value = mock_signed

            yield mock_account_class, mock_account

    def test_create_wallet_success(self, mock_account):
        """Test creating wallet successfully"""
        mock_account_class, mock_account_instance = mock_account
        service = EthereumWalletService()

        result = service.create_wallet()

        assert result == {
            "address": "0x742d35Cc6634C0532925a3b8D0C9964b8d7B1234",
            "private_key": "0x123abc456def",
        }
        mock_account_class.create.assert_called_once()

    def test_create_wallet_error(self, mock_account):
        """Test creating wallet with error"""
        mock_account_class, mock_account_instance = mock_account
        mock_account_class.create.side_effect = Exception("Account creation failed")
        service = EthereumWalletService()

        with pytest.raises(Exception, match="Account creation failed"):
            service.create_wallet()

    def test_sign_transaction_success(self, mock_account):
        """Test signing transaction successfully"""
        mock_account_class, mock_account_instance = mock_account
        service = EthereumWalletService()

        transaction = {
            "to": "0x742d35Cc6634C0532925a3b8D0C9964b8d7B1234",
            "value": 1000000000000000000,
            "gas": 21000,
            "gasPrice": 20000000000,
            "nonce": 0,
        }

        result = service.sign_transaction("0x123abc", transaction)

        assert result == "0xsigned_tx_data"
        mock_account_class.from_key.assert_called_once_with("0x123abc")
        mock_account_instance.sign_transaction.assert_called_once_with(transaction)

    def test_sign_transaction_error(self, mock_account):
        """Test signing transaction with error"""
        mock_account_class, mock_account_instance = mock_account
        mock_account_instance.sign_transaction.side_effect = Exception("Signing failed")
        service = EthereumWalletService()

        transaction = {"to": "0x123", "value": 1000}

        with pytest.raises(Exception, match="Signing failed"):
            service.sign_transaction("0x123abc", transaction)


class TestPostgreSQLWalletRepository:
    """Test PostgreSQL Wallet Repository"""

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
        return PostgreSQLWalletRepository(pool), conn

    @pytest.fixture
    def sample_wallet(self):
        """Create sample wallet entity"""
        return Wallet(
            address="0x742d35Cc6634C0532925a3b8D0C9964b8d7B1234",
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

            repo = await PostgreSQLWalletRepository.create("postgresql://test")

            assert isinstance(repo, PostgreSQLWalletRepository)
            assert repo._pool == mock_pool
            mock_create_pool.assert_called_once_with(dsn="postgresql://test")

    @pytest.mark.asyncio
    async def test_save_wallet_success(self, repository, sample_wallet):
        """Test saving wallet successfully"""
        repo, conn = repository

        await repo.save_wallet(sample_wallet)

        conn.execute.assert_called_once()
        call_args = conn.execute.call_args[0]
        assert "INSERT INTO wallets" in call_args[0]
        assert "ON CONFLICT (address) DO NOTHING" in call_args[0]
        assert call_args[1] == sample_wallet.address

    @pytest.mark.asyncio
    async def test_save_wallet_error(self, repository, sample_wallet):
        """Test saving wallet with database error"""
        repo, conn = repository
        conn.execute.side_effect = Exception("Database error")

        with pytest.raises(Exception, match="Database error"):
            await repo.save_wallet(sample_wallet)

    @pytest.mark.asyncio
    async def test_get_wallet_by_address_found(self, repository, sample_wallet):
        """Test getting wallet by address when found"""
        repo, conn = repository

        # Mock database row
        mock_row = {
            "address": sample_wallet.address,
            "created_at": sample_wallet.created_at,
            "updated_at": sample_wallet.updated_at,
            "deleted_at": sample_wallet.deleted_at,
        }
        conn.fetchrow.return_value = mock_row

        result = await repo.get_wallet_by_address(sample_wallet.address)

        assert isinstance(result, Wallet)
        assert result.address == sample_wallet.address
        conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_wallet_by_address_not_found(self, repository):
        """Test getting wallet by address when not found"""
        repo, conn = repository
        conn.fetchrow.return_value = None

        result = await repo.get_wallet_by_address("0x999")

        assert result is None
        conn.fetchrow.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_wallet_by_address_error(self, repository):
        """Test getting wallet by address with database error"""
        repo, conn = repository
        conn.fetchrow.side_effect = Exception("Database error")

        with pytest.raises(Exception, match="Database error"):
            await repo.get_wallet_by_address("0x123")

    @pytest.mark.asyncio
    async def test_list_wallets_success(self, repository, sample_wallet):
        """Test listing wallets successfully"""
        repo, conn = repository

        # Mock database rows
        mock_row = {
            "address": sample_wallet.address,
            "created_at": sample_wallet.created_at,
            "updated_at": sample_wallet.updated_at,
            "deleted_at": sample_wallet.deleted_at,
        }
        conn.fetch.return_value = [mock_row, mock_row]

        result = await repo.list_wallets()

        assert len(result) == 2
        assert all(isinstance(wallet, Wallet) for wallet in result)
        conn.fetch.assert_called_once()
        call_args = conn.fetch.call_args[0]
        assert (
            "SELECT address, created_at, updated_at, deleted_at FROM wallets"
            in call_args[0]
        )

    @pytest.mark.asyncio
    async def test_list_wallets_empty(self, repository):
        """Test listing wallets when empty"""
        repo, conn = repository
        conn.fetch.return_value = []

        result = await repo.list_wallets()

        assert result == []
        conn.fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_wallets_error(self, repository):
        """Test listing wallets with database error"""
        repo, conn = repository
        conn.fetch.side_effect = Exception("Database error")

        with pytest.raises(Exception, match="Database error"):
            await repo.list_wallets()


class TestWalletRepositoryIntegration:
    """Integration tests for wallet repository components"""

    @pytest.mark.asyncio
    async def test_vault_service_with_metrics_context(self):
        """Test vault service operations with metrics context"""
        with patch("hvac.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_client.is_authenticated.return_value = True

            with patch(
                "app.infrastructure.db.wallet.postgresql_repository.MetricsContext"
            ) as mock_metrics:
                service = HashiCorpVaultService("http://vault:8200", "test-token")
                service.store_private_key("wallet_123", "0x123abc")

                mock_metrics.assert_called_with("store_private_key", "vault")

    @pytest.mark.asyncio
    async def test_ethereum_service_with_metrics_context(self):
        """Test Ethereum service operations with metrics context"""
        with patch(
            "app.infrastructure.db.wallet.postgresql_repository.Account"
        ) as mock_account_class:
            mock_account = Mock()
            mock_account.address = "0x742d35Cc6634C0532925a3b8D0C9964b8d7B1234"
            mock_account.key.hex.return_value = "0x123abc456def"
            mock_account_class.create.return_value = mock_account

            with patch(
                "app.infrastructure.db.wallet.postgresql_repository.MetricsContext"
            ) as mock_metrics:
                service = EthereumWalletService()
                service.create_wallet()

                mock_metrics.assert_called_with("create_wallet", "wallet")

    @pytest.mark.asyncio
    async def test_repository_with_metrics_context(self):
        """Test repository operations with metrics context"""
        pool = Mock()
        conn = AsyncMock()

        async_context = AsyncMock()
        async_context.__aenter__ = AsyncMock(return_value=conn)
        async_context.__aexit__ = AsyncMock(return_value=None)
        pool.acquire.return_value = async_context

        with patch(
            "app.infrastructure.db.wallet.postgresql_repository.MetricsContext"
        ) as mock_metrics:
            repo = PostgreSQLWalletRepository(pool)
            wallet = Wallet(
                address="0x123",
                created_at=datetime.datetime.now(),
                updated_at=datetime.datetime.now(),
                deleted_at=None,
            )

            await repo.save_wallet(wallet)

            mock_metrics.assert_called_with("save_wallet", "database")
