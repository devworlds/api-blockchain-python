import datetime
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from web3 import Web3

from app.application.v1.transaction.schemas import TransactionOnChainRequest
from app.application.v1.transaction.usecase import (
    CreateOnChainTransaction,
    GetTransactionHash,
    ListTransactions,
)
from app.domain.wallet.entity import Wallet

# Valid Ethereum addresses for testing
VALID_FROM_ADDRESS = "0x742d35Cc6634C0532925a3b8D0C9964b8d7B1234"
VALID_TO_ADDRESS = "0x8ba1f109551bD432803012645Hac136c0c8b5678"
VALID_CONTRACT_ADDRESS = "0xA0b86a33E6441D6B1c5d8b1d8e4a8B2c3d4e5f90"


@pytest.fixture
def mock_web3_repo():
    repo = Mock()
    web3 = Mock()
    web3.eth.get_transaction_count.return_value = 1
    web3.eth.gas_price = 100_000_000_000  # 100 gwei
    web3.eth.chain_id = 1
    web3.eth.get_balance.return_value = 10**18  # 1 ETH
    web3.eth.max_priority_fee = 2000000000  # 2 gwei
    web3.eth.estimate_gas.return_value = 21000

    # Mock transaction result
    signed_tx_result = Mock()
    signed_tx_result.raw_transaction = Mock()
    signed_tx_result.raw_transaction.hex.return_value = "0x" + "deadbeef" * 32
    web3.eth.account.sign_transaction.return_value = signed_tx_result

    # Mock send transaction result
    send_result = Mock()
    send_result.hex.return_value = "0x" + "abcdef" * 16
    web3.eth.send_raw_transaction.return_value = send_result

    web3.eth.contract.return_value.functions.transfer.return_value.build_transaction.return_value = {
        "data": "0xdata",
        "gas": 0,
        "gasPrice": 0,
    }

    repo.web3 = web3
    return repo


@pytest.fixture
def mock_db_repo():
    repo = Mock()
    repo.save_transaction = AsyncMock()
    return repo


@pytest.fixture
def mock_wallet_repo():
    repo = Mock()
    repo.get_wallet_by_address = AsyncMock()
    return repo


@pytest.fixture
def mock_vault_service():
    vault = Mock()
    vault.get_private_key.return_value = "0x" + "1" * 64
    return vault


@pytest.fixture
def mock_wallet_service():
    wallet = Mock()
    wallet.sign_transaction.return_value = "0x" + "a" * 128
    return wallet


@pytest.mark.asyncio
@patch("app.application.v1.transaction.usecase.Web3")
async def test_create_on_chain_transaction_eth(
    mock_web3_class,
    mock_web3_repo,
    mock_db_repo,
    mock_vault_service,
    mock_wallet_service,
):
    # Mock Web3 class methods
    mock_web3_class.to_checksum_address.side_effect = lambda x: x

    usecase = CreateOnChainTransaction(
        mock_web3_repo, mock_db_repo, mock_vault_service, mock_wallet_service
    )
    req = TransactionOnChainRequest(
        address_from=VALID_FROM_ADDRESS,
        address_to=VALID_TO_ADDRESS,
        asset="ETH",
        value=0.1,  # Use 0.1 ETH instead of 10^18 Wei
        contract_address=None,
    )
    resp = await usecase.execute(req)
    assert resp.hash
    assert resp.status == "pending"
    assert resp.effective_fee > 0
    mock_db_repo.save_transaction.assert_called_once()
    mock_vault_service.get_private_key.assert_called_once()


@pytest.mark.asyncio
@patch("app.application.v1.transaction.usecase.Web3")
async def test_create_token_transaction(
    mock_web3_class,
    mock_web3_repo,
    mock_db_repo,
    mock_vault_service,
    mock_wallet_service,
):
    # Mock Web3 class methods
    mock_web3_class.to_checksum_address.side_effect = lambda x: x

    usecase = CreateOnChainTransaction(
        mock_web3_repo, mock_db_repo, mock_vault_service, mock_wallet_service
    )
    req = TransactionOnChainRequest(
        address_from=VALID_FROM_ADDRESS,
        address_to=VALID_TO_ADDRESS,
        asset="USDT",
        value=1000,
        contract_address=VALID_CONTRACT_ADDRESS,
    )
    resp = await usecase.execute(req)
    assert resp.hash
    assert resp.status == "pending"
    assert resp.effective_fee > 0
    mock_db_repo.save_transaction.assert_called_once()
    mock_vault_service.get_private_key.assert_called_once()


@pytest.mark.asyncio
@patch("app.application.v1.transaction.usecase.Web3")
async def test_missing_contract_address_for_token(
    mock_web3_class,
    mock_web3_repo,
    mock_db_repo,
    mock_vault_service,
    mock_wallet_service,
):
    # Mock Web3 class methods
    mock_web3_class.to_checksum_address.side_effect = lambda x: x

    usecase = CreateOnChainTransaction(
        mock_web3_repo, mock_db_repo, mock_vault_service, mock_wallet_service
    )
    req = TransactionOnChainRequest(
        address_from=VALID_FROM_ADDRESS,
        address_to=VALID_TO_ADDRESS,
        asset="USDT",
        value=1000,
        contract_address=None,
    )
    with pytest.raises(Exception) as exc:
        await usecase.execute(req)
    assert "contract_address" in str(exc.value)


