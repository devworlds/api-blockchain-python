from unittest.mock import Mock, patch

import pytest

from app.infrastructure.blockchain.transaction.node_repository import (
    Web3TransactionRepository,
)


class MockTransaction:
    """Mock object that behaves like a Web3 transaction"""

    def __init__(self, **kwargs):
        self._data = {}
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value


class TestWeb3TransactionRepositoryErrorHandling:
    """Test error handling and edge cases for Web3TransactionRepository"""

    @pytest.fixture
    def mock_web3(self):
        """Create mock Web3 instance"""
        web3 = Mock()
        mock_tx = MockTransaction(
            hash=Mock(hex=Mock(return_value="0x123")),
            blockNumber=100,
            input="0x",
            value=1000000000000000000,
        )
        mock_tx["from"] = "0xfrom"
        mock_tx["to"] = "0xto"

        web3.eth.get_transaction.return_value = mock_tx
        web3.eth.get_block.return_value = {"number": 110}
        web3.eth.block_number = 110
        return web3

    @pytest.fixture
    def repository(self, mock_web3):
        """Create repository with mock Web3"""
        return Web3TransactionRepository(mock_web3)

    def test_get_transaction_confirmations_no_block_number(self, repository, mock_web3):
        """Test confirmations when transaction has no block number"""
        mock_tx = MockTransaction(
            hash=Mock(hex=Mock(return_value="0x123")),
            blockNumber=None,  # Pending transaction
            input="0x",
            value=1000000000000000000,
        )
        mock_web3.eth.get_transaction.return_value = mock_tx

        confirmations = repository.get_transaction_confirmations("0x123")
        assert confirmations == 0

    def test_get_transaction_confirmations_web3_exception(self, repository, mock_web3):
        """Test confirmations when Web3 raises exception"""
        mock_web3.eth.get_transaction.side_effect = Exception("Network error")

        confirmations = repository.get_transaction_confirmations("0x123")
        assert confirmations == 0

    def test_get_transaction_confirmations_block_number_exception(
        self, repository, mock_web3
    ):
        """Test confirmations when getting block number fails"""
        mock_tx = MockTransaction(blockNumber=100)
        mock_web3.eth.get_transaction.return_value = mock_tx
        mock_web3.eth.block_number = None

        confirmations = repository.get_transaction_confirmations("0x123")
        assert confirmations == 0

    def test_is_valid_transaction_exception(self, repository, mock_web3):
        """Test is_valid_transaction when Web3 raises exception"""
        mock_web3.eth.get_transaction.side_effect = Exception("Network error")

        result = repository.is_valid_transaction("0x123")
        assert result is False

    def test_is_valid_transaction_none_response(self, repository, mock_web3):
        """Test is_valid_transaction when transaction not found"""
        mock_web3.eth.get_transaction.return_value = None

        result = repository.is_valid_transaction("0x123")
        assert result is False

    def test_is_token_transaction_exception(self, repository, mock_web3):
        """Test is_token_transaction when Web3 raises exception"""
        mock_web3.eth.get_transaction.side_effect = Exception("Network error")

        result = repository.is_token_transaction("0x123")
        assert result is False

    def test_is_token_transaction_none_response(self, repository, mock_web3):
        """Test is_token_transaction when transaction not found"""
        mock_web3.eth.get_transaction.return_value = None

        result = repository.is_token_transaction("0x123")
        assert result is False

    def test_is_token_transaction_no_input_field(self, repository, mock_web3):
        """Test is_token_transaction when transaction has no input field"""
        mock_tx = MockTransaction(
            hash=Mock(hex=Mock(return_value="0x123")),
            blockNumber=100,
            # Missing 'input' field
        )
        mock_web3.eth.get_transaction.return_value = mock_tx

        result = repository.is_token_transaction("0x123")
        assert result is False

    def test_get_transaction_exception(self, repository, mock_web3):
        """Test get_transaction when Web3 raises exception"""
        mock_web3.eth.get_transaction.side_effect = Exception("Network error")

        # Should raise exception, not return None
        with pytest.raises(Exception):
            repository.get_transaction("0x123")

    def test_get_transaction_transfers_exception(self, repository, mock_web3):
        """Test get_transaction_transfers when Web3 raises exception"""
        mock_web3.eth.get_transaction.side_effect = Exception("Network error")

        # Should raise exception, not return empty list
        with pytest.raises(Exception):
            repository.get_transaction_transfers("0x123")

    def test_get_transaction_transfers_no_receipt(self, repository, mock_web3):
        """Test get_transaction_transfers when receipt not found"""
        mock_tx = MockTransaction(value=1000000000000000000, input="0x")
        mock_tx["from"] = "0xfrom"
        mock_tx["to"] = "0xto"
        mock_web3.eth.get_transaction.return_value = mock_tx
        mock_web3.eth.get_transaction_receipt.return_value = None

        result = repository.get_transaction_transfers("0x123")
        # Should still return ETH transfer even if receipt is None
        assert len(result) == 1
        assert result[0]["asset"] == "eth"

    def test_get_transaction_transfers_receipt_exception(self, repository, mock_web3):
        """Test get_transaction_transfers when getting receipt fails"""
        mock_tx = MockTransaction(value=1000000000000000000, input="0x")
        mock_tx["from"] = "0xfrom"
        mock_tx["to"] = "0xto"
        mock_web3.eth.get_transaction.return_value = mock_tx
        mock_web3.eth.get_transaction_receipt.side_effect = Exception("Network error")

        result = repository.get_transaction_transfers("0x123")
        # Should still return ETH transfer even if receipt fetch fails
        assert len(result) == 1
        assert result[0]["asset"] == "eth"

    def test_is_transaction_confirmed_with_min_confirmations_zero(
        self, repository, mock_web3
    ):
        """Test is_transaction_confirmed with zero minimum confirmations"""
        mock_tx = MockTransaction(
            hash=Mock(hex=Mock(return_value="0x123")), blockNumber=100
        )
        mock_web3.eth.get_transaction.return_value = mock_tx
        mock_web3.eth.block_number = 100  # Same block, 1 confirmation

        # With 0 min confirmations, should be confirmed
        result = repository.is_transaction_confirmed("0x123", min_confirmations=0)
        assert result is True

    def test_is_transaction_confirmed_pending_transaction(self, repository, mock_web3):
        """Test is_transaction_confirmed with pending transaction"""
        mock_tx = MockTransaction(
            hash=Mock(hex=Mock(return_value="0x123")), blockNumber=None  # Pending
        )
        mock_web3.eth.get_transaction.return_value = mock_tx

        result = repository.is_transaction_confirmed("0x123", min_confirmations=1)
        assert result is False

    def test_is_transaction_confirmed_exception(self, repository, mock_web3):
        """Test is_transaction_confirmed when Web3 raises exception"""
        mock_web3.eth.get_transaction.side_effect = Exception("Network error")

        result = repository.is_transaction_confirmed("0x123", min_confirmations=1)
        assert result is False

    def test_get_transaction_with_empty_input(self, repository, mock_web3):
        """Test get_transaction with empty input field"""
        mock_tx = MockTransaction(
            hash=Mock(hex=Mock(return_value="0x123")),
            blockNumber=100,
            input="0x",  # Empty input
            value=1000000000000000000,
            to="0xto",
        )
        mock_tx["from"] = "0xfrom"
        mock_web3.eth.get_transaction.return_value = mock_tx

        result = repository.get_transaction("0x123")
        assert result is not None
        assert result["input"] == "0x"

    def test_get_transaction_with_token_input(self, repository, mock_web3):
        """Test get_transaction with token transfer input"""
        mock_tx = MockTransaction(
            hash=Mock(hex=Mock(return_value="0x123")),
            blockNumber=100,
            to="0xcontract",
            value=0,
            input="0xa9059cbb000000000000000000000000...",  # Token transfer
        )
        mock_tx["from"] = "0xfrom"
        mock_web3.eth.get_transaction.return_value = mock_tx

        result = repository.get_transaction("0x123")
        assert result is not None
        assert result["input"].startswith("0xa9059cbb")
        assert result["value"] == 0

    def test_get_transaction_transfers_zero_value(self, repository, mock_web3):
        """Test get_transaction_transfers with zero ETH value"""
        mock_tx = MockTransaction(value=0, input="0x")  # No ETH transfer
        mock_tx["from"] = "0xfrom"
        mock_tx["to"] = "0xto"
        mock_web3.eth.get_transaction.return_value = mock_tx
        mock_web3.eth.get_transaction_receipt.return_value = Mock(logs=[])

        result = repository.get_transaction_transfers("0x123")
        # Should return empty list since no ETH transfer and no token transfers
        assert result == []
