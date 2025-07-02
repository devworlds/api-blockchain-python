import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

import pytest
from fastapi import HTTPException

from app.application.v1.transaction.schemas import TransactionOnChainRequest
from app.application.v1.transaction.usecase import (
    CreateOnChainTransaction,
    GetTransactionHash,
    ListTransactions,
)
from app.domain.transaction.entity import Transaction as TransactionEntity
from app.domain.wallet.entity import Wallet


class TestGetTransactionHashErrors:
    """Test error scenarios for GetTransactionHash usecase"""

    @pytest.fixture
    def mock_repositories(self):
        """Create mock repositories"""
        web3_repo = Mock()
        wallet_repo = AsyncMock()
        db_repo = AsyncMock()
        return web3_repo, wallet_repo, db_repo

    @pytest.fixture
    def usecase(self, mock_repositories):
        """Create GetTransactionHash usecase with mocks"""
        web3_repo, wallet_repo, db_repo = mock_repositories
        return GetTransactionHash(
            tx_hash="0x123abc",
            web3_repo=web3_repo,
            wallet_repo=wallet_repo,
            db_repo=db_repo,
            min_confirmations=12,
        )

    @pytest.mark.asyncio
    async def test_validate_destination_address_error(self, usecase):
        """Test validate_destination_address with database error"""
        usecase.wallet_repo.get_wallet_by_address.side_effect = Exception(
            "Database error"
        )

        result = await usecase.validate_destination_address("0x123")

        assert result is False
        usecase.wallet_repo.get_wallet_by_address.assert_called_once_with("0x123")

    @pytest.mark.asyncio
    async def test_execute_transaction_not_found(self, usecase):
        """Test execute when transaction is not found"""
        usecase.web3_repo.get_transaction.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await usecase.execute("0x123abc")

        assert exc_info.value.status_code == 404
        assert "Transaction not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_execute_web3_error(self, usecase):
        """Test execute with Web3 error"""
        usecase.web3_repo.get_transaction.side_effect = Exception(
            "Web3 connection error"
        )

        with pytest.raises(Exception, match="Web3 connection error"):
            await usecase.execute("0x123abc")

    @pytest.mark.asyncio
    async def test_execute_token_transaction_error(self, usecase):
        """Test execute with token transaction processing error"""
        # Mock transaction data for token transaction
        tx_data = {
            "hash": "0x123abc",
            "from": "0xfrom123",
            "to": "0xto123",
            "value": 0,
            "input": "0xa9059cbb000000000000000000000000",  # transfer function signature
        }

        usecase.web3_repo.get_transaction.return_value = tx_data
        usecase.web3_repo.get_transaction_transfers.side_effect = Exception(
            "Token transfer parsing error"
        )
        usecase.web3_repo.get_transaction_confirmations.return_value = 15
        usecase.wallet_repo.get_wallet_by_address.return_value = None

        with pytest.raises(Exception, match="Token transfer parsing error"):
            await usecase.execute("0x123abc")

    @pytest.mark.asyncio
    async def test_execute_database_save_error(self, usecase):
        """Test execute with database save error"""
        # Mock transaction data
        tx_data = {
            "hash": "0x123abc",
            "from": "0xfrom123",
            "to": "0xto123",
            "value": 1000000000000000000,  # 1 ETH
            "input": "0x",
        }

        # Mock wallet exists (to trigger save)
        mock_wallet = Wallet(
            address="0xto123",
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
            deleted_at=None,
        )

        usecase.web3_repo.get_transaction.return_value = tx_data
        usecase.web3_repo.get_transaction_confirmations.return_value = 15
        usecase.wallet_repo.get_wallet_by_address.side_effect = [
            None,
            mock_wallet,
        ]  # from=None, to=wallet
        usecase.db_repo.get_transaction_by_hash.return_value = None
        usecase.db_repo.save_transaction.side_effect = Exception("Database save error")

        with pytest.raises(Exception, match="Database save error"):
            await usecase.execute("0x123abc")

    @pytest.mark.asyncio
    async def test_execute_confirmations_error(self, usecase):
        """Test execute with confirmations check error"""
        tx_data = {
            "hash": "0x123abc",
            "from": "0xfrom123",
            "to": "0xto123",
            "value": 1000000000000000000,
            "input": "0x",
        }

        usecase.web3_repo.get_transaction.return_value = tx_data
        usecase.web3_repo.get_transaction_confirmations.side_effect = Exception(
            "Confirmations check failed"
        )

        with pytest.raises(Exception, match="Confirmations check failed"):
            await usecase.execute("0x123abc")

    @pytest.mark.asyncio
    async def test_execute_internal_transfer_scenario(self, usecase):
        """Test execute with internal transfer (both addresses are ours)"""
        tx_data = {
            "hash": "0x123abc",
            "from": "0xfrom123",
            "to": "0xto123",
            "value": 1000000000000000000,
            "input": "0x",
        }

        # Both wallets exist
        mock_wallet_from = Wallet(
            address="0xfrom123",
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
            deleted_at=None,
        )
        mock_wallet_to = Wallet(
            address="0xto123",
            created_at=datetime.datetime.now(),
            updated_at=datetime.datetime.now(),
            deleted_at=None,
        )

        usecase.web3_repo.get_transaction.return_value = tx_data
        usecase.web3_repo.get_transaction_confirmations.return_value = 15
        usecase.wallet_repo.get_wallet_by_address.side_effect = [
            mock_wallet_from,
            mock_wallet_to,
        ]
        usecase.db_repo.get_transaction_by_hash.return_value = None

        result = await usecase.execute("0x123abc")

        # Should detect internal transfer and save as withdraw
        assert result["is_destination_our_wallet"] is True
        usecase.db_repo.save_transaction.assert_called_once()

        # Check transaction type is withdraw for internal transfers
        saved_tx = usecase.db_repo.save_transaction.call_args[0][0]
        assert saved_tx.type == "withdraw"