@pytest.mark.asyncio
@patch("app.application.v1.transaction.usecase.Web3")
async def test_missing_fields(
    mock_web3_class,
    mock_web3_repo,
    mock_db_repo,
    mock_vault_service,
    mock_wallet_service,
):
    # Mock Web3 class methods
    mock_web3_class.to_checksum_address.side_effect = lambda x: x

    usecase = CreateOnChainTransaction(
        mock_web3_repo, mock_db_repo, mock_vault_service, mock_wallet_service
    )
    req = TransactionOnChainRequest(
        address_from="",
        address_to=VALID_TO_ADDRESS,
        asset="ETH",
        value=0.1,
        contract_address=None,
    )
    with pytest.raises(Exception):
        await usecase.execute(req)


@pytest.mark.asyncio
async def test_get_transaction_hash_valid_eth(
    mock_web3_repo, mock_wallet_repo, mock_db_repo
):
    mock_wallet_repo.get_wallet_by_address.return_value = None
    mock_db_repo.get_transaction_by_hash = AsyncMock(return_value=None)

    usecase = GetTransactionHash(
        "0x" + "a" * 64,
        mock_web3_repo,
        mock_wallet_repo,
        mock_db_repo,
        min_confirmations=6,
    )
    mock_web3_repo.is_valid_transaction.return_value = True
    mock_web3_repo.is_token_transaction.return_value = False
    mock_web3_repo.get_transaction_confirmations.return_value = 10
    mock_web3_repo.is_transaction_confirmed.return_value = True
    mock_web3_repo.get_transaction.return_value = {
        "input": "0x",
        "value": 1000000000000000000,
        "to": VALID_TO_ADDRESS,
        "from": VALID_FROM_ADDRESS,
        "hash": "0x" + "a" * 64,
    }
    result = await usecase.execute("0x" + "a" * 64)
    assert result["tx_hash"] == "0x" + "a" * 64
    assert result["is_token"] is False
    assert result["confirmations"] == 10
    assert result["is_confirmed"] is True
    assert result["min_confirmations_required"] == 6
    assert result["is_destination_our_wallet"] is False


@pytest.mark.asyncio
async def test_get_transaction_hash_our_wallet_destination(
    mock_web3_repo, mock_wallet_repo, mock_db_repo
):
    # Configure AsyncMock to return None for FROM address and Wallet for TO address
    # Fix: Account for address normalization to lowercase
    async def mock_get_wallet_by_address(address):
        if address.lower() == VALID_TO_ADDRESS.lower():
            return Wallet(
                address=VALID_TO_ADDRESS,
                created_at=datetime.datetime.now(),
                updated_at=datetime.datetime.now(),
                deleted_at=None,
            )
        return None

    mock_wallet_repo.get_wallet_by_address = AsyncMock(
        side_effect=mock_get_wallet_by_address
    )
    mock_db_repo.get_transaction_by_hash = AsyncMock(return_value=None)
    mock_db_repo.save_transaction = AsyncMock()

    usecase = GetTransactionHash(
        "0x" + "a" * 64,
        mock_web3_repo,
        mock_wallet_repo,
        mock_db_repo,
        min_confirmations=6,
    )
    mock_web3_repo.is_valid_transaction.return_value = True
    mock_web3_repo.is_token_transaction.return_value = False
    mock_web3_repo.get_transaction_confirmations.return_value = 10
    mock_web3_repo.is_transaction_confirmed.return_value = True
    mock_web3_repo.get_transaction.return_value = {
        "input": "0x",
        "value": 1000000000000000000,
        "to": VALID_TO_ADDRESS,
        "from": VALID_FROM_ADDRESS,
        "hash": "0x" + "a" * 64,
    }
    result = await usecase.execute("0x" + "a" * 64)
    assert result["is_destination_our_wallet"] is True
    # Verify both addresses were checked (now with lowercase normalization)
    assert mock_wallet_repo.get_wallet_by_address.call_count == 2
    mock_wallet_repo.get_wallet_by_address.assert_any_call(VALID_FROM_ADDRESS.lower())
    mock_wallet_repo.get_wallet_by_address.assert_any_call(VALID_TO_ADDRESS.lower())


@pytest.mark.asyncio
async def test_get_transaction_hash_insufficient_confirmations(
    mock_web3_repo, mock_wallet_repo, mock_db_repo
):
    usecase = GetTransactionHash(
        "0x" + "d" * 64,
        mock_web3_repo,
        mock_wallet_repo,
        mock_db_repo,
        min_confirmations=6,
    )
    mock_web3_repo.get_transaction.return_value = None
    with pytest.raises(Exception) as exc:
        await usecase.execute("0x" + "d" * 64)
    assert "Transaction not found" in str(exc.value)


