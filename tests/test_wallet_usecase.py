import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.v1.wallet.usecase import (
    CreateWalletsUseCase,
    GetAllWalletsUseCase,
    SignTransactionWithVaultWalletUseCase,
)
from app.domain.wallet.entity import Wallet


@pytest.mark.asyncio
async def test_create_wallets_usecase():
    vault_service = MagicMock()
    wallet_service = MagicMock()
    wallet_repository = MagicMock()
    wallet_repository.save_wallet = AsyncMock()
    # Simula criação de 2 wallets
    wallet_service.create_wallet.side_effect = [
        {"address": "0xabc", "private_key": "priv1"},
        {"address": "0xdef", "private_key": "priv2"},
    ]
    usecase = CreateWalletsUseCase(vault_service, wallet_service, wallet_repository)
    addresses = await usecase.execute(2)
    assert addresses == ["0xabc", "0xdef"]
    assert vault_service.store_private_key.call_count == 2
    assert wallet_repository.save_wallet.call_count == 2


def test_sign_transaction_with_vault_wallet_usecase():
    vault_service = MagicMock()
    wallet_service = MagicMock()
    vault_service.get_private_key.return_value = "privkey"
    wallet_service.sign_transaction.return_value = "signedtx"
    usecase = SignTransactionWithVaultWalletUseCase(vault_service, wallet_service)
    signed = usecase.execute("0xabc", {"to": "0xdef", "value": 1})
    assert signed == "signedtx"
    vault_service.get_private_key.assert_called_once_with("eth_wallet_0xabc")
    wallet_service.sign_transaction.assert_called_once_with(
        "privkey", {"to": "0xdef", "value": 1}
    )


@pytest.mark.asyncio
async def test_get_all_wallets_usecase():
    conn = MagicMock()
    # Simula retorno do banco
    conn.fetch = AsyncMock(return_value=[{"address": "0xabc"}, {"address": "0xdef"}])
    usecase = GetAllWalletsUseCase(conn)
    result = await usecase.execute()
    assert result == [{"address": "0xabc"}, {"address": "0xdef"}]
    conn.fetch.assert_called_once()