class TestCreateOnChainTransactionErrors:
    """Test error scenarios for CreateOnChainTransaction usecase"""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies"""
        web3_repo = Mock()
        db_repo = AsyncMock()
        vault_service = Mock()
        wallet_service = Mock()

        # Mock Web3 instance
        mock_web3 = Mock()
        web3_repo.web3 = mock_web3

        return web3_repo, db_repo, vault_service, wallet_service, mock_web3

    @pytest.fixture
    def usecase(self, mock_dependencies):
        """Create CreateOnChainTransaction usecase with mocks"""
        web3_repo, db_repo, vault_service, wallet_service, _ = mock_dependencies
        return CreateOnChainTransaction(
            web3_repo=web3_repo,
            db_repo=db_repo,
            vault_service=vault_service,
            wallet_service=wallet_service,
        )

    @pytest.fixture
    def valid_request(self):
        """Create valid transaction request"""
        return TransactionOnChainRequest(
            address_from="0x742d35Cc6634C0532925a3b8D0C9964b8d7B1234",
            address_to="0xC2DBAAF3E4944EDE0DEF95D9D1A129AED2F74587",
            asset="ETH",
            value=1.0,
            contract_address=None,
        )

    @pytest.mark.asyncio
    async def test_execute_missing_required_fields(self, usecase):
        """Test execute with missing required fields"""
        # Test missing address_from
        request = TransactionOnChainRequest(
            address_from="",
            address_to="0xC2DBAAF3E4944EDE0DEF95D9D1A129AED2F74587",
            asset="ETH",
            value=1.0,
        )

        with pytest.raises(HTTPException) as exc_info:
            await usecase.execute(request)

        assert exc_info.value.status_code == 400
        assert "Missing required fields" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_execute_zero_eth_balance(
        self, usecase, valid_request, mock_dependencies
    ):
        """Test execute with zero ETH balance"""
        _, _, _, _, mock_web3 = mock_dependencies

        # Mock Web3 responses
        mock_web3.to_checksum_address.side_effect = lambda x: x
        mock_web3.eth.get_transaction_count.return_value = 1
        mock_web3.eth.chain_id = 1
        mock_web3.eth.get_balance.return_value = 0  # Zero balance

        with pytest.raises(HTTPException) as exc_info:
            await usecase.execute(valid_request)

        assert exc_info.value.status_code == 400
        assert "Insufficient ETH balance for gas fees" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_execute_insufficient_eth_balance(
        self, usecase, valid_request, mock_dependencies
    ):
        """Test execute with insufficient ETH balance"""
        _, _, _, _, mock_web3 = mock_dependencies

        # Mock Web3 responses
        mock_web3.to_checksum_address.side_effect = lambda x: x
        mock_web3.eth.get_transaction_count.return_value = 1
        mock_web3.eth.chain_id = 1
        mock_web3.eth.get_balance.return_value = 100000000000000000  # 0.1 ETH
        mock_web3.eth.gas_price = 20000000000  # 20 gwei
        mock_web3.eth.max_priority_fee = 2000000000  # 2 gwei

        # Request for 1 ETH but only have 0.1 ETH
        with pytest.raises(HTTPException) as exc_info:
            await usecase.execute(valid_request)

        assert exc_info.value.status_code == 400
        assert "Insufficient ETH balance" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_execute_token_missing_contract_address(
        self, usecase, mock_dependencies
    ):
        """Test execute with token transaction missing contract address"""
        request = TransactionOnChainRequest(
            address_from="0x742d35Cc6634C0532925a3b8D0C9964b8d7B1234",
            address_to="0xC2DBAAF3E4944EDE0DEF95D9D1A129AED2F74587",
            asset="USDT",
            value=100.0,
            contract_address=None,  # Missing contract address
        )

        _, _, _, _, mock_web3 = mock_dependencies

        # Mock sufficient ETH balance
        mock_web3.to_checksum_address.side_effect = lambda x: x
        mock_web3.eth.get_transaction_count.return_value = 1
        mock_web3.eth.chain_id = 1
        mock_web3.eth.get_balance.return_value = 1000000000000000000  # 1 ETH
        mock_web3.eth.gas_price = 20000000000
        mock_web3.eth.max_priority_fee = 2000000000

        with pytest.raises(HTTPException) as exc_info:
            await usecase.execute(request)

        assert exc_info.value.status_code == 400
        assert "contract_address is required for tokens" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_execute_token_insufficient_gas(self, usecase, mock_dependencies):
        """Test execute with token transaction insufficient gas"""
        request = TransactionOnChainRequest(
            address_from="0x742d35Cc6634C0532925a3b8D0C9964b8d7B1234",
            address_to="0xC2DBAAF3E4944EDE0DEF95D9D1A129AED2F74587",
            asset="USDT",
            value=100.0,
            contract_address="0xdAC17F958D2ee523a2206206994597C13D831ec7",
        )

        _, _, _, _, mock_web3 = mock_dependencies

        # Mock responses
        mock_web3.to_checksum_address.side_effect = lambda x: x
        mock_web3.eth.get_transaction_count.return_value = 1
        mock_web3.eth.chain_id = 1
        mock_web3.eth.get_balance.return_value = (
            1000000000000000  # 0.001 ETH (very low)
        )
        mock_web3.eth.gas_price = 100000000000  # 100 gwei (very high gas price)
        mock_web3.eth.max_priority_fee = 10000000000  # 10 gwei

        # Mock contract and gas estimation
        mock_contract = Mock()
        mock_contract.functions.transfer.return_value.build_transaction.return_value = {
            "data": "0xabcd"
        }
        mock_web3.eth.contract.return_value = mock_contract
        mock_web3.eth.estimate_gas.return_value = 200000  # Very high gas limit

        with pytest.raises(HTTPException) as exc_info:
            await usecase.execute(request)

        assert exc_info.value.status_code == 400
        assert "Insufficient ETH balance for gas fees" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_execute_vault_key_not_found(
        self, usecase, valid_request, mock_dependencies
    ):
        """Test execute with vault key not found"""
        _, _, vault_service, _, mock_web3 = mock_dependencies

        # Mock successful Web3 setup
        mock_web3.to_checksum_address.side_effect = lambda x: x
        mock_web3.eth.get_transaction_count.return_value = 1
        mock_web3.eth.chain_id = 1
        mock_web3.eth.get_balance.return_value = 10000000000000000000  # 10 ETH
        mock_web3.eth.gas_price = 20000000000
        mock_web3.eth.max_priority_fee = 2000000000

        # Mock vault error
        vault_service.get_private_key.side_effect = ValueError(
            "Private key not found in Vault for wallet 0x742d35Cc6634C0532925a3b8D0C9964b8d7B1234"
        )

        with pytest.raises(HTTPException) as exc_info:
            await usecase.execute(valid_request)

        assert exc_info.value.status_code == 400
        assert "Private key not found in Vault" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_execute_signing_error(
        self, usecase, valid_request, mock_dependencies
    ):
        """Test execute with transaction signing error"""
        _, _, vault_service, _, mock_web3 = mock_dependencies

        # Mock successful Web3 setup
        mock_web3.to_checksum_address.side_effect = lambda x: x
        mock_web3.eth.get_transaction_count.return_value = 1
        mock_web3.eth.chain_id = 1
        mock_web3.eth.get_balance.return_value = 10000000000000000000  # 10 ETH
        mock_web3.eth.gas_price = 20000000000
        mock_web3.eth.max_priority_fee = 2000000000

        # Mock vault returns key but signing fails
        vault_service.get_private_key.return_value = "0x123abc"
        mock_web3.eth.account.sign_transaction.side_effect = Exception(
            "Invalid private key format"
        )

        with pytest.raises(Exception, match="Invalid private key format"):
            await usecase.execute(valid_request)

    @pytest.mark.asyncio
    async def test_execute_broadcast_error(
        self, usecase, valid_request, mock_dependencies
    ):
        """Test execute with transaction broadcast error"""
        _, _, vault_service, _, mock_web3 = mock_dependencies

        # Mock successful Web3 setup
        mock_web3.to_checksum_address.side_effect = lambda x: x
        mock_web3.eth.get_transaction_count.return_value = 1
        mock_web3.eth.chain_id = 1
        mock_web3.eth.get_balance.return_value = 10000000000000000000  # 10 ETH
        mock_web3.eth.gas_price = 20000000000
        mock_web3.eth.max_priority_fee = 2000000000

        # Mock successful signing
        vault_service.get_private_key.return_value = "0x123abc"
        mock_signed = Mock()
        mock_signed.raw_transaction.hex.return_value = "0xsigned_tx"
        mock_signed.raw_transaction = b"\x01\x02\x03"
        mock_web3.eth.account.sign_transaction.return_value = mock_signed

        # Mock broadcast error
        mock_web3.eth.send_raw_transaction.side_effect = Exception(
            "Network error: transaction rejected"
        )

        with pytest.raises(Exception, match="Network error: transaction rejected"):
            await usecase.execute(valid_request)

    @pytest.mark.asyncio
    async def test_execute_database_save_error(
        self, usecase, valid_request, mock_dependencies
    ):
        """Test execute with database save error"""
        web3_repo, db_repo, vault_service, _, mock_web3 = mock_dependencies

        # Mock successful Web3 setup and transaction
        mock_web3.to_checksum_address.side_effect = lambda x: x
        mock_web3.eth.get_transaction_count.return_value = 1
        mock_web3.eth.chain_id = 1
        mock_web3.eth.get_balance.return_value = 10000000000000000000  # 10 ETH
        mock_web3.eth.gas_price = 20000000000
        mock_web3.eth.max_priority_fee = 2000000000

        # Mock successful signing and broadcast
        vault_service.get_private_key.return_value = "0x123abc"
        mock_signed = Mock()
        mock_signed.raw_transaction.hex.return_value = "0xsigned_tx"
        mock_signed.raw_transaction = b"\x01\x02\x03"
        mock_web3.eth.account.sign_transaction.return_value = mock_signed

        mock_tx_hash = Mock()
        mock_tx_hash.hex.return_value = "0x123abc456def"
        mock_web3.eth.send_raw_transaction.return_value = mock_tx_hash

        # Mock database save error
        db_repo.save_transaction.side_effect = Exception("Database connection failed")

        with pytest.raises(Exception, match="Database connection failed"):
            await usecase.execute(valid_request)

    @pytest.mark.asyncio
    async def test_execute_max_priority_fee_fallback(
        self, usecase, valid_request, mock_dependencies
    ):
        """Test execute with max_priority_fee fallback when not supported"""
        _, _, vault_service, _, mock_web3 = mock_dependencies

        # Mock Web3 responses
        mock_web3.to_checksum_address.side_effect = lambda x: x
        mock_web3.eth.get_transaction_count.return_value = 1
        mock_web3.eth.chain_id = 1
        mock_web3.eth.get_balance.return_value = 10000000000000000000  # 10 ETH
        mock_web3.eth.gas_price = 20000000000

        # Mock max_priority_fee not supported (AttributeError)
        # Use a property that raises AttributeError when accessed
        def max_priority_fee_getter():
            raise AttributeError("Not supported")

        type(mock_web3.eth).max_priority_fee = property(max_priority_fee_getter)

        # Mock successful signing and broadcast
        vault_service.get_private_key.return_value = "0x123abc"
        mock_signed = Mock()
        mock_signed.raw_transaction.hex.return_value = "0xsigned_tx"
        mock_signed.raw_transaction = b"\x01\x02\x03"
        mock_web3.eth.account.sign_transaction.return_value = mock_signed

        mock_tx_hash = Mock()
        mock_tx_hash.hex.return_value = "0x123abc456def"
        mock_web3.eth.send_raw_transaction.return_value = mock_tx_hash

        # Should not raise exception and use fallback priority fee
        result = await usecase.execute(valid_request)

        assert result.hash == "0x123abc456def"
        assert result.status == "pending"


class TestListTransactionsErrors:
    """Test error scenarios for ListTransactions usecase"""

    @pytest.fixture
    def mock_db_repo(self):
        """Create mock database repository"""
        return AsyncMock()

    @pytest.fixture
    def usecase(self, mock_db_repo):
        """Create ListTransactions usecase with mock"""
        return ListTransactions(db_repo=mock_db_repo)

    @pytest.mark.asyncio
    async def test_execute_database_error(self, usecase, mock_db_repo):
        """Test execute with database error"""
        mock_db_repo.list_transactions.side_effect = Exception(
            "Database connection failed"
        )

        with pytest.raises(Exception, match="Database connection failed"):
            await usecase.execute(limit=10, offset=0)

    @pytest.mark.asyncio
    async def test_execute_with_parameters(self, usecase, mock_db_repo):
        """Test execute with custom parameters"""
        mock_transactions = [
            TransactionEntity(
                hash="0x123",
                asset="ETH",
                address_from="0xfrom",
                address_to="0xto",
                value=1000000000000000000,
                is_token=False,
                type="withdraw",
                status="confirmed",
                effective_fee=21000000000000000,
                created_at=datetime.datetime.now(),
                updated_at=datetime.datetime.now(),
                deleted_at=None,
                contract_address=None,
            )
        ]
        mock_db_repo.list_transactions.return_value = mock_transactions

        result = await usecase.execute(limit=50, offset=100)

        assert result == mock_transactions
        mock_db_repo.list_transactions.assert_called_once_with(limit=50, offset=100)
