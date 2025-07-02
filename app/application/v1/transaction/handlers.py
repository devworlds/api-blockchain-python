from app.application.v1.transaction.dto import TransactionDTO
from app.application.v1.transaction.schemas import (TransactionHashResponse,
                                                    TransactionOnChainRequest,
                                                    TransactionOnChainResponse)
from app.application.v1.transaction.usecase import (CreateOnChainTransaction,
                                                    GetTransactionHash,
                                                    ListTransactions)
from app.shared.monitoring.logging import get_logger
from app.shared.utils.validators import wei_to_eth

logger = get_logger(__name__)


async def check_transaction_handler(
    tx_hash: str, usecase: GetTransactionHash
) -> TransactionHashResponse:
    result = await usecase.execute(tx_hash)

    # Extract transaction data
    tx_data = result["tx_data"]
    is_token = result["is_token"]
    confirmations = result["confirmations"]
    is_confirmed = result["is_confirmed"]
    min_confirmations_required = result["min_confirmations_required"]
    is_destination_our_wallet = result["is_destination_our_wallet"]

    # Determine asset type
    asset = "token" if is_token else "eth"

    transfers = [
        TransactionDTO(
            asset=transfer["asset"],
            address_from=transfer.get("from") or transfer.get("address_from", ""),
            value=wei_to_eth(transfer["value"]),
        )
        for transfer in result.get("transfers", [])
    ]

    return TransactionHashResponse(
        is_valid=True,
        transfers=transfers,
        confirmations=confirmations,
        is_confirmed=is_confirmed,
        min_confirmations_required=min_confirmations_required,
        is_destination_our_wallet=is_destination_our_wallet,
    )


async def create_onchain_transaction_handler(
    request: TransactionOnChainRequest, usecase: CreateOnChainTransaction
) -> TransactionOnChainResponse:
    return await usecase.execute(request)


async def list_transactions_handler(
    usecase: ListTransactions, limit: int = 100, offset: int = 0
):
    transactions = await usecase.execute(limit=limit, offset=offset)
    return [
        TransactionDTO(
            asset=tx.asset, address_from=tx.address_from, value=wei_to_eth(tx.value)
        )
        for tx in transactions
    ]