@pytest.mark.asyncio
async def test_get_transaction_hash_no_confirmation_required(
    mock_web3_repo, mock_wallet_repo, mock_db_repo
):
    mock_wallet_repo.get_wallet_by_address = AsyncMock(return_value=None)
    mock_db_repo.get_transaction_by_hash = AsyncMock(return_value=None)

    usecase = GetTransactionHash(
        "0x" + "e" * 64,
        mock_web3_repo,
        mock_wallet_repo,
        mock_db_repo,
        min_confirmations=0,
    )
    mock_web3_repo.is_valid_transaction.return_value = True
    mock_web3_repo.is_token_transaction.return_value = False
    mock_web3_repo.get_transaction_confirmations.return_value = 2
    mock_web3_repo.is_transaction_confirmed.return_value = False
    mock_web3_repo.get_transaction.return_value = {
        "input": "0x",
        "value": 1000000000000000000,
        "to": VALID_TO_ADDRESS,
        "from": VALID_FROM_ADDRESS,
        "hash": "0x" + "e" * 64,
    }
    result = await usecase.execute("0x" + "e" * 64)
    assert result["confirmations"] == 2
    # When min_confirmations is 0, is_confirmed should be True regardless
    assert result["is_confirmed"] is True
    assert result["is_destination_our_wallet"] is False


@pytest.mark.asyncio
async def test_get_transaction_hash_valid_token(
    mock_web3_repo, mock_wallet_repo, mock_db_repo
):
    mock_wallet_repo.get_wallet_by_address = AsyncMock(return_value=None)
    mock_db_repo.get_transaction_by_hash = AsyncMock(return_value=None)

    usecase = GetTransactionHash(
        "0x" + "b" * 64,
        mock_web3_repo,
        mock_wallet_repo,
        mock_db_repo,
        min_confirmations=6,
    )
    mock_web3_repo.is_valid_transaction.return_value = True
    mock_web3_repo.is_token_transaction.return_value = True
    mock_web3_repo.get_transaction_confirmations.return_value = 5
    mock_web3_repo.is_transaction_confirmed.return_value = True
    mock_web3_repo.get_transaction.return_value = {
        "input": "0xa9059cbb000000000000000000000000...",
        "value": 0,
        "to": VALID_CONTRACT_ADDRESS,
        "from": VALID_FROM_ADDRESS,
        "hash": "0x" + "b" * 64,
    }
    # Mock the token transfers as a list
    mock_web3_repo.get_transaction_transfers.return_value = [
        {
            "asset": "token",
            "from": VALID_FROM_ADDRESS,
            "to": VALID_CONTRACT_ADDRESS,
            "value": 1000,
        }
    ]

    result = await usecase.execute("0x" + "b" * 64)
    assert result["tx_hash"] == "0x" + "b" * 64
    assert result["is_token"] is True
    assert result["tx_data"]["value"] == 0
    assert result["is_destination_our_wallet"] is False


@pytest.mark.asyncio
async def test_get_transaction_hash_not_found(
    mock_web3_repo, mock_wallet_repo, mock_db_repo
):
    usecase = GetTransactionHash(
        "0x" + "c" * 64,
        mock_web3_repo,
        mock_wallet_repo,
        mock_db_repo,
        min_confirmations=0,
    )
    mock_web3_repo.get_transaction.return_value = None
    with pytest.raises(Exception) as exc:
        await usecase.execute("0x" + "c" * 64)
    assert "Transaction not found" in str(exc.value)


@pytest.mark.asyncio
async def test_get_transaction_hash_multiple_transfers(
    mock_web3_repo, mock_wallet_repo, mock_db_repo
):
    mock_wallet_repo.get_wallet_by_address = AsyncMock(return_value=None)
    mock_db_repo.get_transaction_by_hash = AsyncMock(return_value=None)

    # Simula múltiplas transferências (ETH + 2 tokens)
    mock_web3_repo.is_valid_transaction.return_value = True
    mock_web3_repo.is_token_transaction.return_value = True
    mock_web3_repo.get_transaction_confirmations.return_value = 10
    mock_web3_repo.is_transaction_confirmed.return_value = True
    mock_web3_repo.get_transaction.return_value = {
        "input": "0xa9059cbb...",
        "value": 1000,
        "to": VALID_CONTRACT_ADDRESS,
        "from": VALID_FROM_ADDRESS,
        "hash": "0x" + "f" * 64,
    }
    mock_web3_repo.get_transaction_transfers.return_value = [
        {
            "asset": "eth",
            "from": VALID_FROM_ADDRESS,
            "to": VALID_CONTRACT_ADDRESS,
            "value": 1000,
        },
        {"asset": "token", "from": VALID_FROM_ADDRESS, "to": "0x1", "value": 500},
        {"asset": "token", "from": VALID_FROM_ADDRESS, "to": "0x2", "value": 1500},
    ]
    usecase = GetTransactionHash(
        "0x" + "f" * 64,
        mock_web3_repo,
        mock_wallet_repo,
        mock_db_repo,
        min_confirmations=6,
    )
    result = await usecase.execute("0x" + "f" * 64)
    assert len(result["transfers"]) == 3
    assert result["transfers"][0]["asset"] == "eth"
    assert result["transfers"][1]["asset"] == "token"
    assert result["transfers"][2]["value"] == 1500
